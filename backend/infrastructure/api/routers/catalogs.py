from fastapi import APIRouter, Depends, Query

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.use_cases.list_catalogs import ListCatalogs
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke
from backend.infrastructure.api.schemas.catalogs import (
    CatalogResponse, CategoryListResponse, CategoryResponse,
    SupplierPageResponse, WarehouseListResponse,
)


router = APIRouter(prefix="/api/v1", tags=["catalogs"], responses=ERROR_RESPONSES,
                   dependencies=[Depends(deps.get_current_user)])


def get_catalogs(factory: UnitOfWorkFactory = Depends(deps.get_uow_factory)) -> ListCatalogs:
    return ListCatalogs(factory)


@router.get("/suppliers", response_model=SupplierPageResponse)
def list_suppliers(active_only: bool = True, search: str | None = Query(default=None, max_length=200),
                   limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                   use_case: ListCatalogs = Depends(get_catalogs)):
    return SupplierPageResponse.model_validate(invoke(
        use_case.suppliers, active_only=active_only, search=search, limit=limit, offset=offset,
    ))


@router.get("/warehouses", response_model=WarehouseListResponse)
def list_warehouses(active_only: bool = True, search: str | None = Query(default=None, max_length=200),
                    use_case: ListCatalogs = Depends(get_catalogs)):
    rows = invoke(use_case.warehouses, active_only=active_only, search=search)
    return WarehouseListResponse(items=[CatalogResponse.model_validate(row) for row in rows])


@router.get("/categories", response_model=CategoryListResponse)
def list_categories(active_only: bool = True, search: str | None = Query(default=None, max_length=200),
                    use_case: ListCatalogs = Depends(get_catalogs)):
    rows = invoke(use_case.categories, active_only=active_only, search=search)
    return CategoryListResponse(items=[CategoryResponse.model_validate(row) for row in rows])
