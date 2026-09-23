from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from backend.domain.entities.enums import CalculationRunStatus
from backend.domain.value_objects.demand import DemandSource


@dataclass(frozen=True, slots=True, kw_only=True)
class RunCalculationCommand:
    user_id: UUID
    horizon_days: int
    warehouse_id: UUID | None = None
    category_id: UUID | None = None
    demand_source: DemandSource = DemandSource.TRANSACTIONS
    budget_limit: Decimal | None = None
    currency: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationRunResult:
    id: UUID
    status: CalculationRunStatus
    parameters: Mapping[str, Any]
    started_at: datetime
    finished_at: datetime | None
    algorithm_version: str
    error_details: Mapping[str, Any] | None
    recommendation_count: int
    import_batch_ids: tuple[UUID, ...]
