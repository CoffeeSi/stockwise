"""Deterministic risk-prioritized, whole-pack allocation from saved prices."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from uuid import UUID

from backend.domain.entities.recommendation import Recommendation

BUDGET_METHOD = "risk_priority_whole_pack/v1"


class BudgetInputError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BudgetAllocation:
    quantities: dict[UUID, Decimal]
    currency: str
    allocated_amount: Decimal
    unmet_need_amount: Decimal
    method: str = BUDGET_METHOD


def saved_price(row: Recommendation) -> tuple[Decimal | None, str | None]:
    snapshot = row.calculation_details.get("supplier_terms_snapshot")
    if not isinstance(snapshot, dict):
        return None, None
    currency = snapshot.get("currency")
    currency = currency if isinstance(currency, str) and len(currency) == 3 else None
    raw = snapshot.get("unit_price")
    if raw is None:
        return None, currency
    try:
        price = Decimal(str(raw))
    except InvalidOperation:
        return None, currency
    return (price if price.is_finite() and price >= 0 else None), currency


def allocate_budget(rows: list[Recommendation], budget: Decimal, currency: str | None = None) -> BudgetAllocation:
    if not budget.is_finite() or budget <= 0:
        raise BudgetInputError("invalid_budget")
    priced = []
    currencies = set()
    for row in rows:
        if row.recommended_quantity <= 0:
            continue
        price, row_currency = saved_price(row)
        if price is None or row_currency is None:
            raise BudgetInputError("budget_price_missing")
        currencies.add(row_currency)
        priced.append((row, price))
    if len(currencies) > 1 or (currency and currencies and currency not in currencies):
        raise BudgetInputError("budget_currency_mismatch")
    selected_currency = currency or next(iter(currencies), None)
    if selected_currency is None:
        raise BudgetInputError("budget_currency_missing")
    available = budget
    quantities = {row.id: Decimal("0") for row in rows}
    total_need = sum((row.recommended_quantity * price for row, price in priced), Decimal("0"))
    for row, price in sorted(priced, key=lambda item: (-item[0].risk_score, str(item[0].supplier_id), str(item[0].product_id), str(item[0].id))):
        if price == 0:
            quantity = row.recommended_quantity
        else:
            packs = (available / (price * row.package_size)).to_integral_value(rounding=ROUND_FLOOR)
            quantity = min(row.recommended_quantity, packs * row.package_size)
        if quantity < row.moq:
            quantity = Decimal("0")
        quantities[row.id] = quantity
        available -= quantity * price
    allocated = budget - available
    return BudgetAllocation(quantities, selected_currency, allocated, total_need - allocated)
