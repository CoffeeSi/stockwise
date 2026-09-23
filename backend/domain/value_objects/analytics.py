from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Outlier:
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


@dataclass(frozen=True, slots=True)
class AbcXyzCell:
    abc: str
    xyz: str
    sku_count: int
    demand_share: Decimal
