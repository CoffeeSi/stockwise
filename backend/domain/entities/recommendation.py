from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID, uuid4

from .enums import RecommendationStatus, Urgency
from backend.domain.value_objects.quantity import validate_quantity
from backend.domain.errors import InvalidEntityStateError


class RecommendationQuantityError(ValueError):
    """A submitted quantity violates the supplier terms saved with this run."""

    def __init__(self, recommendation_id: UUID, moq: Decimal, package_size: Decimal) -> None:
        self.recommendation_id = recommendation_id
        self.moq = moq
        self.package_size = package_size
        super().__init__("quantity must be zero or meet MOQ and package size")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must contain timezone information")


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationAdjustment:
    recommendation_id: UUID
    previous_quantity: Decimal
    new_quantity: Decimal
    reason: str
    changed_by: UUID
    changed_at: datetime = field(default_factory=utc_now)
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        validate_quantity(self.previous_quantity, "previous_quantity")
        validate_quantity(self.new_quantity, "new_quantity")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("adjustment reason must not be empty")
        if len(self.reason) > 2000:
            raise ValueError("adjustment reason must not exceed 2000 characters")
        if not isinstance(self.changed_by, UUID):
            raise ValueError("changed_by must be a user UUID")
        require_aware(self.changed_at, "changed_at")


@dataclass(slots=True, kw_only=True)
class Recommendation:
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
    id: UUID = field(default_factory=uuid4)
    status: RecommendationStatus = RecommendationStatus.SUGGESTED
    version: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        nonnegative_values = {
            "forecast_quantity": self.forecast_quantity,
            "current_stock": self.current_stock,
            "in_transit_quantity": self.in_transit_quantity,
            "material_requirement_quantity": self.material_requirement_quantity,
            "safety_stock": self.safety_stock,
            "shortage_quantity": self.shortage_quantity,
            "quantity_before_rounding": self.quantity_before_rounding,
            "recommended_quantity": self.recommended_quantity,
            "effective_quantity": self.effective_quantity,
        }
        for name, value in nonnegative_values.items():
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.moq <= 0:
            raise ValueError("moq must be positive")
        if self.package_size <= 0:
            raise ValueError("package_size must be positive")
        if not Decimal("0") <= self.risk_score <= Decimal("1"):
            raise ValueError("risk_score must be between 0 and 1")
        if not self.explanation.strip():
            raise ValueError("explanation must not be empty")
        if self.version <= 0:
            raise ValueError("version must be positive")
        require_aware(self.created_at, "created_at")
        require_aware(self.updated_at, "updated_at")

    def adjust(
        self,
        new_quantity: Decimal,
        *,
        reason: str,
        changed_by: UUID,
        changed_at: datetime | None = None,
    ) -> RecommendationAdjustment:
        if self.status in {
            RecommendationStatus.REJECTED,
            RecommendationStatus.CONVERTED_TO_ORDER,
        }:
            raise InvalidEntityStateError("closed recommendation cannot be adjusted")
        self.validate_order_quantity(new_quantity, allow_zero=True)
        adjustment = RecommendationAdjustment(
            recommendation_id=self.id,
            previous_quantity=self.effective_quantity,
            new_quantity=new_quantity,
            reason=reason,
            changed_by=changed_by,
            changed_at=changed_at or utc_now(),
        )
        self.effective_quantity = new_quantity
        self.status = RecommendationStatus.ADJUSTED
        self.version += 1
        self.updated_at = adjustment.changed_at
        return adjustment

    def validate_order_quantity(self, quantity: Decimal, *, allow_zero: bool = False) -> None:
        validate_quantity(quantity, "quantity", positive=not allow_zero)
        if quantity == 0 and allow_zero:
            return
        if quantity < self.moq or quantity % self.package_size != 0:
            raise RecommendationQuantityError(self.id, self.moq, self.package_size)

    def accept(self, *, changed_by: UUID, changed_at: datetime | None = None) -> None:
        if self.status not in {RecommendationStatus.SUGGESTED, RecommendationStatus.ADJUSTED}:
            raise InvalidEntityStateError("only a suggested or adjusted recommendation can be accepted")
        if not isinstance(changed_by, UUID):
            raise ValueError("changed_by must be a user UUID")
        self.validate_order_quantity(self.effective_quantity)
        change_time = changed_at or utc_now()
        require_aware(change_time, "changed_at")
        details = dict(self.calculation_details)
        history = details.get("acceptance_history", [])
        if not isinstance(history, list):
            raise ValueError("invalid persisted acceptance history")
        details["acceptance_history"] = [*history, {
            "accepted_by": str(changed_by),
            "accepted_at": change_time.isoformat(),
            "version": self.version + 1,
            "quantity": str(self.effective_quantity),
        }]
        self.calculation_details = details
        self.status = RecommendationStatus.ACCEPTED
        self.version += 1
        self.updated_at = change_time

    def reject(self, *, changed_at: datetime | None = None) -> None:
        if self.status is RecommendationStatus.CONVERTED_TO_ORDER:
            raise ValueError("converted recommendation cannot be rejected")
        change_time = changed_at or utc_now()
        require_aware(change_time, "changed_at")
        self.status = RecommendationStatus.REJECTED
        self.version += 1
        self.updated_at = change_time

    def mark_converted_to_order(self, *, changed_at: datetime | None = None) -> None:
        if self.status is not RecommendationStatus.ACCEPTED:
            raise ValueError("only an accepted recommendation can be converted to an order")
        self.validate_order_quantity(self.effective_quantity)
        change_time = changed_at or utc_now()
        require_aware(change_time, "changed_at")
        self.status = RecommendationStatus.CONVERTED_TO_ORDER
        self.version += 1
        self.updated_at = change_time
