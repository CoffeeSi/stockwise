from dataclasses import dataclass, replace
from decimal import Decimal
from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.domain.entities.enums import CalculationRunStatus, Urgency
from backend.domain.services.budget import allocate_budget, saved_price
from backend.domain.services.replenishment import calculate_replenishment
from backend.domain.services.risk import RiskPolicy, assess_shortage_risk


@dataclass(frozen=True, slots=True, kw_only=True)
class ScenarioAssumptions:
    base_run_id: UUID
    growth_multiplier: Decimal = Decimal("1")
    service_level: Decimal = Decimal("0.95")
    supplier_delay_days: int = 0
    include_anomalies: bool = False
    budget_limit: Decimal | None = None


class PreviewScenario:
    def __init__(self, uow_factory: UnitOfWorkFactory):
        self._uow_factory = uow_factory

    def execute(self, assumptions: ScenarioAssumptions) -> dict:
        if assumptions.growth_multiplier <= 0 or not 0 < assumptions.service_level <= 1 or assumptions.supplier_delay_days < 0:
            raise ValueError("invalid scenario assumptions")
        with self._uow_factory() as uow:
            run = uow.calculation_runs.get(assumptions.base_run_id)
            if run is None:
                raise LookupError("run not found")
            if run.status is not CalculationRunStatus.COMPLETED:
                from backend.domain.errors import InvalidEntityStateError
                raise InvalidEntityStateError("scenario requires a completed calculation")
            rows = []
            offset = 0
            while True:
                page, total = uow.recommendations.list_for_run(run.id, limit=500, offset=offset)
                rows.extend(page)
                offset += len(page)
                if offset >= total or not page:
                    break
            simulated = []
            items = []
            policy = RiskPolicy(**{key: Decimal(str(value)) for key, value in run.parameters.get("risk_policy", {}).items()})
            for row in rows:
                forecast = uow.calculation_runs.get_forecast(run.id, row.product_id, row.warehouse_id)
                if forecast is None:
                    raise ValueError("saved forecast is missing")
                if assumptions.include_anomalies:
                    baseline = max(Decimal("0"), forecast.raw_demand + forecast.return_adjustment + forecast.stockout_adjustment)
                    simulated_forecast = baseline * (Decimal("1") + forecast.growth_rate) * assumptions.growth_multiplier * forecast.seasonality_index
                else:
                    # Preserve the saved forecast: recomputing rounded components can change pack rounding.
                    simulated_forecast = forecast.forecast_quantity * assumptions.growth_multiplier
                lead_days = int(row.calculation_details.get("lead_time_days", 0)) + assumptions.supplier_delay_days
                # Explicit preview heuristic: scale saved safety stock linearly from 95%.
                # This is a scenario assumption, not a statistical service guarantee.
                safety = row.safety_stock * assumptions.service_level / Decimal("0.95") * assumptions.growth_multiplier
                period_days = (forecast.period_end - forecast.period_start).days + 1
                result = calculate_replenishment(forecast_quantity=simulated_forecast,
                    forecast_period_days=period_days, planning_horizon_days=run.forecast_horizon_days,
                    lead_time_days=lead_days, safety_stock=safety, current_stock=row.current_stock,
                    in_transit_quantity=row.in_transit_quantity, material_requirement_quantity=row.material_requirement_quantity,
                    moq=row.moq, package_size=row.package_size)
                risk = assess_shortage_risk(as_of=run.source_cutoff_at, daily_demand=simulated_forecast / Decimal(period_days),
                    demand_during_horizon=result.demand_during_horizon, current_stock=row.current_stock,
                    in_transit_quantity=row.in_transit_quantity, material_requirement_quantity=row.material_requirement_quantity,
                    safety_stock=safety, lead_time_days=lead_days, policy=policy)
                simulated.append(replace(row, recommended_quantity=result.recommended_quantity, effective_quantity=result.recommended_quantity,
                                         risk_score=risk.risk_score, urgency=risk.urgency))
                items.append({"recommendation_id": row.id, "baseline_quantity": row.recommended_quantity,
                              "simulated_quantity": result.recommended_quantity,
                              "reason": "Сохранённый прогноз с коэффициентом роста, сроком поставки и масштабированным страховым запасом; MOQ и упаковка применены."})
            allocation = allocate_budget(simulated, assumptions.budget_limit, run.parameters.get("currency")) if assumptions.budget_limit else None
            if allocation:
                for row, item in zip(simulated, items):
                    item["simulated_quantity"] = allocation.quantities[row.id]
                    item["reason"] += " Применён бюджет по приоритету риска."
            currencies = set()
            amount = Decimal("0")
            prices_known = True
            for row, item in zip(simulated, items):
                price, currency = saved_price(row)
                if item["simulated_quantity"] <= 0:
                    continue
                if price is None or currency is None:
                    prices_known = False
                else:
                    currencies.add(currency)
                    amount += price * item["simulated_quantity"]
            return {"base_run_id": run.id, "assumptions": assumptions,
                    "method": "saved_forecast_linear_safety/v1", "is_preview": True,
                    "limitations": ["Уровень сервиса линейно масштабирует сохранённый страховой запас относительно 0.95; это допущение сценария, а не статистическая гарантия."],
                    "totals": {"amount": amount if prices_known and len(currencies) <= 1 else None,
                               "currency": next(iter(currencies)) if prices_known and len(currencies) == 1 else None,
                               "quantity": sum((item["simulated_quantity"] for item in items), Decimal("0")),
                               "critical_count": sum(row.urgency is Urgency.CRITICAL for row in simulated),
                               "budget_gap": allocation.unmet_need_amount if allocation else None}, "items": items}
