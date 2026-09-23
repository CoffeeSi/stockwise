from uuid import UUID

from fastapi import APIRouter, Depends, Query

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.use_cases.bulk_accept_recommendations import BulkAcceptRecommendations
from backend.application.use_cases.create_orders import CreateOrders
from backend.application.use_cases.list_orders import ListOrders
from backend.domain.entities.catalog import User
from backend.domain.entities.enums import PurchaseOrderStatus
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke
from backend.infrastructure.api.schemas.order_workflow import (
    AcceptRecommendationsRequest, AcceptRecommendationsResponse,
    BulkCreateOrdersRequest, BulkCreateOrdersResponse,
    OrderPageResponse, OrderSummaryResponse,
)
from backend.infrastructure.api.schemas.workflows import OrderResponse, RecommendationResponse

router = APIRouter(prefix="/api", tags=["order workflow"],
                   dependencies=[Depends(deps.get_current_user)], responses=ERROR_RESPONSES)


@router.post("/recommendations/bulk/accept", response_model=AcceptRecommendationsResponse)
def accept_selected(body: AcceptRecommendationsRequest, user: User = Depends(deps.require_writer),
                    factory: UnitOfWorkFactory = Depends(deps.get_uow_factory)):
    rows = invoke(BulkAcceptRecommendations(factory).execute, body.calculation_run_id,
                  items=[(item.recommendation_id, item.version) for item in body.items], user_id=user.id)
    return AcceptRecommendationsResponse(items=[RecommendationResponse.model_validate(row) for row in rows],
                                         accepted_count=len(rows))


@router.post("/orders/bulk", response_model=BulkCreateOrdersResponse, status_code=201)
def create_selected(body: BulkCreateOrdersRequest, user: User = Depends(deps.require_writer),
                    factory: UnitOfWorkFactory = Depends(deps.get_uow_factory)):
    orders = invoke(CreateOrders(factory).execute, body.calculation_run_id,
                    recommendation_ids=body.recommendation_ids, user_id=user.id)
    return BulkCreateOrdersResponse(
        orders=[OrderResponse.model_validate(order) for order in orders],
        consumed_recommendation_ids=[item.recommendation_id for order in orders for item in order.items],
    )


@router.get("/orders", response_model=OrderPageResponse)
def list_orders(calculation_run_id: UUID | None = None, supplier_id: UUID | None = None,
                status: PurchaseOrderStatus | None = None, limit: int = Query(50, ge=1, le=100),
                offset: int = Query(0, ge=0), factory: UnitOfWorkFactory = Depends(deps.get_uow_factory)):
    rows, total = invoke(ListOrders(factory).execute, calculation_run_id=calculation_run_id,
                         supplier_id=supplier_id, status=status, limit=limit, offset=offset)
    return OrderPageResponse(items=[OrderSummaryResponse.model_validate(row) for row in rows],
                             total=total, limit=limit, offset=offset)
