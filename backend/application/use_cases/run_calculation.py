from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from backend.application.dto.calculation import RunCalculationCommand
from backend.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from backend.application.services.calculation_pipeline import CalculationPipeline
from backend.domain.entities.calculation_run import CalculationRun
from backend.domain.entities.enums import CalculationRunStatus
from backend.domain.value_objects.demand import DemandSource


class RunCalculation:
    def __init__(
        self, uow_factory: UnitOfWorkFactory,
        pipeline: CalculationPipeline | None = None,
        *, algorithm_version: str = "mvp-2",
    ) -> None:
        self._uow_factory = uow_factory
        self._pipeline = pipeline or CalculationPipeline()
        self._algorithm_version = algorithm_version

    def prepare(self, command: RunCalculationCommand, uow: UnitOfWork) -> CalculationRun:
        if not isinstance(command.demand_source, DemandSource):
            raise ValueError("demand_source must be explicit and supported")
        if type(command.horizon_days) is not int or command.horizon_days <= 0:
            raise ValueError("horizon_days must be positive")
        if command.warehouse_id is not None:
            warehouse = uow.warehouses.get_by_id(command.warehouse_id)
            if warehouse is None or not warehouse.is_active:
                raise LookupError("active warehouse was not found")
        if command.category_id is not None and not any(
            row.id == command.category_id for row in uow.products.list_categories(active_only=True)
        ):
            raise LookupError("active category was not found")
        run = CalculationRun(
            started_by=command.user_id,
            forecast_horizon_days=command.horizon_days,
            source_cutoff_at=datetime.now(timezone.utc),
            algorithm_version=self._algorithm_version,
            parameters={"horizon_days": command.horizon_days,
                        "demand_source": command.demand_source.value,
                        "warehouse_id": str(command.warehouse_id) if command.warehouse_id else None,
                        "category_id": str(command.category_id) if command.category_id else None,
                        "budget_limit": str(command.budget_limit) if command.budget_limit is not None else None,
                        "currency": command.currency,
                        **(self._pipeline.configuration() if isinstance(self._pipeline, CalculationPipeline) else {})},
            warehouse_id=command.warehouse_id,
            category_id=command.category_id,
        )
        for batch in uow.imports.list_completed():
            if batch.imported_at <= run.source_cutoff_at:
                run.attach_import(batch.id)
        products = uow.products.list_products(category_id=command.category_id) if command.category_id else uow.products.list_products()
        terms = {
            str(product.id): [{key: str(value) if isinstance(value, (UUID, Decimal)) else value
                               for key, value in asdict(item).items()}
                              for item in uow.suppliers.list_terms(product.id)]
            for product in products
        }
        run.parameters = {**run.parameters, "supplier_terms_snapshot": terms}
        return run

    def process(self, run_id: UUID, *, progress: Callable[[str, int, int], None] | None = None,
                finalize: Callable[[UnitOfWork, CalculationRun], None] | None = None) -> CalculationRun:
        with self._uow_factory() as uow:
            run = uow.calculation_runs.get(run_id)
            if run is None:
                raise LookupError("calculation run was not found")
            if run.status in {CalculationRunStatus.COMPLETED, CalculationRunStatus.FAILED}:
                if finalize is not None:
                    finalize(uow, run)
                    uow.commit()
                return run
            if not run.import_batch_ids:
                run.fail({"code": "missing_imports", "message": "no completed import batches available"})
                uow.calculation_runs.save(run)
                if finalize is not None:
                    finalize(uow, run)
                uow.commit()
                return run
            if run.status is CalculationRunStatus.PENDING:
                run.start()
                uow.calculation_runs.save(run)
                uow.commit()
        if progress is not None:
            progress("calculating", 0, 1)
        with self._uow_factory() as uow:
            results = self._pipeline.calculate(run, uow)
            if progress is not None:
                progress("persisting", 0, 1)
            uow.calculation_runs.add_results(results.forecasts, results.anomalies)
            uow.recommendations.add_many(results.recommendations)
            run.complete()
            uow.calculation_runs.save(run)
            if finalize is not None:
                finalize(uow, run)
            uow.commit()
        return run

    def execute(self, command: RunCalculationCommand) -> CalculationRun:
        """Synchronous adapter retained for application callers; HTTP dispatches a durable job."""
        with self._uow_factory() as uow:
            run = self.prepare(command, uow)
            uow.calculation_runs.add(run)
            uow.commit()
        try:
            return self.process(run.id)
        except Exception as error:
            try:
                with self._uow_factory() as uow:
                    persisted = uow.calculation_runs.get(run.id)
                    if persisted is None:
                        raise LookupError(f"calculation run {run.id} disappeared")
                    persisted.fail({"error_type": type(error).__name__, "message": str(error)})
                    uow.calculation_runs.save(persisted)
                    uow.commit()
            except Exception as persistence_error:
                error.add_note(
                    "Failed to persist calculation failure: "
                    f"{type(persistence_error).__name__}: {persistence_error}"
                )
            raise
