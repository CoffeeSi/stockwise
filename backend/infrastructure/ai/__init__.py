"""AI integration using OpenAI API with Structured Outputs and caching."""

from backend.infrastructure.ai.schemas import (
    SkuAnalysisRequest,
    SkuAnalysisResponse,
    SupplierLetterRequest,
    SupplierLetterResponse,
    SupplierSummaryRequest,
    SupplierSummaryResponse,
)
from backend.infrastructure.ai.service import AiProcurementService, get_ai_service

__all__ = [
    "AiProcurementService",
    "SkuAnalysisRequest",
    "SkuAnalysisResponse",
    "SupplierLetterRequest",
    "SupplierLetterResponse",
    "SupplierSummaryRequest",
    "SupplierSummaryResponse",
    "get_ai_service",
]
