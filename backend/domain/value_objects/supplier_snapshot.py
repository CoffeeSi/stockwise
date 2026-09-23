"""Read immutable supplier prices without consulting mutable supplier terms."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.domain.value_objects.quantity import validate_quantity


def snapshot_price(details: Mapping[str, Any]) -> tuple[Decimal | None, str | None]:
    snapshot = details.get("supplier_terms_snapshot")
    if not isinstance(snapshot, Mapping):
        return None, None
    raw_currency = snapshot.get("currency")
    currency = raw_currency if isinstance(raw_currency, str) and raw_currency.strip() else None
    raw_price = snapshot.get("unit_price")
    if raw_price is None:
        return None, currency
    try:
        price = Decimal(str(raw_price))
    except InvalidOperation as error:
        raise ValueError("invalid saved supplier unit price") from error
    validate_quantity(price, "unit_price")
    return price, currency
