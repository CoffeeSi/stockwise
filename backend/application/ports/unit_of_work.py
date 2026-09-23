from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from backend.domain.repositories.import_repository import ImportRepository
from backend.domain.repositories.background_job_repository import BackgroundJobRepository
from backend.domain.repositories.calculation_run_repository import CalculationRunRepository
from backend.domain.repositories.inventory_repository import InventoryRepository
from backend.domain.repositories.material_requirement_repository import MaterialRequirementRepository
from backend.domain.repositories.product_repository import ProductRepository
from backend.domain.repositories.sales_repository import SalesRepository
from backend.domain.repositories.seasonality_repository import SeasonalityRepository
from backend.domain.repositories.supplier_repository import SupplierRepository
from backend.domain.repositories.order_repository import OrderRepository
from backend.domain.repositories.recommendation_repository import RecommendationRepository
from backend.domain.repositories.warehouse_repository import WarehouseRepository


class Repository(Protocol):
    """Marker port refined by repository-specific protocols in REP tasks."""


class UnitOfWork(Protocol):
    """Application transaction boundary; contains no SQLAlchemy dependency."""

    @property
    def jobs(self) -> BackgroundJobRepository: ...

    @property
    def imports(self) -> ImportRepository: ...

    @property
    def sales(self) -> SalesRepository: ...

    @property
    def inventory(self) -> InventoryRepository: ...

    @property
    def suppliers(self) -> SupplierRepository: ...

    @property
    def products(self) -> ProductRepository: ...

    @property
    def warehouses(self) -> WarehouseRepository: ...

    @property
    def seasonality(self) -> SeasonalityRepository: ...

    @property
    def material_requirements(self) -> MaterialRequirementRepository: ...

    @property
    def calculation_runs(self) -> CalculationRunRepository: ...

    @property
    def recommendations(self) -> RecommendationRepository: ...

    @property
    def orders(self) -> OrderRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


UnitOfWorkFactory = Callable[[], UnitOfWork]
