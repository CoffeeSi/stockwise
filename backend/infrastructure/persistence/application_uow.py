from __future__ import annotations

from backend.infrastructure.persistence.calculation_run_repository import SqlAlchemyCalculationRunRepository
from backend.infrastructure.persistence.background_job_repository import SqlAlchemyBackgroundJobRepository
from backend.infrastructure.persistence.import_repository import SqlAlchemyImportRepository
from backend.infrastructure.persistence.inventory_repository import SqlAlchemyInventoryRepository
from backend.infrastructure.persistence.material_requirement_repository import SqlAlchemyMaterialRequirementRepository
from backend.infrastructure.persistence.order_repository import SqlAlchemyOrderRepository
from backend.infrastructure.persistence.product_repository import SqlAlchemyProductRepository
from backend.infrastructure.persistence.recommendation_repository import SqlAlchemyRecommendationRepository
from backend.infrastructure.persistence.sales_repository import SqlAlchemySalesRepository
from backend.infrastructure.persistence.seasonality_repository import SqlAlchemySeasonalityRepository
from backend.infrastructure.persistence.supplier_repository import SqlAlchemySupplierRepository
from backend.infrastructure.persistence.unit_of_work import RepositoryFactories, SqlAlchemyUnitOfWork
from backend.infrastructure.persistence.warehouse_repository import SqlAlchemyWarehouseRepository
from backend.infrastructure.persistence.database import Database


def create_application_uow_factory(database: Database):
    repositories = RepositoryFactories(
        jobs=SqlAlchemyBackgroundJobRepository,
        imports=SqlAlchemyImportRepository,
        sales=SqlAlchemySalesRepository,
        inventory=SqlAlchemyInventoryRepository,
        suppliers=SqlAlchemySupplierRepository,
        calculation_runs=SqlAlchemyCalculationRunRepository,
        recommendations=SqlAlchemyRecommendationRepository,
        orders=SqlAlchemyOrderRepository,
        products=SqlAlchemyProductRepository,
        warehouses=SqlAlchemyWarehouseRepository,
        seasonality=SqlAlchemySeasonalityRepository,
        material_requirements=SqlAlchemyMaterialRequirementRepository,
    )
    return lambda: SqlAlchemyUnitOfWork(database.session_factory, repositories)
