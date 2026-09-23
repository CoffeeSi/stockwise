from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.domain.entities.calculation_run import CalculationRun
from backend.domain.entities.enums import CalculationRunStatus
from backend.domain.entities.demand_forecast import DemandForecast
from backend.domain.entities.detected_anomaly import DetectedAnomaly
from backend.domain.value_objects.analytics import Outlier
from backend.infrastructure.persistence.models.calculation import (
    CalculationRunImportModel,
    CalculationRunModel,
    DemandForecastModel,
    DetectedAnomalyModel,
    RecommendationModel,
)
from backend.infrastructure.persistence.models.catalog import ProductModel
from backend.infrastructure.persistence.models.imports import SalesTransactionModel


def _aware(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def _json(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


class SqlAlchemyCalculationRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, run_id: UUID) -> CalculationRun | None:
        model = self._session.get(CalculationRunModel, run_id)
        if model is None:
            return None
        imports = self._session.scalars(
            select(CalculationRunImportModel.import_batch_id).where(
                CalculationRunImportModel.calculation_run_id == run_id
            )
        ).all()
        return self._run_entity(model, set(imports))

    def list_runs(
        self, *, status: CalculationRunStatus | None = None,
        warehouse_id: UUID | None = None, category_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[CalculationRun], int]:
        query = select(CalculationRunModel)
        if status is not None:
            query = query.where(CalculationRunModel.status == status)
        if warehouse_id is not None:
            query = query.where(CalculationRunModel.warehouse_id == warehouse_id)
        if category_id is not None:
            query = query.where(CalculationRunModel.category_id == category_id)
        total = self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        models = self._session.scalars(query.order_by(
            CalculationRunModel.started_at.desc(), CalculationRunModel.id.desc(),
        ).limit(limit).offset(offset)).all()
        imports = {model.id: set() for model in models}
        if models:
            rows = self._session.execute(select(
                CalculationRunImportModel.calculation_run_id, CalculationRunImportModel.import_batch_id,
            ).where(CalculationRunImportModel.calculation_run_id.in_(imports)))
            for run_id, batch_id in rows:
                imports[run_id].add(batch_id)
        return [self._run_entity(model, imports[model.id]) for model in models], total

    @staticmethod
    def _run_entity(model: CalculationRunModel, imports: set[UUID]) -> CalculationRun:
        return CalculationRun(
            id=model.id, started_by=model.started_by,
            forecast_horizon_days=model.forecast_horizon_days,
            source_cutoff_at=_aware(model.source_cutoff_at),
            algorithm_version=model.algorithm_version,
            parameters=dict(model.parameters), warehouse_id=model.warehouse_id,
            category_id=model.category_id, status=model.status,
            started_at=_aware(model.started_at), finished_at=_aware(model.finished_at),
            error_details=dict(model.error_details) if model.error_details else None,
            import_batch_ids=imports,
        )

    def add(self, run: CalculationRun) -> None:
        if self._session.get(CalculationRunModel, run.id) is not None:
            raise ValueError("calculation run already exists")
        self._session.add(CalculationRunModel(
            id=run.id, status=run.status, started_by=run.started_by,
            warehouse_id=run.warehouse_id, category_id=run.category_id,
            forecast_horizon_days=run.forecast_horizon_days,
            source_cutoff_at=run.source_cutoff_at, algorithm_version=run.algorithm_version,
            parameters=_json(dict(run.parameters)), started_at=run.started_at,
            finished_at=run.finished_at,
            error_details=_json(dict(run.error_details)) if run.error_details else None,
        ))
        self._session.flush()
        for batch_id in run.import_batch_ids:
            self._session.add(CalculationRunImportModel(
                calculation_run_id=run.id, import_batch_id=batch_id,
            ))
        self._session.flush()

    def save(self, run: CalculationRun) -> None:
        model = self._session.get(CalculationRunModel, run.id)
        if model is None:
            raise LookupError(f"calculation run {run.id} not found")
        model.status = run.status
        model.finished_at = run.finished_at
        model.parameters = _json(dict(run.parameters))
        model.error_details = _json(dict(run.error_details)) if run.error_details else None
        self._session.flush()

    def add_results(
        self, forecasts: list[DemandForecast], anomalies: list[DetectedAnomaly]
    ) -> None:
        for item in forecasts:
            self._session.add(DemandForecastModel(
                id=item.id, calculation_run_id=item.calculation_run_id,
                product_id=item.product_id, warehouse_id=item.warehouse_id,
                forecast_period_start=item.period_start, forecast_period_end=item.period_end,
                raw_demand=item.raw_demand, return_adjustment=item.return_adjustment,
                anomaly_adjustment=item.anomaly_adjustment,
                stockout_adjustment=item.stockout_adjustment,
                cleaned_baseline=item.cleaned_baseline, growth_rate=item.growth_rate,
                seasonality_index=item.seasonality_index,
                forecast_quantity=item.forecast_quantity, details=_json(dict(item.details)),
            ))
        for item in anomalies:
            self._session.add(DetectedAnomalyModel(
                id=item.id, calculation_run_id=item.calculation_run_id,
                sales_transaction_id=item.sales_transaction_id, method=item.method,
                original_quantity=item.original_quantity,
                replacement_quantity=item.replacement_quantity, threshold=item.threshold,
                reason=item.reason, details=_json(dict(item.details)),
            ))
        self._session.flush()

    def get_forecast(
        self, run_id: UUID, product_id: UUID, warehouse_id: UUID
    ) -> DemandForecast | None:
        model = self._session.scalar(select(DemandForecastModel).where(
            DemandForecastModel.calculation_run_id == run_id,
            DemandForecastModel.product_id == product_id,
            DemandForecastModel.warehouse_id == warehouse_id,
        ).order_by(DemandForecastModel.forecast_period_start.desc()).limit(1))
        if model is None:
            return None
        return self._forecast_entity(model)

    def list_forecasts(self, run_id: UUID) -> list[DemandForecast]:
        models = self._session.scalars(select(DemandForecastModel).where(
            DemandForecastModel.calculation_run_id == run_id,
        ).order_by(DemandForecastModel.product_id, DemandForecastModel.warehouse_id)).all()
        return [self._forecast_entity(model) for model in models]

    @staticmethod
    def _forecast_entity(model: DemandForecastModel) -> DemandForecast:
        return DemandForecast(
            id=model.id, calculation_run_id=model.calculation_run_id,
            product_id=model.product_id, warehouse_id=model.warehouse_id,
            period_start=model.forecast_period_start,
            period_end=model.forecast_period_end,
            raw_demand=model.raw_demand, return_adjustment=model.return_adjustment,
            anomaly_adjustment=model.anomaly_adjustment,
            stockout_adjustment=model.stockout_adjustment,
            cleaned_baseline=model.cleaned_baseline, growth_rate=model.growth_rate,
            seasonality_index=model.seasonality_index,
            forecast_quantity=model.forecast_quantity, details=dict(model.details),
        )

    def list_anomalies(
        self, run_id: UUID, product_id: UUID, warehouse_id: UUID
    ) -> list[DetectedAnomaly]:
        models = self._session.scalars(select(DetectedAnomalyModel).join(
            SalesTransactionModel,
            DetectedAnomalyModel.sales_transaction_id == SalesTransactionModel.id,
        ).where(
            DetectedAnomalyModel.calculation_run_id == run_id,
            SalesTransactionModel.product_id == product_id,
            SalesTransactionModel.warehouse_id == warehouse_id,
        ).order_by(DetectedAnomalyModel.id)).all()
        return [DetectedAnomaly(
            id=model.id, calculation_run_id=model.calculation_run_id,
            sales_transaction_id=model.sales_transaction_id, method=model.method,
            original_quantity=model.original_quantity,
            replacement_quantity=model.replacement_quantity,
            reason=model.reason, threshold=model.threshold,
            details=dict(model.details),
        ) for model in models]

    def list_outliers(
        self, run_id: UUID, *, supplier_id: UUID | None = None,
        product_id: UUID | None = None, warehouse_id: UUID | None = None,
        category_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[Outlier], int]:
        query = select(
            DetectedAnomalyModel, SalesTransactionModel.product_id, ProductModel.sku,
            SalesTransactionModel.warehouse_id, SalesTransactionModel.sold_at,
        ).select_from(DetectedAnomalyModel).join(
            SalesTransactionModel, DetectedAnomalyModel.sales_transaction_id == SalesTransactionModel.id,
        )
        query = query.join(ProductModel, SalesTransactionModel.product_id == ProductModel.id).where(
            DetectedAnomalyModel.calculation_run_id == run_id,
        )
        if supplier_id is not None:
            query = query.where(select(RecommendationModel.id).where(
                RecommendationModel.calculation_run_id == run_id,
                RecommendationModel.product_id == SalesTransactionModel.product_id,
                RecommendationModel.warehouse_id == SalesTransactionModel.warehouse_id,
                RecommendationModel.supplier_id == supplier_id,
            ).exists())
        if product_id is not None:
            query = query.where(SalesTransactionModel.product_id == product_id)
        if category_id is not None:
            query = query.where(select(DemandForecastModel.id).where(
                DemandForecastModel.calculation_run_id == run_id,
                DemandForecastModel.product_id == SalesTransactionModel.product_id,
                DemandForecastModel.warehouse_id == SalesTransactionModel.warehouse_id,
                DemandForecastModel.details["category_id"].as_string() == str(category_id),
            ).exists())
        if warehouse_id is not None:
            query = query.where(SalesTransactionModel.warehouse_id == warehouse_id)
        total = self._session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._session.execute(query.order_by(
            SalesTransactionModel.sold_at.desc(), DetectedAnomalyModel.id,
        ).limit(limit).offset(offset))
        items = [Outlier(
            id=anomaly.id, sales_transaction_id=anomaly.sales_transaction_id,
            product_id=product, sku=sku, warehouse_id=warehouse,
            occurred_at=_aware(occurred_at), method=anomaly.method,
            original_quantity=anomaly.original_quantity, replacement_quantity=anomaly.replacement_quantity,
            threshold=anomaly.threshold, reason=anomaly.reason,
        ) for anomaly, product, sku, warehouse, occurred_at in rows]
        return items, total
