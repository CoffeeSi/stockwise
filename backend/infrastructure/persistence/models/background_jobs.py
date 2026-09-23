from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, CreatedAtMixin, JSON_DOCUMENT, UUIDPrimaryKeyMixin


class BackgroundJobModel(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        UniqueConstraint("kind", "created_by", "idempotency_key", name="uq_background_jobs_idempotency"),
        CheckConstraint("kind IN ('calculation', 'import')", name="valid_job_kind"),
        CheckConstraint("status IN ('pending', 'running', 'completed', 'failed')", name="valid_job_status"),
        CheckConstraint("(kind = 'calculation' AND calculation_run_id IS NOT NULL AND import_batch_id IS NULL) OR "
                        "(kind = 'import' AND import_batch_id IS NOT NULL AND calculation_run_id IS NULL)",
                        name="valid_job_resource"),
        Index("ix_background_jobs_claim", "status", "lease_until", "created_at"),
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    calculation_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("calculation_runs.id", ondelete="CASCADE"), unique=True)
    import_batch_id: Mapped[UUID | None] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), unique=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    claim_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
