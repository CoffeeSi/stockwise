from typing import Protocol
from uuid import UUID

from backend.domain.entities.catalog import Warehouse


class WarehouseRepository(Protocol):
    def list_active_ids(self) -> list[UUID]: ...

    def get_by_id(self, warehouse_id: UUID) -> Warehouse | None: ...

    def list_warehouses(self, *, active_only: bool = True, search: str | None = None) -> list[Warehouse]: ...
