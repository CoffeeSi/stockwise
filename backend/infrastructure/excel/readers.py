from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

import pandas as pd

from backend.application.dto.imports import ImportFileCommand, ParsedImport
from backend.domain.enums import ImportSourceType
from backend.infrastructure.excel.ai_mapping import (
    AiExcelMappingAssistant, MappingUnavailableError, WorkbookPreview,
)


class ExcelImportValidationError(ValueError):
    def __init__(self, message: str, *, issues: list[dict[str, Any]] | None = None) -> None:
        self.issues = issues or []
        super().__init__(message)


def _header(value: object) -> str:
    text = str(value).strip().lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я0-9]+", "_", text).strip("_")


COMMON_ALIASES: dict[str, tuple[str, ...]] = {
    "sku": (
        "sku", "артикул", "код_товара", "код", "номенклатурный_номер",
        "код_1с", "номенклатура_код",
    ),
    "product_name": ("product_name", "наименование", "номенклатура", "товар"),
    "unit": ("unit", "единица", "ед_изм", "единица_измерения", "ед"),
    "category_code": ("category_code", "код_категории", "категория"),
    "category_name": ("category_name", "наименование_категории", "категория"),
    "warehouse_code": ("warehouse_code", "код_склада", "склад"),
    "warehouse_name": ("warehouse_name", "наименование_склада", "склад"),
    "supplier_code": ("supplier_code", "код_поставщика", "поставщик"),
    "supplier_name": ("supplier_name", "наименование_поставщика", "поставщик"),
}


SOURCE_ALIASES: dict[ImportSourceType, dict[str, tuple[str, ...]]] = {
    ImportSourceType.SALES: {
        "sold_at": ("sold_at", "дата", "дата_продажи", "дата_документа"),
        "source_row_number": ("source_row_number", "номер_строки"),
        "external_document_number": (
            "external_document_number", "номер_документа", "документ", "номер"
        ),
        "anonymous_customer_id": (
            "anonymous_customer_id", "обезличенный_id_клиента"
        ),
        "transaction_type": ("transaction_type", "тип_операции", "вид_операции"),
        "quantity": ("quantity", "количество", "кол_во", "объем"),
        "unit_price": ("unit_price", "цена", "цена_за_единицу"),
        "total_amount": ("total_amount", "сумма", "стоимость"),
    },
    ImportSourceType.MONTHLY_SALES: {
        "period_start": ("period_start", "начало_периода", "месяц", "период"),
        "period_end": ("period_end", "конец_периода"),
        "quantity": ("quantity", "количество", "продажи"),
    },
    ImportSourceType.INVENTORY: {
        "snapshot_at": ("snapshot_at", "дата", "дата_остатка", "период"),
        "quantity_on_hand": ("quantity_on_hand", "остаток", "количество_на_складе"),
        "quantity_reserved": ("quantity_reserved", "резерв", "зарезервировано"),
        "quantity_available": ("quantity_available", "доступно", "свободный_остаток"),
    },
    ImportSourceType.STOCKOUT: {
        "started_at": ("started_at", "начало", "дата_начала"),
        "ended_at": ("ended_at", "окончание", "дата_окончания"),
        "source": ("source", "источник"),
        "confidence": ("confidence", "уверенность"),
    },
    ImportSourceType.IN_TRANSIT: {
        "external_order_number": (
            "external_order_number", "номер_заказа", "заказ", "документ"
        ),
        "quantity": ("quantity", "количество", "кол_во"),
        "expected_at": ("expected_at", "дата_поступления", "ожидаемая_дата", "дата"),
        "status": ("status", "статус"),
    },
    ImportSourceType.SEASONALITY: {
        "month": ("month", "месяц", "номер_месяца"),
        "coefficient": (
            "coefficient", "коэффициент", "индекс_сезонности", "норм_коэф"
        ),
        "valid_from": ("valid_from", "действует_с", "дата_начала"),
        "valid_to": ("valid_to", "действует_до", "дата_окончания"),
        "version": ("version", "версия"),
    },
    ImportSourceType.SUPPLIER_TERMS: {
        "moq": (
            "moq", "минимальная_партия", "мин_партия", "мин_разр_к_отгр"
        ),
        "package_size": ("package_size", "кратность", "размер_упаковки"),
        "lead_time_days": ("lead_time_days", "срок_поставки", "срок_поставки_дней"),
        "purchase_price": ("purchase_price", "закупочная_цена", "цена"),
        "currency": ("currency", "валюта"),
        "priority": ("priority", "приоритет"),
        "is_primary": ("is_primary", "основной", "приоритетный_поставщик"),
    },
    ImportSourceType.GROWTH: {
        "growth_rate": ("growth_rate", "темп_роста", "прирост", "коэффициент_роста"),
        "valid_from": ("valid_from", "действует_с", "дата_начала"),
        "valid_to": ("valid_to", "действует_до", "дата_окончания"),
        "source": ("source", "источник"),
    },
    ImportSourceType.MATERIAL_REQUIREMENTS: {
        "external_document_number": (
            "external_document_number", "номер_документа", "документ"
        ),
        "required_quantity": ("required_quantity", "потребность", "количество"),
        "required_at": ("required_at", "дата_потребности", "дата"),
        "status": ("status", "статус"),
    },
}


