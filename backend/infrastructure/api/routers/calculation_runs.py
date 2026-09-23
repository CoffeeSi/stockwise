from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from backend.application.dto.calculation import RunCalculationCommand
from backend.application.use_cases.run_calculation import RunCalculation
from backend.application.use_cases.get_calculation_run import GetCalculationRun
from backend.application.use_cases.get_demand_trends import GetDemandTrends
from backend.application.use_cases.list_recommendations import ListRecommendations, ListRecommendationsQuery
from backend.domain.entities.catalog import User
from backend.domain.entities.enums import CalculationRunStatus
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke, require_result
from backend.infrastructure.api.schemas.workflows import (
    CalculationRunResponse, DemandTrendPointResponse, RecommendationFilters,
    RecommendationPageResponse, RunCalculationRequest,
)

router = APIRouter(prefix="/api/calculation-runs", tags=["calculations"],
                   dependencies=[Depends(deps.get_audit_actor)], responses=ERROR_RESPONSES)


@router.post("", response_model=CalculationRunResponse, status_code=201)
def run_calculation(body: RunCalculationRequest, user: User = Depends(deps.get_audit_actor),
                    use_case: RunCalculation = Depends(deps.get_run_calculation)):
    result = invoke(use_case.execute, RunCalculationCommand(user_id=user.id, **body.model_dump()))
    response = CalculationRunResponse.model_validate(result)
    if result.status is CalculationRunStatus.FAILED:
        return JSONResponse(status_code=422, content=response.model_dump(mode="json"))
    return response


@router.get("/{run_id}", response_model=CalculationRunResponse)
def get_run(run_id: UUID, use_case: GetCalculationRun = Depends(deps.get_calculation_run)):
    return CalculationRunResponse.model_validate(require_result(invoke(use_case.execute, run_id)))


@router.get("/{run_id}/demand-trends", response_model=list[DemandTrendPointResponse])
def get_demand_trends(run_id: UUID, category_id: UUID | None = None,
                      warehouse_id: UUID | None = None,
                      use_case: GetDemandTrends = Depends(deps.get_demand_trends)):
    return [DemandTrendPointResponse.model_validate(row) for row in
            require_result(invoke(use_case.execute, run_id, category_id=category_id,
                                  warehouse_id=warehouse_id))]


@router.get("/{run_id}/recommendations", response_model=RecommendationPageResponse)
def list_recommendations(run_id: UUID, filters: Annotated[RecommendationFilters, Query()],
                         use_case: ListRecommendations = Depends(deps.get_list_recommendations)):
    result = invoke(use_case.execute, ListRecommendationsQuery(calculation_run_id=run_id, **filters.model_dump()))
    return RecommendationPageResponse.model_validate(result)
