from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from backend.domain.entities.enums import PurchaseOrderStatus
from backend.infrastructure.api.schemas.workflows import (
    OrderResponse, ReadModel, RecommendationResponse, RequestModel,
)


class AcceptSelectionItem(RequestModel):
    recommendation_id: UUID
    version: int = Field(gt=0, strict=True)


class AcceptRecommendationsRequest(RequestModel):
    calculation_run_id: UUID
    items: list[AcceptSelectionItem] = Field(min_length=1, max_length=500)

    @field_validator("items")
    @classmethod
    def unique_ids(cls, values: list[AcceptSelectionItem]) -> list[AcceptSelectionItem]:
        if len({value.recommendation_id for value in values}) != len(values):
            raise ValueError("recommendation IDs must be unique")
        return values


class AcceptRecommendationsResponse(ReadModel):
    items: list[RecommendationResponse]
    accepted_count: int


class BulkCreateOrdersRequest(RequestModel):
    calculation_run_id: UUID
    recommendation_ids: list[UUID] = Field(min_length=1, max_length=500)

    @field_validator("recommendation_ids")
    @classmethod
    def unique_ids(cls, values: list[UUID]) -> list[UUID]:
        if len(set(values)) != len(values):
            raise ValueError("recommendation IDs must be unique")
        return values


class BulkCreateOrdersResponse(ReadModel):
    orders: list[OrderResponse]
    consumed_recommendation_ids: list[UUID]


class OrderSummaryResponse(ReadModel):
    id: UUID
    order_number: str
    supplier_id: UUID
    supplier_name: str
    warehouse_id: UUID
    warehouse_name: str
    created_from_run_id: UUID
    status: PurchaseOrderStatus
    created_at: datetime
    approved_at: datetime | None
    item_count: int
    total_amount: Decimal | None
    currency: str | None


class OrderPageResponse(ReadModel):
    items: list[OrderSummaryResponse]
    total: int
    limit: int
    offset: int
