from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.use_cases.get_run_analytics import AnalyticsUnavailableError, GetRunAnalytics
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke
from backend.infrastructure.api.schemas.analytics import (
    AbcXyzResponse, DemandSeriesResponse, OutlierPageResponse, RecommendationHistoryResponse,
)


router = APIRouter(tags=["analytics"], responses=ERROR_RESPONSES,
                   dependencies=[Depends(deps.get_current_user)])


def get_analytics(factory: UnitOfWorkFactory = Depends(deps.get_uow_factory)) -> GetRunAnalytics:
    return GetRunAnalytics(factory)


def read_analytics(operation, *args, **kwargs):
    try:
        return invoke(operation, *args, **kwargs)
    except AnalyticsUnavailableError:
        raise HTTPException(status_code=422, detail={
            "code": "analytics_unavailable",
            "message": "This calculation has no saved evidence for the requested analysis",
        }) from None


@router.get("/api/recommendations/{recommendation_id}/history", response_model=RecommendationHistoryResponse)
def recommendation_history(recommendation_id: UUID, months: int = Query(default=24, ge=1, le=24),
                           use_case: GetRunAnalytics = Depends(get_analytics)):
    return RecommendationHistoryResponse.model_validate(read_analytics(
        use_case.history, recommendation_id, months=months,
    ))


@router.get("/api/v1/analytics/outliers", response_model=OutlierPageResponse)
def outliers(calculation_run_id: UUID, supplier_id: UUID | None = None,
             product_id: UUID | None = None, warehouse_id: UUID | None = None,
             category_id: UUID | None = None,
             limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
             use_case: GetRunAnalytics = Depends(get_analytics)):
    return OutlierPageResponse.model_validate(read_analytics(
        use_case.outliers, calculation_run_id, supplier_id=supplier_id,
        product_id=product_id, warehouse_id=warehouse_id, category_id=category_id, limit=limit, offset=offset,
    ))


@router.get("/api/v1/analytics/demand-series", response_model=DemandSeriesResponse)
def demand_series(calculation_run_id: UUID, supplier_id: UUID | None = None,
                  product_id: UUID | None = None, warehouse_id: UUID | None = None,
                  category_id: UUID | None = None, months: int = Query(default=24, ge=1, le=24),
                  use_case: GetRunAnalytics = Depends(get_analytics)):
    return DemandSeriesResponse.model_validate(read_analytics(
        use_case.demand_series, calculation_run_id, supplier_id=supplier_id,
        product_id=product_id, warehouse_id=warehouse_id, category_id=category_id, months=months,
    ))


@router.get("/api/v1/analytics/abc-xyz", response_model=AbcXyzResponse)
def abc_xyz(calculation_run_id: UUID, supplier_id: UUID | None = None,
            warehouse_id: UUID | None = None, category_id: UUID | None = None,
            use_case: GetRunAnalytics = Depends(get_analytics)):
    return AbcXyzResponse.model_validate(read_analytics(
        use_case.abc_xyz, calculation_run_id, supplier_id=supplier_id,
        warehouse_id=warehouse_id, category_id=category_id,
    ))
