from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from .enums import PurchaseOrderStatus
from backend.domain.value_objects.quantity import validate_quantity
from backend.domain.errors import InvalidEntityStateError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True, kw_only=True)
class PurchaseOrderItem:
    recommendation_id: UUID
    product_id: UUID
    recommended_quantity: Decimal
    approved_quantity: Decimal
    unit_price: Decimal | None = None
    total_amount: Decimal | None = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        validate_quantity(self.recommended_quantity, "recommended_quantity")
        validate_quantity(self.approved_quantity, "approved_quantity", positive=True)
        if self.unit_price is not None:
            validate_quantity(self.unit_price, "unit_price")
        if self.total_amount is not None:
            validate_quantity(self.total_amount, "total_amount")


@dataclass(slots=True, kw_only=True)
class PurchaseOrder:
    order_number: str
    supplier_id: UUID
    warehouse_id: UUID
    created_from_run_id: UUID
    created_by: UUID
    id: UUID = field(default_factory=uuid4)
    status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT
    created_at: datetime = field(default_factory=utc_now)
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    exported_at: datetime | None = None
    items: list[PurchaseOrderItem] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.order_number.strip():
            raise ValueError("order_number must not be empty")
        self._require_aware(self.created_at, "created_at")
        if self.approved_at is not None:
            self._require_aware(self.approved_at, "approved_at")
        if self.exported_at is not None:
            self._require_aware(self.exported_at, "exported_at")
        if self.status in {PurchaseOrderStatus.APPROVED, PurchaseOrderStatus.EXPORTED}:
            if self.approved_by is None or self.approved_at is None:
                raise ValueError("approved order must contain approval audit")

    @staticmethod
    def _require_aware(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must contain timezone information")

    def add_item(self, item: PurchaseOrderItem) -> None:
        if self.status is not PurchaseOrderStatus.DRAFT:
            raise ValueError("items can only be added to a draft order")
        if any(existing.recommendation_id == item.recommendation_id for existing in self.items):
            raise ValueError("recommendation is already included in the order")
        self.items.append(item)

    def approve(self, *, approved_by: UUID, approved_at: datetime | None = None) -> None:
        if self.status is not PurchaseOrderStatus.DRAFT:
            raise InvalidEntityStateError("only a draft order can be approved")
        if not self.items:
            raise InvalidEntityStateError("empty order cannot be approved")
        for item in self.items:
            validate_quantity(item.approved_quantity, "approved_quantity", positive=True)
        if not isinstance(approved_by, UUID):
            raise ValueError("approved_by must be a user UUID")
        approval_time = approved_at or utc_now()
        self._require_aware(approval_time, "approved_at")
        if approval_time < self.created_at:
            raise ValueError("approved_at cannot be earlier than created_at")
        self.status = PurchaseOrderStatus.APPROVED
        self.approved_by = approved_by
        self.approved_at = approval_time

    def mark_exported(self, *, exported_at: datetime | None = None) -> None:
        if self.status is not PurchaseOrderStatus.APPROVED:
            raise InvalidEntityStateError("only an approved order can be exported")
        export_time = exported_at or utc_now()
        self._require_aware(export_time, "exported_at")
        if self.approved_at is not None and export_time < self.approved_at:
            raise ValueError("exported_at cannot be earlier than approved_at")
        self.status = PurchaseOrderStatus.EXPORTED
        self.exported_at = export_time

    def cancel(self) -> None:
        if self.status is PurchaseOrderStatus.EXPORTED:
            raise ValueError("exported order cannot be cancelled")
        if self.status is PurchaseOrderStatus.CANCELLED:
            raise ValueError("order is already cancelled")
        self.status = PurchaseOrderStatus.CANCELLED


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderSummary:
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
