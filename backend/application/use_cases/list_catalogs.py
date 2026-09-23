from dataclasses import dataclass

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.domain.entities.catalog import Category, Supplier, Warehouse


@dataclass(frozen=True, slots=True)
class SupplierPage:
    items: list[Supplier]
    total: int
    limit: int
    offset: int


class ListCatalogs:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def suppliers(self, *, active_only: bool = True, search: str | None = None,
                  limit: int = 50, offset: int = 0) -> SupplierPage:
        if not 1 <= limit <= 500 or offset < 0:
            raise ValueError("limit must be 1..500 and offset nonnegative")
        with self._uow_factory() as uow:
            items, total = uow.suppliers.list_suppliers(
                active_only=active_only, search=search, limit=limit, offset=offset,
            )
            return SupplierPage(items, total, limit, offset)

    def warehouses(self, *, active_only: bool = True, search: str | None = None) -> list[Warehouse]:
        with self._uow_factory() as uow:
            return uow.warehouses.list_warehouses(active_only=active_only, search=search)

    def categories(self, *, active_only: bool = True, search: str | None = None) -> list[Category]:
        with self._uow_factory() as uow:
            return uow.products.list_categories(active_only=active_only, search=search)
