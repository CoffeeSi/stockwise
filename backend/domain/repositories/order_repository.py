from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from backend.domain.entities.enums import PurchaseOrderStatus
from backend.domain.entities.order_export import OrderExport
from backend.domain.entities.purchase_order import OrderSummary, PurchaseOrder


class OrderRepositoryError(RuntimeError):
    pass


class OrderNotFoundError(OrderRepositoryError):
    def __init__(self, order_id: UUID) -> None:
        self.order_id = order_id
        super().__init__(f"purchase order {order_id} was not found")


class DuplicateOrderNumberError(OrderRepositoryError):
    def __init__(self, order_number: str) -> None:
        self.order_number = order_number
        super().__init__(f"purchase order number {order_number!r} already exists")


class RecommendationAlreadyOrderedError(OrderRepositoryError):
    def __init__(self, recommendation_id: UUID) -> None:
        self.recommendation_id = recommendation_id
        super().__init__(f"recommendation {recommendation_id} is already in an order")


class InvalidOrderPersistenceStateError(OrderRepositoryError):
    pass


class OrderConflictError(InvalidOrderPersistenceStateError):
    """The persisted status/audit changed during this operation."""


class OrderRepository(Protocol):
    """Persistence port for purchase orders and their export audit."""

    def get(self, order_id: UUID) -> PurchaseOrder | None: ...

    def get_by_number(self, order_number: str) -> PurchaseOrder | None: ...

    def list_page(self, *, calculation_run_id: UUID | None = None, supplier_id: UUID | None = None,
                  status: PurchaseOrderStatus | None = None, limit: int = 50,
                  offset: int = 0) -> tuple[list[OrderSummary], int]: ...

    def list_by_supplier(
        self,
        supplier_id: UUID,
        *,
        status: PurchaseOrderStatus | None = None,
    ) -> Sequence[PurchaseOrder]: ...

    def add(self, order: PurchaseOrder) -> PurchaseOrder: ...

    def save(self, order: PurchaseOrder, *, expected_status: PurchaseOrderStatus | None = None) -> PurchaseOrder:
        """Conditionally update status; do not overwrite existing approval audit."""
        ...

    def add_export(self, export: OrderExport) -> OrderExport: ...

    def list_exports(self, order_id: UUID) -> Sequence[OrderExport]: ...
