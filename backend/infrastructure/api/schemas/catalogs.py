from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    is_active: bool


class CategoryResponse(CatalogResponse):
    parent_id: UUID | None


class SupplierPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[CatalogResponse]
    total: int
    limit: int
    offset: int


class WarehouseListResponse(BaseModel):
    items: list[CatalogResponse]


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
