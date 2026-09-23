from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from backend.infrastructure.api import dependencies as deps

from backend.infrastructure.ai.schemas import (
    SkuAnalysisRequest,
    SkuAnalysisResponse,
    SupplierLetterRequest,
    SupplierLetterResponse,
    SupplierSummaryRequest,
    SupplierSummaryResponse,
)
from backend.infrastructure.ai.service import AiProcurementService, get_ai_service
from backend.infrastructure.config.settings import Settings

router = APIRouter(prefix="/api/v1/ai", tags=["ai"],
                   dependencies=[Depends(deps.get_current_user)])


def get_service_dep(request: Request) -> AiProcurementService:
    settings = getattr(request.app.state, "settings", None)
    if settings is None:
        try:
            settings = Settings()
        except Exception:
            settings = None
    if settings is not None:
        return get_ai_service(settings)
    return AiProcurementService()


@router.post("/sku-analysis", response_model=SkuAnalysisResponse)
async def analyze_sku(
    request_data: SkuAnalysisRequest,
    service: AiProcurementService = Depends(get_service_dep),
) -> SkuAnalysisResponse:
    """Генерация глубокого, человекочитаемого обоснования по конкретной позиции (SKU Explainability)."""
    return await service.analyze_sku(request_data)


@router.post("/supplier-summary", response_model=SupplierSummaryResponse)
async def get_supplier_summary(
    request_data: SupplierSummaryRequest,
    service: AiProcurementService = Depends(get_service_dep),
) -> SupplierSummaryResponse:
    """Формирование Executive-сводки по поставщику (анализ рисков, бюджета и сезонного пика)."""
    return await service.generate_supplier_summary(request_data)


@router.post("/supplier-letter", response_model=SupplierLetterResponse)
async def get_supplier_letter(
    request_data: SupplierLetterRequest,
    service: AiProcurementService = Depends(get_service_dep),
) -> SupplierLetterResponse:
    """Составление официального делового письма поставщику (IEK) на бронирование/заказ товара."""
    return await service.generate_supplier_letter(request_data)
