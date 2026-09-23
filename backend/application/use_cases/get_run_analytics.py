"""Read analytics from saved forecasts and the exact import set attached to a run."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Mapping
from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from backend.domain.entities.calculation_run import CalculationRun
from backend.domain.entities.demand_forecast import DemandForecast
from backend.domain.entities.enums import CalculationRunStatus
from backend.domain.errors import InvalidEntityStateError
from backend.domain.repositories.filters import AmbiguousSourceDataError
from backend.domain.services.abc_xyz import classify_demand
from backend.domain.value_objects.analytics import AbcXyzCell, Outlier
from backend.domain.value_objects.demand import DemandSource


class AnalyticsUnavailableError(RuntimeError):
    """The saved run predates the evidence required by the requested analysis."""


@dataclass(frozen=True, slots=True)
class HistoryPoint:
    month: str
    sales: Decimal
    stock: Decimal | None


@dataclass(frozen=True, slots=True)
class RecommendationHistory:
    recommendation_id: UUID
    run_id: UUID
    points: list[HistoryPoint]


@dataclass(frozen=True, slots=True)
class DemandSeriesPoint:
    month: str
    raw_sales: Decimal
    cleaned_demand: Decimal
    stock: Decimal | None


@dataclass(frozen=True, slots=True)
class DemandSeries:
    run_id: UUID
    points: list[DemandSeriesPoint]
    algorithm_version: str
    available_months: int


@dataclass(frozen=True, slots=True)
class AbcXyz:
    run_id: UUID
    cells: list[AbcXyzCell]
    algorithm_version: str
    metadata: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class OutlierPage:
    items: list[Outlier]
    total: int
    limit: int
    offset: int


def _month_start(index: int) -> date:
    return date(index // 12, index % 12 + 1, 1)


def _get_run(uow: UnitOfWork, run_id: UUID) -> CalculationRun:
    run = uow.calculation_runs.get(run_id)
    if run is None:
        raise LookupError("calculation run not found")
    if run.status is not CalculationRunStatus.COMPLETED:
        raise InvalidEntityStateError("Analytics require a completed calculation")
    return run


def _filtered_forecasts(uow: UnitOfWork, run_id: UUID, *, supplier_id: UUID | None,
                        warehouse_id: UUID | None, category_id: UUID | None,
                        product_id: UUID | None = None) -> list[DemandForecast]:
    supplier_pairs = None
    if supplier_id is not None:
        supplier_pairs = set()
        offset = 0
        while True:
            rows, total = uow.recommendations.list_for_run(
                run_id, supplier_id=supplier_id, limit=500, offset=offset,
            )
            supplier_pairs.update((row.product_id, row.warehouse_id) for row in rows)
            offset += len(rows)
            if not rows or offset >= total:
                break
    forecasts = []
    for item in uow.calculation_runs.list_forecasts(run_id):
        if product_id is not None and item.product_id != product_id:
            continue
        if warehouse_id is not None and item.warehouse_id != warehouse_id:
            continue
        if category_id is not None and item.details.get("category_id") != str(category_id):
            continue
        if supplier_pairs is not None and (item.product_id, item.warehouse_id) not in supplier_pairs:
            continue
        if "monthly_history" not in item.details:
            raise AnalyticsUnavailableError("Monthly demand was not saved for this calculation")
        forecasts.append(item)
    return forecasts


class GetRunAnalytics:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def history(self, recommendation_id: UUID, *, months: int = 24) -> RecommendationHistory:
        if not 1 <= months <= 24:
            raise ValueError("months must be 1..24")
        with self._uow_factory() as uow:
            item = uow.recommendations.get(recommendation_id)
            if item is None:
                raise LookupError("recommendation not found")
            run = _get_run(uow, item.calculation_run_id)
            cutoff = run.source_cutoff_at
            source = DemandSource(run.parameters["demand_source"])
            last_index = cutoff.year * 12 + cutoff.month - 1
            if source is DemandSource.MONTHLY_SALES:
                last_index -= 1
            first_index = last_index - months + 1
            start = _month_start(first_index)
            lower = datetime.combine(start, time.min, tzinfo=timezone.utc)
            end = min(cutoff.date(), _month_start(last_index + 1) - timedelta(days=1))
            sales: dict[str, Decimal] = {}
            if source is DemandSource.TRANSACTIONS:
                rows = uow.sales.list_transactions(
                    lower, cutoff, product_id=item.product_id, warehouse_id=item.warehouse_id,
                    import_batch_ids=run.import_batch_ids,
                )
                for row in rows:
                    month = row.sold_at.strftime("%Y-%m")
                    sales[month] = sales.get(month, Decimal("0")) + row.quantity
            else:
                rows = uow.sales.list_monthly_sales(
                    start, end, product_id=item.product_id, warehouse_id=item.warehouse_id,
                    import_batch_ids=run.import_batch_ids,
                )
                seen = set()
                for row in rows:
                    month = row.period_start.strftime("%Y-%m")
                    if (row.period_start.year, row.period_start.month) != (row.period_end.year, row.period_end.month):
                        raise AnalyticsUnavailableError("Source period cannot be assigned to one month")
                    if month in seen:
                        raise AmbiguousSourceDataError("Conflicting monthly sales observations")
                    seen.add(month)
                    sales[month] = row.quantity
            stock: dict[str, tuple[datetime, Decimal]] = {}
            for row in uow.inventory.list_snapshots(
                item.product_id, item.warehouse_id, started_at=lower, ended_at=cutoff,
                import_batch_ids=run.import_batch_ids,
            ):
                month = row.snapshot_at.strftime("%Y-%m")
                previous = stock.get(month)
                if previous is not None and previous[0] == row.snapshot_at and previous[1] != row.quantity_available:
                    raise AmbiguousSourceDataError("Conflicting monthly stock observations")
                if previous is None or row.snapshot_at >= previous[0]:
                    stock[month] = (row.snapshot_at, row.quantity_available)
            points = []
            for index in range(first_index, last_index + 1):
                month = _month_start(index).strftime("%Y-%m")
                # Months lacking both sources remain absent; no synthetic history is fabricated.
                if month not in sales and month not in stock:
                    continue
                if source is DemandSource.MONTHLY_SALES and month not in sales:
                    continue
                points.append(HistoryPoint(month, sales.get(month, Decimal("0")),
                                           stock[month][1] if month in stock else None))
            return RecommendationHistory(item.id, run.id, points)

    def outliers(self, run_id: UUID, *, supplier_id: UUID | None = None,
                 product_id: UUID | None = None, warehouse_id: UUID | None = None,
                 category_id: UUID | None = None,
                 limit: int = 50, offset: int = 0) -> OutlierPage:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("limit must be 1..100 and offset nonnegative")
        with self._uow_factory() as uow:
            _get_run(uow, run_id)
            rows, total = uow.calculation_runs.list_outliers(
                run_id, supplier_id=supplier_id, product_id=product_id,
                warehouse_id=warehouse_id, category_id=category_id, limit=limit, offset=offset,
            )
            return OutlierPage(rows, total, limit, offset)

    def demand_series(self, run_id: UUID, *, supplier_id: UUID | None = None,
                      warehouse_id: UUID | None = None, category_id: UUID | None = None,
                      product_id: UUID | None = None, months: int = 24) -> DemandSeries:
        if not 1 <= months <= 24:
            raise ValueError("months must be 1..24")
        with self._uow_factory() as uow:
            run = _get_run(uow, run_id)
            forecasts = _filtered_forecasts(uow, run_id, supplier_id=supplier_id,
                warehouse_id=warehouse_id, category_id=category_id, product_id=product_id)
            totals: dict[str, list[Decimal | None]] = {}
            for forecast in forecasts:
                for point in forecast.details["monthly_history"]:
                    month = point["period_start"][:7]
                    values = totals.setdefault(month, [Decimal("0"), Decimal("0"), Decimal("0")])
                    values[0] += Decimal(point["raw_demand"])
                    values[1] += Decimal(point["cleaned_demand"])
                    observed_stock = point.get("stock")
                    if values[2] is None or observed_stock is None:
                        values[2] = None
                    else:
                        values[2] += Decimal(observed_stock)
            available_months = len(totals)
            points = [DemandSeriesPoint(month, *totals[month]) for month in sorted(totals)[-months:]]
            return DemandSeries(run_id, points, run.algorithm_version, available_months)

    def abc_xyz(self, run_id: UUID, *, supplier_id: UUID | None = None,
                warehouse_id: UUID | None = None, category_id: UUID | None = None) -> AbcXyz:
        with self._uow_factory() as uow:
            run = _get_run(uow, run_id)
            policy = run.parameters.get("analytics_policy")
            if not isinstance(policy, Mapping):
                raise AnalyticsUnavailableError("ABC/XYZ policy was not saved for this calculation")
            forecasts = _filtered_forecasts(uow, run_id, supplier_id=supplier_id,
                warehouse_id=warehouse_id, category_id=category_id)
            series: dict[UUID, dict[str, Decimal]] = {}
            for forecast in forecasts:
                values = series.setdefault(forecast.product_id, {})
                for point in forecast.details["monthly_history"]:
                    month = point["period_start"][:7]
                    values[month] = values.get(month, Decimal("0")) + Decimal(point["cleaned_demand"])
            cells = classify_demand(series, policy)
            return AbcXyz(run_id, cells, run.algorithm_version, dict(policy))
