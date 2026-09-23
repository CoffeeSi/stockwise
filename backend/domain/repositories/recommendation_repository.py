from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from backend.domain.entities.enums import RecommendationStatus, Urgency
from backend.domain.entities.recommendation import Recommendation, RecommendationAdjustment
from backend.domain.value_objects.recommendation_display import RecommendationDisplay


class RecommendationNotFoundError(RuntimeError):
    pass


class RecommendationConflictError(RuntimeError):
    """The recommendation was changed or ordered by another operation."""


class RecommendationRepository(Protocol):
    def get(self, recommendation_id: UUID) -> Recommendation | None: ...

    def list_for_run(
        self,
        run_id: UUID,
        *,
        supplier_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        urgency: Urgency | None = None,
        status: RecommendationStatus | None = None,
        category_id: UUID | None = None,
        search: str | None = None,
        sort_by: str = "risk_score",
        descending: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Recommendation], int]: ...

    def get_display_data(self, recommendation_ids: Sequence[UUID]) -> dict[UUID, RecommendationDisplay]: ...

    def add_many(self, recommendations: list[Recommendation]) -> None: ...

    def count_for_run(self, run_id: UUID) -> int: ...

    def count_for_runs(self, run_ids: Sequence[UUID]) -> dict[UUID, int]: ...

    def list_orderable(self, calculation_run_id: UUID) -> Sequence[Recommendation]:
        """Accepted, positive, not yet ordered; deterministic ID order."""
        ...

    def save_adjustment(
        self, recommendation: Recommendation, adjustment: RecommendationAdjustment,
        *, expected_version: int,
    ) -> None:
        """Compare-and-swap version/status and append audit in the caller's transaction."""
        ...

    def mark_converted(self, recommendation: Recommendation, *, expected_version: int) -> None:
        """Atomically claim an accepted recommendation before inserting its order item."""
        ...

    def save_acceptance(self, recommendation: Recommendation, *, expected_version: int) -> None:
        """Compare-and-swap suggested/adjusted to accepted in one transaction."""
        ...

    def list_adjustments(self, recommendation_id: UUID) -> Sequence[RecommendationAdjustment]: ...