REQUIRED: dict[ImportSourceType, tuple[str, ...]] = {
    ImportSourceType.SALES: ("sku", "warehouse_code", "sold_at", "quantity"),
    ImportSourceType.MONTHLY_SALES: ("sku", "period_start", "quantity"),
    ImportSourceType.INVENTORY: (
        "sku", "warehouse_code", "snapshot_at", "quantity_on_hand"
    ),
    ImportSourceType.STOCKOUT: ("sku", "warehouse_code", "started_at"),
    ImportSourceType.IN_TRANSIT: (
        "sku", "warehouse_code", "supplier_code", "quantity"
    ),
    ImportSourceType.SEASONALITY: ("month", "coefficient"),
    ImportSourceType.SUPPLIER_TERMS: ("sku", "supplier_code", "moq"),
    ImportSourceType.GROWTH: ("growth_rate", "valid_from"),
    ImportSourceType.MATERIAL_REQUIREMENTS: (
        "sku", "warehouse_code", "required_quantity", "required_at"
    ),
}

FORBIDDEN_PERSONAL_HEADERS = {
    "фио", "имя_клиента", "фамилия", "телефон", "email", "e_mail",
    "адрес_клиента", "наименование_клиента", "клиент", "id_клиента", "клиент_id",
}

OPAQUE_CUSTOMER_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,254}\Z")


