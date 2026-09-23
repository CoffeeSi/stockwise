from __future__ import annotations

import asyncio
import logging
from typing import Any

from openai import AsyncOpenAI
from fastapi import HTTPException

from backend.infrastructure.ai.cache import AiMemoryCache
from backend.infrastructure.ai.schemas import (
    SkuAnalysisRequest,
    SkuAnalysisResponse,
    SupplierLetterRequest,
    SupplierLetterResponse,
    SupplierSummaryRequest,
    SupplierSummaryResponse,
)
from backend.infrastructure.config.settings import Settings

logger = logging.getLogger("procurement.ai")


class AiProcurementService:
    """Service orchestrating OpenAI GPT-4o-mini with Structured Outputs."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: float = 15.0,
        cache_ttl: int = 300,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.cache = AiMemoryCache(maxsize=1000, ttl=cache_ttl)

        valid_key = api_key and api_key.strip() and not api_key.startswith("your-")
        if valid_key:
            self.client: AsyncOpenAI | None = AsyncOpenAI(api_key=api_key.strip())
        else:
            self.client = None
            logger.info("OpenAI API key not configured; AI endpoints are unavailable.")

    @staticmethod
    def _unavailable() -> HTTPException:
        return HTTPException(status_code=503, detail={"code": "ai_provider_unavailable", "message": "AI service unavailable"})

    async def analyze_sku(self, req: SkuAnalysisRequest) -> SkuAnalysisResponse:
        """Generate SKU explainability report for purchaser drawer."""
        cache_key = self.cache.hash_key("sku", req.model_dump())
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.client is None:
            raise self._unavailable()

        prompt = (
            "Ты — ведущий эксперт по закупкам ТОО «Электрокомплект». Проанализируй товарную позицию "
            "и сформируй четкое, профессиональное обоснование для менеджера по закупкам.\n\n"
            f"Товар: {req.item_name} (Артикул: {req.sku}, Код вендора: {req.vendor_code})\n"
            f"Категория: {req.category}, Поставщик: {req.supplier_name}\n"
            f"Текущий остаток: {req.current_stock:,.0f} {req.unit}\n"
            f"В пути: {req.in_transit:,.0f} {req.unit} ({req.transit_details or 'нет открытых накладных'})\n"
            f"Среднесуточный расход: {req.daily_demand:.1f} {req.unit}/день\n"
            f"Дней запаса: {req.days_of_stock if req.days_of_stock is not None else 'критический 0'}\n"
            f"Сезонный фактор на октябрь: {req.season_factor:.3f}\n"
            f"Кратность упаковки: {req.package_multiplicity:.0f} {req.unit}, MOQ: {req.moq:.0f}\n"
            f"Расчетная чистая потребность: {req.calculated_need:,.0f} {req.unit}\n"
            f"Скорректированная потребность: {req.adjusted_need:,.0f} {req.unit}\n"
            f"Статус срочности: {req.urgency}\n"
            f"Сумма закупки: {req.total_cost:,.0f} ₸\n"
            f"Отфильтрован оптовый выброс: {'Да' if req.has_whale_outlier else 'Нет'}\n"
            f"Компенсация stockout: {'Да' if req.stockout_recovered else 'Нет'}\n"
            f"Детерминированное обоснование алгоритма: {req.reasoning or '—'}\n\n"
            "Сформулируй краткое резюме, причину потребности/дефицита, риски и рекомендацию."
        )

        try:
            parsed = await asyncio.wait_for(
                self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Ты — Senior Procurement Analyst дистрибьютора ТОО «Электрокомплект». "
                                "Твоя цель — дать глубокое, реалистичное и емкое объяснение ситуации по позиции, "
                                "учитывая сезонность, кратность упаковок IEK и риски срыва поставок."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format=SkuAnalysisResponse,
                ),
                timeout=self.timeout,
            )
            choice = parsed.choices[0].message.parsed
            if choice is not None:
                choice.is_fallback = False
                self.cache.set(cache_key, choice)
                return choice
        except Exception as exc:
            logger.warning("OpenAI SKU analysis failed: %s", exc)
            raise self._unavailable() from exc
        raise self._unavailable()

    async def generate_supplier_summary(self, req: SupplierSummaryRequest) -> SupplierSummaryResponse:
        """Generate executive procurement summary for dashboard bento card."""
        cache_key = self.cache.hash_key("summary", req.model_dump())
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.client is None:
            raise self._unavailable()

        crit_preview = "\n".join(
            f"- {it.get('sku')}: {it.get('item_name')} — остаток на {it.get('days_of_stock', 0)} дн., потребность {it.get('calculated_need', 0)}"
            for it in req.top_critical_items[:5]
        )

        prompt = (
            "Сформируй Executive-сводку для директора по закупкам ТОО «Электрокомплект».\n\n"
            f"Поставщик: {req.supplier_name}\n"
            f"Целевой период: {req.season_name} (сезонный коэффициент: {req.season_factor:.3f}, рост спроса +{int((req.season_factor - 1) * 100)}%)\n"
            f"Всего позиций в пуле: {req.total_items}\n"
            f"Общий бюджет закупки: {req.total_budget:,.0f} ₸\n"
            f"Критических позиций (CRITICAL): {req.critical_count}\n"
            f"Плановых позиций (PLANNED / HIGH): {req.planned_count}\n"
            f"Позиций в норме (NORMAL): {req.normal_count}\n\n"
            f"Ключевые дефицитные артикулы:\n{crit_preview}\n\n"
            "Предоставь емкое резюме ситуации, анализ бюджета, перечень главных рисков и ключевые рекомендации."
        )

        try:
            parsed = await asyncio.wait_for(
                self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Ты — директор по логистике и закупкам крупного электротехнического дистрибьютора. "
                                "Пиши на профессиональном языке закупок, формулируя четкие выводы для топ-менеджмента."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format=SupplierSummaryResponse,
                ),
                timeout=self.timeout,
            )
            choice = parsed.choices[0].message.parsed
            if choice is not None:
                choice.is_fallback = False
                self.cache.set(cache_key, choice)
                return choice
        except Exception as exc:
            logger.warning("OpenAI supplier summary failed: %s", exc)
            raise self._unavailable() from exc
        raise self._unavailable()

    async def generate_supplier_letter(self, req: SupplierLetterRequest) -> SupplierLetterResponse:
        """Generate official reservation letter to supplier (IEK)."""
        cache_key = self.cache.hash_key("letter", req.model_dump())
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.client is None:
            raise self._unavailable()

        items_preview = "\n".join(
            f"- {it.get('sku')} | {it.get('item_name')} | {it.get('quantity')} {it.get('unit', 'шт')} | {it.get('total_cost', 0):,.0f} ₸"
            for it in req.items[:25]
        )

        prompt = (
            f"Составь официальное деловое письмо-заявку на резервирование и поставку продукции.\n\n"
            f"Заказчик: {req.company_name}\n"
            f"Поставщик: {req.supplier_name}\n"
            f"Желаемый срок поставки: {req.target_date or 'не указан'}\n"
            f"Условия отгрузки: {req.delivery_notes or 'не указаны'}\n\n"
            f"Спецификация позиций:\n{items_preview}\n\n"
            "Сформируй корректную тему письма, официального адресата, вежливое приветствие, "
            "деловое тело письма со ссылкой на партнерские отношения и договор, "
            "аккуратную таблицу позиций и официальную подпись."
        )

        try:
            parsed = await asyncio.wait_for(
                self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Ты — руководитель службы материально-технического снабжения ТОО «Электрокомплект». "
                                "Составляй строгое, юридически грамотное и уважительное деловое письмо поставщику электротехники."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format=SupplierLetterResponse,
                ),
                timeout=self.timeout,
            )
            choice = parsed.choices[0].message.parsed
            if choice is not None:
                choice.is_fallback = False
                self.cache.set(cache_key, choice)
                return choice
        except Exception as exc:
            logger.warning("OpenAI supplier letter failed: %s", exc)
            raise self._unavailable() from exc
        raise self._unavailable()


_ai_service_instance: AiProcurementService | None = None


def get_ai_service(settings: Settings | None = None) -> AiProcurementService:
    """Singleton getter for AiProcurementService."""
    global _ai_service_instance
    if _ai_service_instance is None:
        if settings is None:
            settings = Settings()
        _ai_service_instance = AiProcurementService(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout=settings.openai_timeout_seconds,
            cache_ttl=settings.ai_cache_ttl_seconds,
        )
    return _ai_service_instance
