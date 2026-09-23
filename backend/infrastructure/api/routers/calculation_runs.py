from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.exc import IntegrityError

from backend.application.dto.calculation import RunCalculationCommand
from backend.application.use_cases.dispatch_calculation import DispatchCalculation
from backend.application.use_cases.get_calculation_run import GetCalculationRun
from backend.application.use_cases.get_demand_trends import GetDemandTrends
from backend.application.use_cases.list_recommendations import ListRecommendations, ListRecommendationsQuery
from backend.application.use_cases.list_calculation_runs import ListCalculationRuns, ListCalculationRunsQuery
from backend.domain.entities.catalog import User
from backend.domain.entities.enums import CalculationRunStatus
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke, require_result
from backend.infrastructure.api.schemas.workflows import (
    CalculationRunPageResponse, CalculationRunResponse, DemandTrendPointResponse, RecommendationFilters,
    RecommendationPageResponse, RunCalculationRequest,
)

router = APIRouter(prefix="/api/calculation-runs", tags=["calculations"],
                   dependencies=[Depends(deps.get_current_user)], responses=ERROR_RESPONSES)


@router.post("", response_model=CalculationRunResponse, status_code=202)
def run_calculation(body: RunCalculationRequest, request: Request,
                    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
                    user: User = Depends(deps.require_writer)):
    use_case = DispatchCalculation(deps.get_uow_factory(request))
    command = RunCalculationCommand(user_id=user.id, **body.model_dump())
    try:
        result = invoke(use_case.execute, command, idempotency_key=idempotency_key)
    except IntegrityError:
        # Concurrent submissions with the same key race only at the unique job constraint.
        result = invoke(use_case.execute, command, idempotency_key=idempotency_key)
    request.app.state.background_worker.notify()
    response = CalculationRunResponse.model_validate(result)
    with deps.get_uow_factory(request)() as uow:
        job = uow.jobs.get_for_resource("calculation", result.id)
        if job is not None:
            response = CalculationRunResponse.model_validate({**response.model_dump(), "progress": job.progress})
    return response


@router.get("", response_model=CalculationRunPageResponse)
def list_runs(status: CalculationRunStatus | None = None, warehouse_id: UUID | None = None,
              category_id: UUID | None = None, limit: int = Query(default=50, ge=1, le=100),
              offset: int = Query(default=0, ge=0),
              use_case: ListCalculationRuns = Depends(deps.get_list_calculation_runs)):
    return CalculationRunPageResponse.model_validate(invoke(use_case.execute, ListCalculationRunsQuery(
        status=status, warehouse_id=warehouse_id, category_id=category_id, limit=limit, offset=offset,
    )))


@router.get("/{run_id}", response_model=CalculationRunResponse)
def get_run(run_id: UUID, request: Request, use_case: GetCalculationRun = Depends(deps.get_calculation_run)):
    response = CalculationRunResponse.model_validate(require_result(invoke(use_case.execute, run_id)))
    with deps.get_uow_factory(request)() as uow:
        job = uow.jobs.get_for_resource("calculation", run_id)
        if job is not None:
            response = CalculationRunResponse.model_validate({**response.model_dump(), "progress": job.progress})
    return response


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
