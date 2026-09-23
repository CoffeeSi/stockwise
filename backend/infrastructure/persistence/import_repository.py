from __future__ import annotations

from datetime import timezone
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.entities.imports import ImportBatch
from backend.domain.enums import ImportStatus
from backend.domain.repositories.import_repository import (
    DuplicateImportError,
    ImportBatchNotFoundError,
    InvalidImportStatusTransitionError,
)
from backend.infrastructure.persistence.models.imports import ImportBatchModel


class SqlAlchemyImportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, batch_id: UUID) -> ImportBatch | None:
        model = self._session.get(ImportBatchModel, batch_id)
        return self._to_domain(model) if model is not None else None

    def list_completed(self) -> list[ImportBatch]:
        models = self._session.scalars(
            select(ImportBatchModel)
            .where(ImportBatchModel.status == ImportStatus.COMPLETED)
            .order_by(ImportBatchModel.imported_at, ImportBatchModel.id)
        ).all()
        return [self._to_domain(model) for model in models]

    def get_completed_by_checksum(self, file_checksum: str) -> ImportBatch | None:
        model = self._session.scalar(
            select(ImportBatchModel)
            .where(
                ImportBatchModel.file_checksum == file_checksum,
                ImportBatchModel.status == ImportStatus.COMPLETED,
            )
            .limit(1)
        )
        return self._to_domain(model) if model is not None else None

    def create_batch(self, batch: ImportBatch) -> ImportBatch:
        if batch.status is not ImportStatus.PENDING:
            raise InvalidImportStatusTransitionError(
                batch.status.value,
                ImportStatus.PENDING.value,
            )
        if batch.row_count != 0:
            raise ValueError("a new import batch must have row_count equal to zero")
        if self.get_completed_by_checksum(batch.file_checksum) is not None:
            raise DuplicateImportError(batch.file_checksum)

        model = ImportBatchModel(
            id=batch.id,
            source_type=batch.source_type,
            file_name=batch.file_name,
            file_checksum=batch.file_checksum,
            status=batch.status,
            row_count=batch.row_count,
            imported_by=batch.imported_by,
            imported_at=batch.imported_at,
            error_details=dict(batch.error_details) if batch.error_details is not None else None,
        )
        self._session.add(model)
        self._session.flush()
        return self._to_domain(model)

    def mark_processing(self, batch_id: UUID) -> ImportBatch:
        model = self._require(batch_id)
        self._require_transition(model.status, ImportStatus.PROCESSING)
        model.status = ImportStatus.PROCESSING
        model.error_details = None
        self._session.flush()
        return self._to_domain(model)

    def mark_completed(
        self, batch_id: UUID, *, row_count: int,
        warnings: tuple[dict[str, Any], ...] = (),
    ) -> ImportBatch:
        if row_count < 0:
            raise ValueError("row_count must be nonnegative")
        model = self._require(batch_id)
        self._require_transition(model.status, ImportStatus.COMPLETED)

        duplicate = self._session.scalar(
            select(ImportBatchModel.id)
            .where(
                ImportBatchModel.file_checksum == model.file_checksum,
                ImportBatchModel.status == ImportStatus.COMPLETED,
                ImportBatchModel.id != model.id,
            )
            .limit(1)
        )
        if duplicate is not None:
            raise DuplicateImportError(model.file_checksum)

        model.status = ImportStatus.COMPLETED
        model.row_count = row_count
        model.error_details = {"warnings": list(warnings)} if warnings else None
        try:
            self._session.flush()
        except IntegrityError:
            raise DuplicateImportError(model.file_checksum) from None
        return self._to_domain(model)

    def mark_failed(
        self,
        batch_id: UUID,
        *,
        error_details: Mapping[str, Any],
    ) -> ImportBatch:
        model = self._require(batch_id)
        self._require_transition(model.status, ImportStatus.FAILED)
        model.status = ImportStatus.FAILED
        model.error_details = dict(error_details)
        self._session.flush()
        return self._to_domain(model)

    def _require(self, batch_id: UUID) -> ImportBatchModel:
        model = self._session.get(ImportBatchModel, batch_id)
        if model is None:
            raise ImportBatchNotFoundError(batch_id)
        return model

    @staticmethod
    def _require_transition(current: ImportStatus, target: ImportStatus) -> None:
        allowed = {
            ImportStatus.PENDING: {ImportStatus.PROCESSING, ImportStatus.FAILED},
            ImportStatus.PROCESSING: {ImportStatus.COMPLETED, ImportStatus.FAILED},
            ImportStatus.COMPLETED: set(),
            ImportStatus.FAILED: set(),
        }
        if target not in allowed[current]:
            raise InvalidImportStatusTransitionError(current.value, target.value)

    @staticmethod
    def _to_domain(model: ImportBatchModel) -> ImportBatch:
        imported_at = model.imported_at
        if imported_at.tzinfo is None or imported_at.utcoffset() is None:
            imported_at = imported_at.replace(tzinfo=timezone.utc)
        return ImportBatch(
            id=model.id,
            source_type=model.source_type,
            file_name=model.file_name,
            file_checksum=model.file_checksum,
            status=model.status,
            row_count=model.row_count,
            imported_by=model.imported_by,
            imported_at=imported_at,
            error_details=(
                dict(model.error_details) if model.error_details is not None else None
            ),
        )
