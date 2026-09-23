from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.domain.entities.enums import PurchaseOrderStatus
from backend.domain.entities.purchase_order import OrderSummary


class ListOrders:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, *, calculation_run_id: UUID | None = None, supplier_id: UUID | None = None,
                status: PurchaseOrderStatus | None = None, limit: int = 50,
                offset: int = 0) -> tuple[list[OrderSummary], int]:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError("limit must be 1..100 and offset must be nonnegative")
        with self._uow_factory() as uow:
            return uow.orders.list_page(calculation_run_id=calculation_run_id,
                                       supplier_id=supplier_id, status=status, limit=limit, offset=offset)
