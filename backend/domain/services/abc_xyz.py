from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

from backend.domain.value_objects.analytics import AbcXyzCell


def classify_demand(
    series: Mapping[UUID, Mapping[str, Decimal]], policy: Mapping[str, str],
) -> list[AbcXyzCell]:
    """Classify saved SKU demand quantities; all calendar months participate in CV."""
    if policy.get("version") != "demand-quantity-abc-xyz/v1":
        raise ValueError("Unsupported ABC/XYZ policy version")
    a_share, b_share = Decimal(policy["abc_a_share"]), Decimal(policy["abc_b_share"])
    x_cv, y_cv = Decimal(policy["xyz_x_cv"]), Decimal(policy["xyz_y_cv"])
    if not Decimal("0") < a_share < b_share < Decimal("1") or not Decimal("0") <= x_cv < y_cv:
        raise ValueError("Invalid ABC/XYZ policy thresholds")
    months = sorted({month for values in series.values() for month in values})
    totals = {sku: sum(values.values(), Decimal("0")) for sku, values in series.items()}
    if any(not value.is_finite() or value < 0 for values in series.values() for value in values.values()):
        raise ValueError("ABC/XYZ requires finite nonnegative saved demand")
    grand_total = sum(totals.values(), Decimal("0"))
    counts = {(abc, xyz): 0 for abc in "ABC" for xyz in "XYZ"}
    amounts = {(abc, xyz): Decimal("0") for abc in "ABC" for xyz in "XYZ"}
    cumulative = Decimal("0")
    for sku in sorted(totals, key=lambda value: (-totals[value], str(value))):
        total = totals[sku]
        if total == 0 or grand_total == 0 or not months:
            abc, xyz = "C", "Z"
        else:
            # The item crossing a cumulative threshold belongs to the preceding class.
            previous_share = cumulative / grand_total
            abc = "A" if previous_share < a_share else "B" if previous_share < b_share else "C"
            values = [series[sku].get(month, Decimal("0")) for month in months]
            mean = total / Decimal(len(values))
            variance = sum(((value - mean) ** 2 for value in values), Decimal("0")) / Decimal(len(values))
            cv = variance.sqrt() / mean
            xyz = "X" if cv <= x_cv else "Y" if cv <= y_cv else "Z"
        counts[(abc, xyz)] += 1
        amounts[(abc, xyz)] += total
        cumulative += total
    return [AbcXyzCell(abc, xyz, counts[(abc, xyz)],
                       amounts[(abc, xyz)] / grand_total if grand_total else Decimal("0"))
            for abc in "ABC" for xyz in "XYZ"]
