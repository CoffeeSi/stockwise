from typing import Protocol
from uuid import UUID

from backend.domain.entities.catalog import Supplier, SupplierProduct


class SupplierRepository(Protocol):
    def get_by_id(self, supplier_id: UUID) -> Supplier | None: ...

    def list_suppliers(
        self, *, active_only: bool = True, search: str | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[Supplier], int]: ...

    def list_terms(
        self, product_id: UUID, *, supplier_id: UUID | None = None, active_only: bool = True,
    ) -> list[SupplierProduct]:
        """All matching terms; active_only checks both terms and supplier.

        Does not choose a supplier based on price, priority or lead time.
        """
        ...
