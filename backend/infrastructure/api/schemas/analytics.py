from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HistoryPointResponse(ReadModel):
    month: str
    sales: Decimal
    stock: Decimal | None


class RecommendationHistoryResponse(ReadModel):
    recommendation_id: UUID
    run_id: UUID
    points: list[HistoryPointResponse]


class DemandSeriesPointResponse(ReadModel):
    month: str
    raw_sales: Decimal
    cleaned_demand: Decimal
    stock: Decimal | None


class DemandSeriesResponse(ReadModel):
    run_id: UUID
    points: list[DemandSeriesPointResponse]
    algorithm_version: str
    available_months: int


class AbcXyzCellResponse(ReadModel):
    abc: Literal["A", "B", "C"]
    xyz: Literal["X", "Y", "Z"]
    sku_count: int
    demand_share: Decimal


class AbcXyzMetadata(ReadModel):
    version: str
    abc_method: str
    abc_a_share: Decimal
    abc_b_share: Decimal
    xyz_method: str
    xyz_x_cv: Decimal
    xyz_y_cv: Decimal


class AbcXyzResponse(ReadModel):
    run_id: UUID
    cells: list[AbcXyzCellResponse]
    algorithm_version: str
    metadata: AbcXyzMetadata


class OutlierResponse(ReadModel):
    id: UUID
    sales_transaction_id: UUID
    product_id: UUID
    sku: str
    warehouse_id: UUID
    occurred_at: datetime
    method: str
    original_quantity: Decimal
    replacement_quantity: Decimal
    threshold: Decimal | None
    reason: str


class OutlierPageResponse(ReadModel):
    items: list[OutlierResponse]
    total: int
    limit: int
    offset: int
