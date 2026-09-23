from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RecommendationDisplay:
    recommendation_id: UUID
    sku: str
    product_name: str
    unit: str
    supplier_name: str
    warehouse_name: str
    category_id: UUID | None
    category_name: str | None
