from uuid import UUID

from fastapi import APIRouter, Depends

from backend.application.use_cases.adjust_recommendation import AdjustRecommendation
from backend.application.use_cases.accept_recommendation import AcceptRecommendation
from backend.application.use_cases.explain_recommendation import ExplainRecommendation
from backend.domain.entities.catalog import User
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke, require_result
from backend.infrastructure.api.schemas.workflows import (
    AcceptRecommendationRequest, AdjustRecommendationRequest, ExplanationResponse, RecommendationResponse,
)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"],
                   dependencies=[Depends(deps.get_current_user)], responses=ERROR_RESPONSES)


@router.get("/{recommendation_id}/explain", response_model=ExplanationResponse)
def explain(recommendation_id: UUID, use_case: ExplainRecommendation = Depends(deps.get_explain_recommendation)):
    return ExplanationResponse.model_validate(require_result(invoke(use_case.execute, recommendation_id)))


@router.patch("/{recommendation_id}", response_model=RecommendationResponse)
def adjust(recommendation_id: UUID, body: AdjustRecommendationRequest,
           user: User = Depends(deps.require_writer),
           use_case: AdjustRecommendation = Depends(deps.get_adjust_recommendation)):
    result = invoke(use_case.execute, recommendation_id, expected_version=body.version,
                    new_quantity=body.new_quantity, reason=body.reason, user_id=user.id)
    return RecommendationResponse.model_validate(result)


@router.post("/{recommendation_id}/accept", response_model=RecommendationResponse)
def accept(recommendation_id: UUID, body: AcceptRecommendationRequest,
           _user: User = Depends(deps.require_writer),
           use_case: AcceptRecommendation = Depends(deps.get_accept_recommendation)):
    result = invoke(use_case.execute, recommendation_id, expected_version=body.version, user_id=_user.id)
    return RecommendationResponse.model_validate(result)
