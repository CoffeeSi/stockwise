from dataclasses import dataclass
from uuid import UUID

from backend.application.dto.calculation import CalculationRunResult
from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.domain.entities.enums import CalculationRunStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ListCalculationRunsQuery:
    status: CalculationRunStatus | None = None
    warehouse_id: UUID | None = None
    category_id: UUID | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class CalculationRunPage:
    items: list[CalculationRunResult]
    total: int
    limit: int
    offset: int


class ListCalculationRuns:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, query: ListCalculationRunsQuery) -> CalculationRunPage:
        if not 1 <= query.limit <= 100 or query.offset < 0:
            raise ValueError("limit must be 1..100 and offset nonnegative")
        with self._uow_factory() as uow:
            runs, total = uow.calculation_runs.list_runs(
                status=query.status, warehouse_id=query.warehouse_id,
                category_id=query.category_id, limit=query.limit, offset=query.offset,
            )
            counts = uow.recommendations.count_for_runs([run.id for run in runs])
            items = [CalculationRunResult(
                id=run.id, status=run.status, parameters=run.parameters,
                started_at=run.started_at, finished_at=run.finished_at,
                algorithm_version=run.algorithm_version, error_details=run.error_details,
                recommendation_count=counts.get(run.id, 0),
                import_batch_ids=tuple(sorted(run.import_batch_ids)),
            ) for run in runs]
            return CalculationRunPage(items, total, query.limit, query.offset)
