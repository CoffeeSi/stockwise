from decimal import Decimal
from uuid import UUID

from pydantic import Field

from backend.infrastructure.api.schemas.workflows import ReadModel, RequestModel


class ScenarioPreviewRequest(RequestModel):
    base_run_id: UUID
    growth_multiplier: Decimal = Field(default=Decimal("1"), gt=0, allow_inf_nan=False)
    service_level: Decimal = Field(default=Decimal("0.95"), gt=0, le=1, allow_inf_nan=False)
    supplier_delay_days: int = Field(default=0, ge=0, le=3650, strict=True)
    include_anomalies: bool = False
    budget_limit: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=4, allow_inf_nan=False)


class ScenarioTotals(ReadModel):
    amount: Decimal | None
    currency: str | None
    quantity: Decimal
    critical_count: int
    budget_gap: Decimal | None


class ScenarioItem(ReadModel):
    recommendation_id: UUID
    baseline_quantity: Decimal
    simulated_quantity: Decimal
    reason: str


class ScenarioPreviewResponse(ReadModel):
    base_run_id: UUID
    assumptions: ScenarioPreviewRequest
    method: str
    is_preview: bool
    limitations: list[str]
    totals: ScenarioTotals
    items: list[ScenarioItem]
