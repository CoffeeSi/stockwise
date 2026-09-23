from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from backend.domain.entities.enums import RecommendationStatus, Urgency
from backend.domain.entities.recommendation import Recommendation
from backend.domain.value_objects.recommendation_display import RecommendationDisplay


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcurementRecommendationRow:
    id: UUID
    calculation_run_id: UUID
    product_id: UUID
    warehouse_id: UUID
    supplier_id: UUID
    forecast_quantity: Decimal
    current_stock: Decimal
    in_transit_quantity: Decimal
    material_requirement_quantity: Decimal
    safety_stock: Decimal
    shortage_quantity: Decimal
    quantity_before_rounding: Decimal
    moq: Decimal
    package_size: Decimal
    recommended_quantity: Decimal
    effective_quantity: Decimal
    risk_score: Decimal
    urgency: Urgency
    explanation: str
    calculation_details: Mapping[str, Any]
    status: RecommendationStatus
    version: int
    created_at: datetime
    updated_at: datetime
    sku: str
    product_name: str
    unit: str
    supplier_name: str
    warehouse_name: str
    category_id: UUID | None
    category_name: str | None
    unit_price: Decimal | None
    currency: str | None
    estimated_total: Decimal | None

    @classmethod
    def from_recommendation(cls, item: Recommendation, display: RecommendationDisplay):
        snapshot = item.calculation_details.get("supplier_terms_snapshot")
        price: Decimal | None = None
        currency: str | None = None
        if isinstance(snapshot, Mapping):
            raw_price = snapshot.get("unit_price")
            if raw_price is not None:
                price = Decimal(str(raw_price))
                if not price.is_finite() or price < 0:
                    raise ValueError("Invalid saved supplier price")
            raw_currency = snapshot.get("currency")
            if isinstance(raw_currency, str) and raw_currency.strip():
                currency = raw_currency
        return cls(
            **{field.name: getattr(item, field.name) for field in fields(Recommendation)},
            sku=display.sku, product_name=display.product_name, unit=display.unit,
            supplier_name=display.supplier_name, warehouse_name=display.warehouse_name,
            category_id=display.category_id, category_name=display.category_name,
            unit_price=price, currency=currency,
            estimated_total=price * item.effective_quantity if price is not None else None,
        )
