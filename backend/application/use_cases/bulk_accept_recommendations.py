from collections.abc import Sequence
from uuid import UUID

from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.domain.entities.enums import RecommendationStatus
from backend.domain.entities.recommendation import Recommendation, utc_now
from backend.domain.repositories.recommendation_repository import RecommendationConflictError


class RecommendationSelectionConflictError(RecommendationConflictError):
    def __init__(self, recommendation_ids: Sequence[UUID]) -> None:
        self.recommendation_ids = tuple(recommendation_ids)
        super().__init__("Selected recommendations are unavailable, changed, or already ordered")


class BulkAcceptRecommendations:
    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    def execute(self, calculation_run_id: UUID, *, items: Sequence[tuple[UUID, int]],
                user_id: UUID) -> tuple[Recommendation, ...]:
        if not isinstance(user_id, UUID):
            raise ValueError("user_id must be a user UUID")
        ids = [item_id for item_id, _version in items]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("recommendation IDs must be nonempty and unique")
        if any(type(version) is not int or version <= 0 for _item_id, version in items):
            raise ValueError("versions must be positive integers")
        with self._uow_factory() as uow:
            if uow.calculation_runs.get(calculation_run_id) is None:
                raise LookupError("calculation run was not found")
            selected: dict[UUID, Recommendation] = {}
            conflicting = []
            for item_id, version in items:
                row = uow.recommendations.get(item_id)
                if (row is None or row.calculation_run_id != calculation_run_id or row.version != version
                        or row.status not in {RecommendationStatus.SUGGESTED, RecommendationStatus.ADJUSTED}):
                    conflicting.append(item_id)
                else:
                    selected[item_id] = row
            if conflicting:
                raise RecommendationSelectionConflictError(conflicting)
            now = utc_now()
            for row in selected.values():
                row.accept(changed_by=user_id, changed_at=now)
            # Stable claim order avoids deadlocks; any failure rolls back every update.
            for item_id, version in sorted(items):
                try:
                    uow.recommendations.save_acceptance(selected[item_id], expected_version=version)
                except RecommendationConflictError as error:
                    raise RecommendationSelectionConflictError([item_id]) from error
            uow.commit()
        return tuple(selected[item_id] for item_id in ids)
