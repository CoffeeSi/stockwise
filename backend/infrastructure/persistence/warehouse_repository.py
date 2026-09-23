from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.domain.entities.catalog import Warehouse
from backend.infrastructure.persistence.models.catalog import WarehouseModel
from ._read_repository import to_entity
from .catalog_search import filter_catalog


class SqlAlchemyWarehouseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_warehouses(self, *, active_only: bool = True, search: str | None = None) -> list[Warehouse]:
        query = filter_catalog(select(WarehouseModel), WarehouseModel,
                               active_only=active_only, search=search)
        rows = self._session.scalars(query.order_by(WarehouseModel.name, WarehouseModel.id))
        return [to_entity(row, Warehouse) for row in rows]

    def list_active_ids(self) -> list[UUID]:
        return list(
            self._session.scalars(
                select(WarehouseModel.id)
                .where(WarehouseModel.is_active.is_(True))
                .order_by(WarehouseModel.id)
            )
        )

    def get_by_id(self, warehouse_id: UUID) -> Warehouse | None:
        model = self._session.get(WarehouseModel, warehouse_id)
        return to_entity(model, Warehouse) if model is not None else None
