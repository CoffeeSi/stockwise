from fastapi import APIRouter, Depends

from backend.application.use_cases.preview_scenario import PreviewScenario, ScenarioAssumptions
from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke
from backend.infrastructure.api.schemas.scenarios import ScenarioPreviewRequest, ScenarioPreviewResponse


router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"], responses=ERROR_RESPONSES,
                   dependencies=[Depends(deps.get_current_user)])


@router.post("/preview", response_model=ScenarioPreviewResponse)
def preview(body: ScenarioPreviewRequest, factory: UnitOfWorkFactory = Depends(deps.get_uow_factory)):
    result = invoke(PreviewScenario(factory).execute, ScenarioAssumptions(**body.model_dump()))
    result["assumptions"] = body
    return ScenarioPreviewResponse.model_validate(result)
