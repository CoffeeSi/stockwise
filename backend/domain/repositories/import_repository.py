from __future__ import annotations

from typing import Any, Mapping, Protocol
from uuid import UUID

from backend.domain.entities.imports import ImportBatch


class ImportRepositoryError(RuntimeError):
    pass


class ImportBatchNotFoundError(ImportRepositoryError):
    def __init__(self, batch_id: UUID) -> None:
        super().__init__(f"import batch {batch_id} was not found")
        self.batch_id = batch_id


class DuplicateImportError(ImportRepositoryError):
    def __init__(self, file_checksum: str) -> None:
        super().__init__("a completed import with this checksum already exists")
        self.file_checksum = file_checksum


class InvalidImportStatusTransitionError(ImportRepositoryError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(f"invalid import status transition: {current} -> {target}")
        self.current = current
        self.target = target


class ImportRepository(Protocol):
    def get(self, batch_id: UUID) -> ImportBatch | None: ...

    def list_completed(self) -> list[ImportBatch]: ...

    def get_completed_by_checksum(self, file_checksum: str) -> ImportBatch | None: ...

    def create_batch(self, batch: ImportBatch) -> ImportBatch: ...

    def mark_processing(self, batch_id: UUID) -> ImportBatch: ...

    def mark_completed(
        self, batch_id: UUID, *, row_count: int,
        warnings: tuple[dict[str, Any], ...] = (),
    ) -> ImportBatch: ...

    def mark_failed(
        self,
        batch_id: UUID,
        *,
        error_details: Mapping[str, Any],
    ) -> ImportBatch: ...
