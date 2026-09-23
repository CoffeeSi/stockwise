"""Orchestrate saved facts through the domain demand preparation pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWork
from backend.domain.entities.calculation_run import CalculationRun
from backend.domain.entities.catalog import SupplierProduct
from backend.domain.entities.demand_forecast import DemandForecast
from backend.domain.entities.detected_anomaly import DetectedAnomaly
from backend.domain.entities.recommendation import Recommendation
from backend.domain.enums import GrowthSource, TransactionType
from backend.domain.repositories.filters import AmbiguousSourceDataError
from backend.domain.services.demand_preparation import prepare_demand
from backend.domain.services.forecasting import calculate_demand_forecast
from backend.domain.services.recommendation import build_recommendation
from backend.domain.services.risk import RiskPolicy
from backend.domain.services.budget import allocate_budget
from backend.domain.value_objects.demand import DemandConfig, DemandGroup, DemandSource


class MissingSupplierTermsError(ValueError):
    code = "supplier_terms_missing"


@dataclass(frozen=True, slots=True)
class CalculationResults:
    anomalies: list[DetectedAnomaly]
    forecasts: list[DemandForecast]
    recommendations: list[Recommendation]


def _month_start(index: int) -> date:
    return date(index // 12, index % 12 + 1, 1)


def _midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _saved_terms(run: CalculationRun, uow: UnitOfWork, product_id: UUID):
    saved = run.parameters.get("supplier_terms_snapshot")
    if saved is None:
        return uow.suppliers.list_terms(product_id)
    return [SupplierProduct(
        id=UUID(item["id"]), supplier_id=UUID(item["supplier_id"]), product_id=UUID(item["product_id"]),
        moq=Decimal(item["moq"]), package_size=Decimal(item["package_size"]),
        lead_time_days=item["lead_time_days"],
        purchase_price=Decimal(item["purchase_price"]) if item["purchase_price"] is not None else None,
        currency=item["currency"], priority=item["priority"],
        is_primary=item["is_primary"], is_active=item["is_active"],
    ) for item in saved.get(str(product_id), [])]


def _monthly_stock(snapshots, start: date, end: date) -> str | None:
    rows = [item for item in snapshots if start <= item.snapshot_at.date() <= end]
    if not rows:
        return None
    latest = max(item.snapshot_at for item in rows)
    observations = {item.quantity_available for item in rows if item.snapshot_at == latest}
    if len(observations) != 1:
        raise AmbiguousSourceDataError("Conflicting monthly stock observations")
    return str(observations.pop())


def _growth_override(uow: UnitOfWork, product, warehouse_id, on_date, batch_ids):
    rows = [row for row in uow.seasonality.list_growth_assumptions(on_date)
            if (row.import_batch_id is None or row.import_batch_id in batch_ids)
            and (row.product_id == product.id or
                 row.product_id is None and row.category_id == product.category_id)
            and (row.warehouse_id is None or row.warehouse_id == warehouse_id)]
    if not rows:
        return None
    # SKU > category; specific warehouse > global; manual > imported;
    # latest effective date. A genuine tie is an input ambiguity, not a guess.
    priority = {GrowthSource.MANUAL: 0, GrowthSource.IMPORTED: 1, GrowthSource.CALCULATED: 2}

    def rank(row):
        return (row.product_id != product.id, row.warehouse_id != warehouse_id,
                priority[row.source], -row.valid_from.toordinal())

    rows.sort(key=lambda row: (rank(row), str(row.id)))
    if len(rows) > 1 and rank(rows[0]) == rank(rows[1]):
        raise AmbiguousSourceDataError("Equally ranked growth assumptions")
    return rows[0]


class CalculationPipeline:
    """Build 30-day forecasts from 12 months, including live transaction facts."""

    def __init__(self, *, demand_config: DemandConfig = DemandConfig(),
                 risk_policy: RiskPolicy = RiskPolicy()) -> None:
        self._demand_config = demand_config
        self._risk_policy = risk_policy

    def configuration(self) -> dict:
        return {
            "demand_config": {key: str(value) if isinstance(value, Decimal) else value
                              for key, value in asdict(self._demand_config).items()},
            "risk_policy": {key: str(value) for key, value in asdict(self._risk_policy).items()},
            "history_periods": 12,
            "forecast_period_days": 30,
            "safety_stock_days": 7,
            "analytics_policy": {
                "version": "demand-quantity-abc-xyz/v1",
                "abc_method": "descending_cleaned_quantity_cumulative_share",
                "abc_a_share": "0.80", "abc_b_share": "0.95",
                "xyz_method": "population_coefficient_of_variation",
                "xyz_x_cv": "0.10", "xyz_y_cv": "0.25",
            },
        }

    def calculate(self, run: CalculationRun, uow: UnitOfWork) -> CalculationResults:
        cutoff = run.source_cutoff_at
        batch_ids = run.import_batch_ids
        source = DemandSource(run.parameters["demand_source"])
        current_month = cutoff.year * 12 + cutoff.month - 1
        last_month = current_month if source is DemandSource.TRANSACTIONS else current_month - 1
        start = _month_start(last_month - 11)
        end = cutoff.date() if source is DemandSource.TRANSACTIONS else _month_start(last_month + 1) - timedelta(days=1)
        lower, upper = _midnight(start), min(_midnight(end + timedelta(days=1)), cutoff)
        forecast_start, forecast_end = cutoff.date(), cutoff.date() + timedelta(days=29)
        products = uow.products.list_products(category_id=run.category_id) if run.category_id else uow.products.list_products()
        warehouses = [run.warehouse_id] if run.warehouse_id else uow.warehouses.list_active_ids()
        anomalies: list[DetectedAnomaly] = []
        forecasts: list[DemandForecast] = []
        recommendations: list[Recommendation] = []

        for product in products:
            terms = sorted(_saved_terms(run, uow, product.id), key=lambda item: (
                not item.is_primary, item.priority, item.lead_time_days,
                item.purchase_price if item.purchase_price is not None else Decimal("Infinity"),
                str(item.supplier_id),
            ))
            for warehouse_id in warehouses:
                transactions = []
                monthly = []
                if source is DemandSource.TRANSACTIONS:
                    rows = uow.sales.list_transactions(
                        lower, upper, product_id=product.id, warehouse_id=warehouse_id,
                        import_batch_ids=batch_ids,
                    )
                    by_id = {row.id: row for row in rows}
                    sale_ids = [row.id for row in rows if row.transaction_type is TransactionType.SALE]
                    for row in uow.sales.list_returns_for_sales(sale_ids, as_of=cutoff, import_batch_ids=batch_ids):
                        by_id[row.id] = row
                    references = {row.original_transaction_id for row in by_id.values()
                                  if row.original_transaction_id is not None}
                    for row in uow.sales.get_transactions_by_ids(
                        references - by_id.keys(), as_of=cutoff, import_batch_ids=batch_ids,
                    ):
                        by_id[row.id] = row
                    transactions = tuple(by_id.values())
                else:
                    monthly = uow.sales.list_monthly_sales(
                        start, end, product_id=product.id, warehouse_id=warehouse_id,
                        import_batch_ids=batch_ids,
                    )
                snapshots = uow.inventory.list_snapshots(
                    product.id, warehouse_id,
                    started_at=lower - timedelta(days=self._demand_config.stockout_max_snapshot_gap_days),
                    ended_at=cutoff, import_batch_ids=batch_ids,
                )
                stockouts = [row for row in uow.inventory.list_stockout_periods(
                    lower, upper, product_id=product.id, warehouse_id=warehouse_id,
                ) if row.import_batch_id is None or row.import_batch_id in batch_ids]
                override = _growth_override(uow, product, warehouse_id, forecast_start, batch_ids)
                prepared = prepare_demand(
                    calculation_run_id=run.id, source=source, start=start, end=end,
                    source_cutoff_at=cutoff, groups=[DemandGroup(product=product, warehouse_id=warehouse_id)],
                    transactions=transactions, monthly_sales=monthly, stockouts=stockouts,
                    snapshots=snapshots, growth_overrides={(product.id, warehouse_id): override} if override else {},
                    config=self._demand_config,
                    allow_partial_final_month=source is DemandSource.TRANSACTIONS,
                ).series[0]
                material = sum((item.required_quantity for item in uow.material_requirements.list_requirements(
                    cutoff, cutoff + timedelta(days=run.forecast_horizon_days),
                    product_id=product.id, warehouse_id=warehouse_id, import_batch_ids=batch_ids,
                )), Decimal("0"))
                if not any(period.observed or period.stockout_adjustment > 0 for period in prepared.periods) and material <= 0:
                    continue
                if not terms:
                    raise MissingSupplierTermsError(f"active supplier terms missing for product {product.id}")
                history_days = sum((period.period_end - period.period_start).days + 1
                                   for period in prepared.periods)
                scale = Decimal("30") / Decimal(history_days)

                def component(name):
                    return sum((getattr(period, name) for period in prepared.periods), Decimal("0")) * scale

                coefficient = uow.seasonality.get_coefficient(
                    product.id, forecast_start, import_batch_ids=batch_ids,
                )
                forecast = calculate_demand_forecast(
                    calculation_run_id=run.id, product_id=product.id, warehouse_id=warehouse_id,
                    period_start=forecast_start, period_end=forecast_end,
                    raw_demand=component("raw_demand"), return_adjustment=component("return_adjustment"),
                    anomaly_adjustment=component("anomaly_adjustment") + component("nonnegative_adjustment"),
                    stockout_adjustment=component("stockout_adjustment"),
                    growth_rate=prepared.growth.factor - Decimal("1"),
                    seasonality_index=coefficient.coefficient if coefficient else Decimal("1"),
                    extra_details={
                        "historical_days": history_days, "source": source.value,
                        "category_id": str(product.category_id) if product.category_id else None,
                        "import_batch_ids": [str(item) for item in sorted(batch_ids)],
                        "preparation_version": "ALG-01-05/v1",
                        "growth_source": prepared.growth.source.value,
                        "growth_reason": prepared.growth.reason,
                        "growth_assumption_id": str(prepared.growth.assumption_id) if prepared.growth.assumption_id else None,
                        "customer_check": prepared.customer_check,
                        "limitations": list(prepared.limitations),
                        "nonnegative_adjustment": str(component("nonnegative_adjustment")),
                        "stockout_evidence": [
                            {"id": str(item.id), "source": item.source.value,
                             "started_at": item.started_at.isoformat(),
                             "ended_at": item.ended_at.isoformat() if item.ended_at else None}
                            for item in prepared.stockout_periods
                        ],
                        "monthly_history": [
                            {"period_start": item.period_start.isoformat(),
                             "period_end": item.period_end.isoformat(),
                             "raw_demand": str(item.raw_demand),
                             "cleaned_demand": str(item.cleaned_demand),
                             "stockout_adjustment": str(item.stockout_adjustment),
                             "stock": _monthly_stock(snapshots, item.period_start, item.period_end),
                             "observed": item.observed}
                            for item in prepared.periods
                        ],
                        "period_anomalies": [
                            {"period_start": item.period_start.isoformat(), "method": item.method,
                             "original_quantity": str(item.original_quantity),
                             "replacement_quantity": str(item.replacement_quantity)}
                            for item in prepared.period_anomalies
                        ],
                    },
                )
                forecasts.append(forecast)
                anomalies.extend(prepared.anomalies)
                snapshot = uow.inventory.get_latest_snapshot(
                    product.id, warehouse_id, cutoff, import_batch_ids=batch_ids,
                )
                stock = max(Decimal("0"), snapshot.quantity_available) if snapshot else Decimal("0")
                transit = sum((item.quantity for item in uow.inventory.list_active_in_transit(
                    product_id=product.id, warehouse_id=warehouse_id,
                    expected_from=cutoff, expected_before=cutoff + timedelta(days=run.forecast_horizon_days),
                    import_batch_ids=batch_ids,
                )), Decimal("0"))
                safety = forecast.forecast_quantity * Decimal("7") / Decimal("30")
                recommendation = build_recommendation(
                    forecast=forecast, supplier_terms=terms[0], current_stock=stock,
                    in_transit_quantity=transit, material_requirement_quantity=material,
                    safety_stock=safety, planning_horizon_days=run.forecast_horizon_days,
                    as_of=cutoff, risk_policy=self._risk_policy,
                )
                recommendation.calculation_details = {
                    **recommendation.calculation_details,
                    "supplier_selection": {
                        "rule": "primary_priority_lead_time_price_supplier_id",
                        "selected_supplier_id": str(terms[0].supplier_id),
                        "candidate_count": len(terms),
                    },
                    "supplier_terms_snapshot": {
                        "supplier_product_id": str(terms[0].id),
                        "unit_price": str(terms[0].purchase_price) if terms[0].purchase_price is not None else None,
                        "currency": terms[0].currency,
                        "moq": str(terms[0].moq),
                        "package_size": str(terms[0].package_size),
                        "lead_time_days": terms[0].lead_time_days,
                    },
                    "risk_policy": self.configuration()["risk_policy"],
                }
                recommendations.append(recommendation)
        budget_value = run.parameters.get("budget_limit")
        if budget_value is not None:
            allocation = allocate_budget(recommendations, Decimal(str(budget_value)), run.parameters.get("currency"))
            run.parameters = {**run.parameters, "currency": allocation.currency,
                              "allocated_amount": str(allocation.allocated_amount),
                              "unmet_need_amount": str(allocation.unmet_need_amount),
                              "optimization_method": allocation.method}
            for row in recommendations:
                unconstrained = row.recommended_quantity
                row.recommended_quantity = allocation.quantities[row.id]
                row.effective_quantity = allocation.quantities[row.id]
                row.calculation_details = {**row.calculation_details, "budget_allocation": {
                    "method": allocation.method, "unconstrained_quantity": str(unconstrained),
                    "allocated_quantity": str(row.recommended_quantity),
                }}
                row.explanation += f" Budget allocation ({allocation.method}): {row.recommended_quantity} of {unconstrained}."
        return CalculationResults(anomalies, forecasts, recommendations)
