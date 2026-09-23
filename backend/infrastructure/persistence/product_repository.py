from uuid import UUID

from sqlalchemy import select

from backend.domain.entities.product import Product
from backend.domain.entities.catalog import Category
from backend.domain.repositories.filters import ALL, IdFilter
from backend.domain.repositories.product_repository import ProductRepository
from ._read_repository import SqlAlchemyReadRepository, id_filter
from .models.catalog import CategoryModel, ProductModel
from .catalog_search import filter_catalog


class SqlAlchemyProductRepository(SqlAlchemyReadRepository, ProductRepository):
    def list_categories(self, *, active_only: bool = True, search: str | None = None) -> list[Category]:
        query = filter_catalog(select(CategoryModel), CategoryModel,
                               active_only=active_only, search=search)
        return self._read(query.order_by(CategoryModel.name, CategoryModel.id), Category)

    def get_by_id(self, product_id: UUID) -> Product | None:
        rows = self._read(select(ProductModel).where(ProductModel.id == product_id), Product)
        return rows[0] if rows else None

    def get_by_sku(self, sku: str) -> Product | None:
        rows = self._read(select(ProductModel).where(ProductModel.sku == sku), Product)
        return rows[0] if rows else None

    def list_products(
        self, *, category_id: IdFilter = ALL, is_active: bool | None = True,
    ) -> list[Product]:
        query = select(ProductModel).where(id_filter(ProductModel.category_id, category_id))
        if is_active is not None:
            query = query.where(ProductModel.is_active == is_active)
        return self._read(query.order_by(ProductModel.sku, ProductModel.id), Product)