class ExcelImportReader:
    """Read partner XLSX files into source-specific normalized dictionaries."""

    def __init__(self, ai_mapper: AiExcelMappingAssistant | None = None) -> None:
        self._ai_mapper = ai_mapper

    def read(self, command: ImportFileCommand) -> ParsedImport:
        try:
            preview = WorkbookPreview.read(command.content)
            sheet_index, header_row = self._initial_header(preview, command.source_type)
            frame = self._read_frame(command.content, sheet_index, header_row)
        except Exception as error:
            raise ExcelImportValidationError("cannot read XLSX workbook") from error
        warnings: list[dict[str, Any]] = []
        frame = self._prepare_frame(command.source_type, frame, warnings=warnings)
        missing = [name for name in REQUIRED[command.source_type] if name not in frame.columns]
        if missing and self._ai_mapper is not None:
            try:
                aliases = {**COMMON_ALIASES, **SOURCE_ALIASES[command.source_type]}
                mapping = self._ai_mapper.infer(
                    command.source_type, preview, set(aliases), REQUIRED[command.source_type],
                )
                frame = self._read_frame(command.content, mapping.sheet_index, mapping.header_row - 1)
                warnings.clear()
                frame = self._prepare_frame(
                    command.source_type, frame, mapping.columns, warnings=warnings,
                )
                missing = [name for name in REQUIRED[command.source_type] if name not in frame.columns]
            except MappingUnavailableError as error:
                raise ExcelImportValidationError(
                    "cannot determine workbook columns",
                    issues=[{"code": "ai_mapping_unavailable"}, {"missing_columns": missing}],
                ) from error
        if missing:
            raise ExcelImportValidationError(
                "required columns are missing",
                issues=[{"missing_columns": missing}],
            )

        issues: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        for offset, (_, series) in enumerate(frame.iterrows(), start=2):
            try:
                rows.append(self._normalize_row(command.source_type, series, offset))
            except (TypeError, ValueError, InvalidOperation) as error:
                issues.append({"row": offset, "message": str(error)})
                if len(issues) >= 50:
                    break
        if issues:
            raise ExcelImportValidationError(
                f"{len(issues)} invalid row(s) found",
                issues=issues,
            )
        if not rows:
            raise ExcelImportValidationError("workbook contains no valid data rows")
        return ParsedImport(
            source_type=command.source_type, rows=tuple(rows), warnings=tuple(warnings),
        )

    @staticmethod
    def _read_frame(content: bytes, sheet_index: int, header_row: int) -> pd.DataFrame:
        return pd.read_excel(
            BytesIO(content), sheet_name=sheet_index, header=header_row,
            dtype=object, engine="openpyxl",
        )

    @staticmethod
    def _initial_header(preview: WorkbookPreview, source: ImportSourceType) -> tuple[int, int]:
        if source is ImportSourceType.SEASONALITY:
            for sheet_index, rows in enumerate(preview.sheets):
                for row_index, row in enumerate(rows):
                    headers = {_header(value) for value in row if value is not None}
                    if {"месяц", "норм_коэф"}.issubset(headers):
                        return sheet_index, row_index
        return 0, 0

    def _prepare_frame(
        self, source: ImportSourceType, frame: pd.DataFrame,
        ai_columns: dict[str, int] | None = None,
        *, warnings: list[dict[str, Any]],
    ) -> pd.DataFrame:
        frame = frame.dropna(how="all")
        normalized_headers = {_header(column): column for column in frame.columns}
        forbidden = sorted(
            name for name in normalized_headers if self._is_forbidden_personal_header(name)
        )
        if forbidden:
            raise ExcelImportValidationError(
                "direct customer identifiers are forbidden",
                issues=[{"columns": forbidden}],
            )

        aliases = {**COMMON_ALIASES, **SOURCE_ALIASES[source]}
        rename: dict[object, str] = {}
        if ai_columns:
            for canonical, index in ai_columns.items():
                column = frame.columns[index]
                if (source in {ImportSourceType.MONTHLY_SALES, ImportSourceType.INVENTORY}
                        and self._date_from_header(column) is not None
                        and canonical in {"period_start", "snapshot_at", "quantity", "quantity_on_hand"}):
                    continue
                if (source is ImportSourceType.IN_TRANSIT
                        and "поступление до" in str(column).lower()
                        and canonical in {"quantity", "expected_at", "external_order_number"}):
                    continue
                rename[column] = canonical
        for canonical, variants in aliases.items():
            if canonical in rename.values():
                continue
            for variant in variants:
                original = normalized_headers.get(_header(variant))
                if original is not None:
                    rename.setdefault(original, canonical)
                    break
        frame = frame.rename(columns=rename)
        return self._apply_partner_profile(source, normalized_headers, frame, warnings)

    def _apply_partner_profile(
        self, source: ImportSourceType, headers: dict[str, object], frame: pd.DataFrame,
        warnings: list[dict[str, Any]],
    ) -> pd.DataFrame:
        names = set(headers)
        if source is ImportSourceType.SALES and {"дата", "код", "склад", "количество"}.issubset(names):
            frame = self._drop_partner_nondata_rows(frame)
        elif source in {ImportSourceType.MONTHLY_SALES, ImportSourceType.INVENTORY} and "номенклатура_код" in names:
            frame = self._drop_partner_nondata_rows(frame)
            if "warehouse_code" not in frame.columns:
                frame["warehouse_code"] = "__ALL_WAREHOUSES__"
                frame["warehouse_name"] = "Все склады (агрегированные данные)"
        elif source is ImportSourceType.IN_TRANSIT and {"код_1с", "артикул_иэк"}.issubset(names):
            frame = self._drop_partner_nondata_rows(frame)
            if "warehouse_code" not in frame.columns:
                frame["warehouse_code"] = "__ALL_WAREHOUSES__"
                frame["warehouse_name"] = "Все склады (агрегированные данные)"
            if "supplier_code" not in frame.columns:
                frame["supplier_code"] = "IEK_KAZAKHSTAN"
                frame["supplier_name"] = "IEK Казахстан"
        elif source is ImportSourceType.SEASONALITY and {"месяц", "норм_коэф"}.issubset(names):
            frame = frame.loc[frame["month"].map(self._month_from_header).notna()].copy()
            frame["month"] = frame["month"].map(self._month_from_header)
            if "sku" not in frame.columns and "category_code" not in frame.columns:
                frame["category_code"] = "__ALL_PRODUCTS__"
                frame["category_name"] = "Все товары (общая сезонность)"
        frame = self._apply_supplier_terms_profile(source, headers, frame, warnings)
        return self._reshape_wide(source, frame)

    @staticmethod
    def _drop_partner_nondata_rows(frame: pd.DataFrame) -> pd.DataFrame:
        missing_sku = frame["sku"].isna() | frame["sku"].astype(str).str.strip().eq("")
        if "product_name" in frame.columns:
            label = frame["product_name"].fillna("").astype(str).str.strip().str.lower()
        else:
            label = pd.Series("", index=frame.index)
        summary = label.eq("") | label.eq("итого")
        if "sold_at" in frame.columns:
            summary = summary | frame["sold_at"].fillna("").astype(str).str.strip().str.lower().eq("итого")
        return frame.loc[~(missing_sku & summary)].copy()

    @staticmethod
    def _apply_supplier_terms_profile(
        source: ImportSourceType,
        normalized_headers: dict[str, object],
        frame: pd.DataFrame,
        warnings: list[dict[str, Any]],
    ) -> pd.DataFrame:
        """Recognize the partner's IEK MOQ workbook, which omits supplier columns."""
        headers = set(normalized_headers)
        is_iek_moq_template = {
            "код_1с", "артикул_поставщика", "мин_разр_к_отгр"
        }.issubset(headers)
        if source is not ImportSourceType.SUPPLIER_TERMS or not is_iek_moq_template:
            return frame

        # The template is explicitly the IEK supplier catalog. Its 1C code is
        # the product key used by sales imports; the supplier article is not.
        if "supplier_code" not in frame.columns:
            frame["supplier_code"] = "IEK_KAZAKHSTAN"
            frame["supplier_name"] = "IEK Казахстан"
        missing_moq = frame["moq"].isna() | frame["moq"].astype(str).str.strip().isin({"#N/A", "N/A"})
        skipped = int(missing_moq.sum())
        if skipped:
            warnings.append({"code": "missing_moq", "count": skipped})
        return frame.loc[~missing_moq].copy()

    def _reshape_wide(
        self, source: ImportSourceType, frame: pd.DataFrame
    ) -> pd.DataFrame:
        if source is ImportSourceType.MONTHLY_SALES and not {
            "period_start", "quantity"
        }.issubset(frame.columns):
            return self._melt_period_columns(
                frame, period_name="period_start", value_name="quantity"
            )
        if source is ImportSourceType.INVENTORY and not {
            "snapshot_at", "quantity_on_hand"
        }.issubset(frame.columns):
            return self._melt_period_columns(
                frame, period_name="snapshot_at", value_name="quantity_on_hand"
            )
        if source is ImportSourceType.IN_TRANSIT and "quantity" not in frame.columns:
            return self._melt_order_columns(frame)
        if source is ImportSourceType.SEASONALITY and not {
            "month", "coefficient"
        }.issubset(frame.columns):
            return self._melt_month_columns(frame)
        return frame

    def _melt_period_columns(
        self,
        frame: pd.DataFrame,
        *,
        period_name: str,
        value_name: str,
    ) -> pd.DataFrame:
        period_columns: dict[object, date] = {}
        for column in frame.columns:
            parsed = self._date_from_header(column)
            if parsed is not None:
                period_columns[column] = parsed
        if not period_columns:
            return frame
        identifier_columns = [
            column for column in frame.columns if column not in period_columns
        ]
        records: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            base = {
                column: row[column]
                for column in identifier_columns
                if not self._missing(row[column])
            }
            for column, period in period_columns.items():
                value = row[column]
                if self._missing(value):
                    continue
                records.append(
                    {**base, period_name: period, value_name: value}
                )
        return pd.DataFrame.from_records(records)

    def _melt_order_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        order_columns: dict[object, tuple[date, str]] = {}
        for column in frame.columns:
            title = str(column)
            if "поступление до" not in title.lower():
                continue
            expected_at = self._date_from_header(title)
            order = re.search(r"УТ-\d+", title, flags=re.IGNORECASE)
            if expected_at is not None and order is not None:
                order_columns[column] = expected_at, order.group().upper()
        if not order_columns:
            return frame
        identifier_columns = [column for column in frame.columns if column not in order_columns]
        records: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            base = {
                column: row[column]
                for column in identifier_columns
                if not self._missing(row[column])
            }
            for column, (expected_at, order_number) in order_columns.items():
                value = row[column]
                if self._missing(value):
                    continue
                records.append({
                    **base, "external_order_number": order_number,
                    "expected_at": expected_at, "quantity": value,
                })
        return pd.DataFrame.from_records(records)

    def _melt_month_columns(self, frame: pd.DataFrame) -> pd.DataFrame:
        month_columns: dict[object, int] = {}
        for column in frame.columns:
            month = self._month_from_header(column)
            if month is not None:
                month_columns[column] = month
        if not month_columns:
            return frame
        identifier_columns = [
            column for column in frame.columns if column not in month_columns
        ]
        records: list[dict[str, Any]] = []
        for _, row in frame.iterrows():
            base = {
                column: row[column]
                for column in identifier_columns
                if not self._missing(row[column])
            }
            for column, month in month_columns.items():
                value = row[column]
                if self._missing(value):
                    continue
                records.append({**base, "month": month, "coefficient": value})
        return pd.DataFrame.from_records(records)

    def _normalize_row(
        self, source: ImportSourceType, row: pd.Series, row_number: int
    ) -> dict[str, Any]:
        result = {
            key: self._clean(value)
            for key, value in row.items()
            if isinstance(key, str) and not self._missing(value)
        }
        result["source_row_number"] = row_number
        for name in REQUIRED[source]:
            if name not in result or result[name] in (None, ""):
                raise ValueError(f"{name} is required")

        for name in self._decimal_fields(source):
            if name in result:
                result[name] = self._decimal(result[name], name)
        for name in self._datetime_fields(source):
            if name in result:
                result[name] = self._datetime(result[name], name)
        for name in self._date_fields(source):
            if name in result:
                result[name] = self._date(result[name], name)
        for name in ("month", "version", "lead_time_days", "priority"):
            if name in result:
                result[name] = int(result[name])
        if "is_primary" in result:
            result["is_primary"] = self._boolean(result["is_primary"])
        if source is ImportSourceType.SALES and "anonymous_customer_id" in result:
            customer_id = str(result["anonymous_customer_id"]).strip()
            if (not OPAQUE_CUSTOMER_ID.fullmatch(customer_id) or
                    re.fullmatch(r"\d{10,15}", customer_id)):
                # Never echo the original value into validation errors or logs.
                raise ValueError("anonymous_customer_id must be an opaque pseudonym, not contact data")
            result["anonymous_customer_id"] = customer_id

        result.setdefault("product_name", str(result.get("sku", "")))
        result.setdefault("unit", "pcs")
        if "warehouse_code" in result:
            result.setdefault("warehouse_name", str(result["warehouse_code"]))
        if "supplier_code" in result:
            result.setdefault("supplier_name", str(result["supplier_code"]))
        return self._source_defaults(source, result)

    @staticmethod
    def _source_defaults(source: ImportSourceType, row: dict[str, Any]) -> dict[str, Any]:
        if source is ImportSourceType.SALES:
            quantity = row["quantity"]
            transaction_type = str(row.get("transaction_type", "")).lower()
            is_return = quantity < 0 or transaction_type in {"return", "возврат"}
            row["transaction_type"] = "return" if is_return else "sale"
            row["quantity"] = -abs(quantity) if is_return else abs(quantity)
            if "total_amount" not in row and "unit_price" in row:
                row["total_amount"] = row["quantity"] * row["unit_price"]
        elif source is ImportSourceType.MONTHLY_SALES:
            start = row["period_start"]
            row.setdefault("period_end", ExcelImportReader._month_end(start))
        elif source is ImportSourceType.INVENTORY:
            row.setdefault("quantity_reserved", Decimal("0"))
            row.setdefault(
                "quantity_available",
                row["quantity_on_hand"] - row["quantity_reserved"],
            )
        elif source is ImportSourceType.STOCKOUT:
            row["source"] = {
                "импорт": "imported",
                "расчет": "inferred",
                "ручной": "manual",
            }.get(str(row.get("source", "imported")).lower(), str(row.get("source", "imported")).lower())
        elif source is ImportSourceType.IN_TRANSIT:
            row["status"] = {
                "запланирован": "planned",
                "в_пути": "in_transit",
                "в пути": "in_transit",
                "получен": "received",
                "отменен": "cancelled",
            }.get(str(row.get("status", "in_transit")).lower(), str(row.get("status", "in_transit")).lower())
        elif source is ImportSourceType.SEASONALITY:
            if ("sku" in row) == ("category_code" in row):
                raise ValueError("exactly one of sku or category_code is required")
            row.setdefault("valid_from", date(2026, 1, 1))
            row.setdefault("version", 1)
        elif source is ImportSourceType.SUPPLIER_TERMS:
            row.setdefault("package_size", Decimal("1"))
            row.setdefault("lead_time_days", 0)
            row.setdefault("priority", 100)
            row.setdefault("is_primary", False)
        elif source is ImportSourceType.GROWTH:
            if "sku" not in row and "category_code" not in row:
                raise ValueError("sku or category_code is required")
            row["source"] = {
                "расчет": "calculated",
                "импорт": "imported",
                "ручной": "manual",
            }.get(str(row.get("source", "imported")).lower(), str(row.get("source", "imported")).lower())
        elif source is ImportSourceType.MATERIAL_REQUIREMENTS:
            row["status"] = {
                "запланирован": "planned",
                "выполнен": "fulfilled",
                "отменен": "cancelled",
            }.get(str(row.get("status", "planned")).lower(), str(row.get("status", "planned")).lower())
        return row

    @staticmethod
    def _decimal_fields(source: ImportSourceType) -> tuple[str, ...]:
        fields = {
            ImportSourceType.SALES: ("quantity", "unit_price", "total_amount"),
            ImportSourceType.MONTHLY_SALES: ("quantity",),
            ImportSourceType.INVENTORY: (
                "quantity_on_hand", "quantity_reserved", "quantity_available"
            ),
            ImportSourceType.STOCKOUT: ("confidence",),
            ImportSourceType.IN_TRANSIT: ("quantity",),
            ImportSourceType.SEASONALITY: ("coefficient",),
            ImportSourceType.SUPPLIER_TERMS: (
                "moq", "package_size", "purchase_price"
            ),
            ImportSourceType.GROWTH: ("growth_rate",),
            ImportSourceType.MATERIAL_REQUIREMENTS: ("required_quantity",),
        }
        return fields[source]

    @staticmethod
    def _datetime_fields(source: ImportSourceType) -> tuple[str, ...]:
        fields = {
            ImportSourceType.SALES: ("sold_at",),
            ImportSourceType.INVENTORY: ("snapshot_at",),
            ImportSourceType.STOCKOUT: ("started_at", "ended_at"),
            ImportSourceType.IN_TRANSIT: ("expected_at",),
            ImportSourceType.MATERIAL_REQUIREMENTS: ("required_at",),
        }
        return fields.get(source, ())

    @staticmethod
    def _date_fields(source: ImportSourceType) -> tuple[str, ...]:
        fields = {
            ImportSourceType.MONTHLY_SALES: ("period_start", "period_end"),
            ImportSourceType.SEASONALITY: ("valid_from", "valid_to"),
            ImportSourceType.GROWTH: ("valid_from", "valid_to"),
        }
        return fields.get(source, ())

    @staticmethod
    def _missing(value: object) -> bool:
        missing = pd.isna(value)
        return bool(missing) if not hasattr(missing, "__len__") else False

    @staticmethod
    def _is_forbidden_personal_header(name: str) -> bool:
        if name in FORBIDDEN_PERSONAL_HEADERS:
            return True
        direct_prefixes = ("фио_", "фамилия_", "телефон_", "email_", "e_mail_", "адрес_клиента")
        if name.startswith(direct_prefixes):
            return True
        return "клиент" in name and "id" not in name and "обезлич" not in name

    @staticmethod
    def _clean(value: object) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _decimal(value: object, name: str) -> Decimal:
        normalized = str(value).strip().replace(" ", "").replace(",", ".")
        result = Decimal(normalized)
        if not result.is_finite():
            raise ValueError(f"{name} must be finite")
        return result

    @staticmethod
    def _datetime(value: object, name: str) -> datetime:
        parsed = pd.to_datetime(value, errors="raise", dayfirst=True).to_pydatetime()
        if not isinstance(parsed, datetime):
            raise ValueError(f"{name} must be a datetime")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _date(value: object, name: str) -> date:
        parsed = pd.to_datetime(value, errors="raise", dayfirst=True)
        result = parsed.date()
        if not isinstance(result, date):
            raise ValueError(f"{name} must be a date")
        return result

    @staticmethod
    def _boolean(value: object) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "да", "истина"}:
            return True
        if normalized in {"0", "false", "no", "нет", "ложь"}:
            return False
        raise ValueError("boolean value is invalid")

    @staticmethod
    def _month_end(value: date) -> date:
        if value.month == 12:
            return date(value.year, 12, 31)
        return date(value.year, value.month + 1, 1) - timedelta(days=1)

    @staticmethod
    def _date_from_header(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip().lower().replace("ё", "е")
        match = re.search(r"(20\d{2})[-_/.](0?[1-9]|1[0-2])(?:[-_/.](0?[1-9]|[12]\d|3[01]))?", text)
        if match:
            year, month, day = match.groups()
            return date(int(year), int(month), int(day or 1))
        match = re.search(r"(0?[1-9]|[12]\d|3[01])[-_/.](0?[1-9]|1[0-2])[-_/.](20\d{2})", text)
        if match:
            day, month, year = match.groups()
            return date(int(year), int(month), int(day))
        months = {
            "янв": 1, "фев": 2, "мар": 3, "апр": 4,
            "май": 5, "июн": 6, "июл": 7, "авг": 8,
            "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
        }
        year_match = re.search(r"20\d{2}", text)
        if year_match:
            for prefix, month in months.items():
                if prefix in text:
                    return date(int(year_match.group()), month, 1)
        return None

    @staticmethod
    def _month_from_header(value: object) -> int | None:
        text = _header(value)
        if text.isdigit() and 1 <= int(text) <= 12:
            return int(text)
        names = {
            "январь": 1, "янв": 1, "january": 1, "jan": 1,
            "февраль": 2, "фев": 2, "february": 2, "feb": 2,
            "март": 3, "мар": 3, "march": 3, "mar": 3,
            "апрель": 4, "апр": 4, "april": 4, "apr": 4,
            "май": 5, "may": 5,
            "июнь": 6, "июн": 6, "june": 6, "jun": 6,
            "июль": 7, "июл": 7, "july": 7, "jul": 7,
            "август": 8, "авг": 8, "august": 8, "aug": 8,
            "сентябрь": 9, "сен": 9, "september": 9, "sep": 9,
            "октябрь": 10, "окт": 10, "october": 10, "oct": 10,
            "ноябрь": 11, "ноя": 11, "november": 11, "nov": 11,
            "декабрь": 12, "дек": 12, "december": 12, "dec": 12,
        }
        return names.get(text)
