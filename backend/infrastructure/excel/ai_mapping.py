"""Bounded, schema-only OpenAI assistance for unfamiliar Excel headers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from openai import OpenAI
from openpyxl import load_workbook
from pydantic import BaseModel, ConfigDict, Field

from backend.domain.enums import ImportSourceType


class ExcelColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet_index: int = Field(ge=0)
    header_row: int = Field(ge=1, le=30)
    columns: dict[str, int]


class MappingUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkbookPreview:
    sheets: tuple[tuple[tuple[Any, ...], ...], ...]

    @classmethod
    def read(cls, content: bytes) -> WorkbookPreview:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        try:
            sheets = tuple(
                tuple(
                    tuple(row[:60])
                    for row in sheet.iter_rows(min_row=1, max_row=min(sheet.max_row, 30), values_only=True)
                )
                for sheet in workbook.worksheets[:8]
            )
            return cls(sheets=sheets)
        finally:
            workbook.close()

    def candidates(self) -> list[dict[str, Any]]:
        candidates: list[tuple[int, dict[str, Any]]] = []
        header_words = re.compile(
            r"код|артикул|склад|товар|номенклат|колич|остат|продаж|месяц|период|"
            r"срок|постав|заказ|дата|коэф|sku|quantity|warehouse|supplier|product|"
            r"янв|фев|март|апр|июн|июл|авг|сент|окт|ноя|дек",
            re.IGNORECASE,
        )
        for sheet_index, rows in enumerate(self.sheets):
            for row_index, row in enumerate(rows):
                labels = [str(value).strip() if isinstance(value, str) else ""
                          for value in row]
                score = sum(bool(header_words.search(label)) for label in labels)
                if score < 2:
                    continue
                following = rows[row_index + 1:row_index + 4]
                candidates.append((score, {
                    "sheet_index": sheet_index,
                    "header_row": row_index + 1,
                    "headers": [self._safe_label(value) for value in row[:60]],
                    "sample_types": [
                        [self._value_type(value) for value in sample[:60]]
                        for sample in following
                    ],
                    "sample_values": [
                        [self._safe_sample_value(value, row[index] if index < len(row) else None)
                         for index, value in enumerate(sample[:24])]
                        for sample in following[:2]
                    ],
                }))
        candidates.sort(key=lambda item: item[0], reverse=True)
        return [candidate for _, candidate in candidates[:6]]

    @staticmethod
    def _safe_label(value: Any) -> str:
        if not isinstance(value, str):
            return ""
        label = value.strip()[:80]
        if "@" in label or re.search(r"\+?\d[\d() -]{8,}\d", label):
            return "[скрыто]"
        return label

    @staticmethod
    def _value_type(value: Any) -> str:
        if value is None:
            return "empty"
        if isinstance(value, (date, datetime)):
            return "date"
        if isinstance(value, (int, float, Decimal)):
            return "number"
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return "empty"
            if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
                return "numeric_text"
            if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{4}.*", text):
                return "date_text"
            return "text"
        return type(value).__name__[:24]

    @staticmethod
    def _safe_sample_value(value: Any, header: Any) -> str:
        label = str(header or "").lower()
        if any(term in label for term in ("клиент", "customer", "фио", "телефон", "email", "адрес")):
            return "[скрыто]"
        if value is None:
            return ""
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, (int, float, Decimal)):
            return str(value)[:24]
        text = str(value).strip()
        if "@" in text or re.search(r"\+?\d[\d() -]{8,}\d", text):
            return "[скрыто]"
        if any(term in label for term in ("код", "артикул", "склад", "поставщик", "дата", "месяц", "период", "ед")):
            return text[:24]
        if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
            return text[:24]
        return "[текст]"


class AiExcelMappingAssistant:
    def __init__(self, api_key: str | None, model: str, timeout: float) -> None:
        key = (api_key or "").strip()
        self._client = OpenAI(api_key=key, timeout=timeout) if key and not key.startswith("your-") else None
        self._model = model

    def infer(
        self,
        source: ImportSourceType,
        preview: WorkbookPreview,
        allowed_fields: set[str],
        required_fields: tuple[str, ...],
    ) -> ExcelColumnMapping:
        if self._client is None:
            raise MappingUnavailableError("OPENAI_API_KEY не настроен для распознавания нестандартных столбцов")
        candidates = preview.candidates()
        if not candidates:
            raise MappingUnavailableError("В книге не найдена строка заголовков")
        prompt = {
            "source_type": source.value,
            "allowed_fields": sorted(allowed_fields),
            "required_fields": list(required_fields),
            "field_guidance": {
                "sku": "Внутренний код номенклатуры/код 1С, не артикул поставщика",
                "warehouse_code": "Код или название склада, только если склад указан в файле",
                "supplier_code": "Код или название организации-поставщика, не артикул товара",
                "quantity": "Количество единиц товара",
                "quantity_on_hand": "Фактический остаток товара",
                "moq": "Минимальная разрешенная партия отгрузки",
                "coefficient": "Коэффициент сезонности, не объем продаж",
            },
            "candidates": candidates,
        }
        try:
            completion = self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": (
                        "Определи строку заголовков и сопоставь реальные колонки Excel с полями схемы. "
                        "Индексы колонок начинаются с 0. Выбирай только наблюдаемые колонки, "
                        "не придумывай отсутствующие поля и значения. 'sample_types' содержит только типы, "
                        "Примеры содержат не более двух коротких значений на столбец. "
                        "Ответ только по заданной JSON-схеме."
                    )},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                response_format=ExcelColumnMapping,
                temperature=0,
            )
            mapping = completion.choices[0].message.parsed
        except Exception as error:
            raise MappingUnavailableError("OpenAI не смог определить столбцы файла") from error
        if mapping is None or mapping.sheet_index >= len(preview.sheets):
            raise MappingUnavailableError("OpenAI вернул неверный лист Excel")
        rows = preview.sheets[mapping.sheet_index]
        if mapping.header_row > len(rows):
            raise MappingUnavailableError("OpenAI вернул неверную строку заголовков")
        header = rows[mapping.header_row - 1]
        if (not set(mapping.columns).issubset(allowed_fields)
                or len(set(mapping.columns.values())) != len(mapping.columns)
                or any(index < 0 or index >= len(header) or header[index] is None
                       for index in mapping.columns.values())):
            raise MappingUnavailableError("OpenAI вернул недопустимое соответствие столбцов")
        return mapping
