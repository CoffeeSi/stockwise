from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.dto.recommendation import ProcurementRecommendationRow
from backend.domain.entities.enums import RecommendationStatus, Urgency


@dataclass(frozen=True, slots=True, kw_only=True)
class ListRecommendationsQuery:
    calculation_run_id: UUID
    supplier_id: UUID | None = None
    category_id: UUID | None = None
    warehouse_id: UUID | None = None
    urgency: Urgency | None = None
    status: RecommendationStatus | None = None
    search: str | None = None
    sort_by: str = "risk_score"
    descending: bool = True
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class RecommendationPage:
    items: list[ProcurementRecommendationRow]
    total: int
    limit: int
    offset: int


class ListRecommendations:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, query: ListRecommendationsQuery) -> RecommendationPage:
        if not 1 <= query.limit <= 500 or query.offset < 0:
            raise ValueError("limit must be 1..500 and offset nonnegative")
        with self._uow_factory() as uow:
            if uow.calculation_runs.get(query.calculation_run_id) is None:
                raise LookupError("calculation run not found")
            items, total = uow.recommendations.list_for_run(
                query.calculation_run_id, supplier_id=query.supplier_id,
                category_id=query.category_id, warehouse_id=query.warehouse_id,
                urgency=query.urgency, status=query.status,
                search=query.search,
                sort_by=query.sort_by, descending=query.descending,
                limit=query.limit, offset=query.offset,
            )
            displays = uow.recommendations.get_display_data([item.id for item in items])
            rows = [ProcurementRecommendationRow.from_recommendation(item, displays[item.id])
                    for item in items]
            return RecommendationPage(rows, total, query.limit, query.offset)
