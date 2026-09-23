from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import cast

from sqlalchemy.orm import Session, sessionmaker

from backend.application.ports.unit_of_work import Repository
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


RepositoryFactory = Callable[[Session], Repository]


@dataclass(frozen=True, slots=True)
class RepositoryFactories:
    imports: Callable[[Session], ImportRepository]
    sales: RepositoryFactory
    inventory: Callable[[Session], InventoryRepository]
    suppliers: RepositoryFactory
    calculation_runs: Callable[[Session], CalculationRunRepository]
    recommendations: Callable[[Session], RecommendationRepository]
    orders: Callable[[Session], OrderRepository]
    products: RepositoryFactory | None = None
    seasonality: RepositoryFactory | None = None
    material_requirements: RepositoryFactory | None = None
    warehouses: Callable[[Session], WarehouseRepository] | None = None
    jobs: Callable[[Session], BackgroundJobRepository] | None = None

    def as_dict(self) -> dict[str, RepositoryFactory]:
        factories = {
            "imports": self.imports,
            "sales": self.sales,
            "inventory": self.inventory,
            "suppliers": self.suppliers,
            "calculation_runs": self.calculation_runs,
            "recommendations": self.recommendations,
            "orders": self.orders,
        }
        for name in ("products", "seasonality", "material_requirements", "warehouses", "jobs"):
            factory = getattr(self, name)
            if factory is not None:
                factories[name] = factory
        return factories


class SqlAlchemyUnitOfWork:
    """One explicit transaction shared by all repositories in a use case."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        repository_factories: RepositoryFactories,
    ) -> None:
        self._session_factory = session_factory
        self._repository_factories = repository_factories
        self._session: Session | None = None
        self._repositories: dict[str, Repository] = {}

    @property
    def jobs(self) -> BackgroundJobRepository:
        return cast(BackgroundJobRepository, self._repository("jobs"))

    @property
    def imports(self) -> ImportRepository:
        return cast(ImportRepository, self._repository("imports"))

    @property
    def sales(self) -> SalesRepository:
        return cast(SalesRepository, self._repository("sales"))

    @property
    def inventory(self) -> InventoryRepository:
        return cast(InventoryRepository, self._repository("inventory"))

    @property
    def suppliers(self) -> SupplierRepository:
        return cast(SupplierRepository, self._repository("suppliers"))

    @property
    def products(self) -> ProductRepository:
        return cast(ProductRepository, self._repository("products"))

    @property
    def warehouses(self) -> WarehouseRepository:
        return cast(WarehouseRepository, self._repository("warehouses"))

    @property
    def seasonality(self) -> SeasonalityRepository:
        return cast(SeasonalityRepository, self._repository("seasonality"))

    @property
    def material_requirements(self) -> MaterialRequirementRepository:
        return cast(MaterialRequirementRepository, self._repository("material_requirements"))

    @property
    def calculation_runs(self) -> CalculationRunRepository:
        return cast(CalculationRunRepository, self._repository("calculation_runs"))

    @property
    def recommendations(self) -> RecommendationRepository:
        return cast(RecommendationRepository, self._repository("recommendations"))

    @property
    def orders(self) -> OrderRepository:
        return cast(OrderRepository, self._repository("orders"))

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        if self._session is not None:
            raise RuntimeError("unit of work is already active")

        session = self._session_factory()
        try:
            repositories = {
                name: factory(session)
                for name, factory in self._repository_factories.as_dict().items()
            }
        except BaseException:
            session.close()
            raise

        self._session = session
        self._repositories = repositories
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            session.rollback()
        finally:
            session.close()
            self._repositories = {}
            self._session = None

    def commit(self) -> None:
        session = self._active_session()
        try:
            session.commit()
        except BaseException:
            session.rollback()
            raise

    def rollback(self) -> None:
        self._active_session().rollback()

    def _active_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("unit of work must be used inside a with block")
        return self._session

    def _repository(self, name: str) -> Repository:
        self._active_session()
        try:
            return cast(Repository, self._repositories[name])
        except KeyError:
            raise RuntimeError(f"repository {name!r} is not configured") from None
