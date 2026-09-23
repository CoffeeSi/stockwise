from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from backend.domain.entities.background_job import BackgroundJob, JobLeaseLostError
from backend.infrastructure.persistence.models.background_jobs import BackgroundJobModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SqlAlchemyBackgroundJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _domain(row: BackgroundJobModel) -> BackgroundJob:
        return BackgroundJob(id=row.id, kind=row.kind, resource_id=row.calculation_run_id or row.import_batch_id,
                             created_by=row.created_by, request_fingerprint=row.request_fingerprint,
                             idempotency_key=row.idempotency_key, payload=dict(row.payload),
                             progress=dict(row.progress), status=row.status, claim_token=row.claim_token,
                             created_at=row.created_at)

    def get_for_key(self, kind: str, user_id: UUID, key: str) -> BackgroundJob | None:
        row = self._session.scalar(select(BackgroundJobModel).where(
            BackgroundJobModel.kind == kind, BackgroundJobModel.created_by == user_id,
            BackgroundJobModel.idempotency_key == key,
        ))
        return self._domain(row) if row else None

    def get_for_resource(self, kind: str, resource_id: UUID) -> BackgroundJob | None:
        column = BackgroundJobModel.calculation_run_id if kind == "calculation" else BackgroundJobModel.import_batch_id
        row = self._session.scalar(select(BackgroundJobModel).where(BackgroundJobModel.kind == kind, column == resource_id))
        return self._domain(row) if row else None

    def add(self, job: BackgroundJob) -> None:
        self._session.add(BackgroundJobModel(
            id=job.id, kind=job.kind,
            calculation_run_id=job.resource_id if job.kind == "calculation" else None,
            import_batch_id=job.resource_id if job.kind == "import" else None,
            created_by=job.created_by, idempotency_key=job.idempotency_key,
            request_fingerprint=job.request_fingerprint, status="pending", attempts=0,
            payload=job.payload, progress=job.progress, created_at=job.created_at,
        ))
        self._session.flush()

    def claim(self, *, lease_seconds: int = 60) -> BackgroundJob | None:
        now = _now()
        eligible = or_(BackgroundJobModel.status == "pending",
                       (BackgroundJobModel.status == "running") & (BackgroundJobModel.lease_until < now))
        row = self._session.scalar(select(BackgroundJobModel).where(eligible)
            .order_by(BackgroundJobModel.created_at, BackgroundJobModel.id).with_for_update(skip_locked=True).limit(1))
        if row is None:
            return None
        token = uuid4()
        changed = self._session.execute(update(BackgroundJobModel).where(
            BackgroundJobModel.id == row.id, eligible,
        ).values(status="running", claim_token=token, lease_until=now + timedelta(seconds=lease_seconds),
                 attempts=BackgroundJobModel.attempts + 1).execution_options(synchronize_session=False))
        if changed.rowcount != 1:
            return None
        self._session.refresh(row)
        return self._domain(row)

    def _owned(self, job_id: UUID, token: UUID):
        return (BackgroundJobModel.id == job_id, BackgroundJobModel.claim_token == token,
                BackgroundJobModel.status == "running")

    def assert_owned(self, job_id: UUID, claim_token: UUID) -> None:
        found = self._session.scalar(select(BackgroundJobModel.id).where(*self._owned(job_id, claim_token)).with_for_update())
        if found is None:
            raise JobLeaseLostError("background job lease was replaced")

    def heartbeat(self, job_id: UUID, claim_token: UUID, *, progress: dict | None = None) -> None:
        values = {"lease_until": _now() + timedelta(seconds=60)}
        if progress is not None:
            values["progress"] = progress
        result = self._session.execute(update(BackgroundJobModel).where(*self._owned(job_id, claim_token)).values(**values))
        if result.rowcount != 1:
            raise JobLeaseLostError("background job lease was replaced")

    def complete(self, job_id: UUID, claim_token: UUID, *, progress: dict) -> None:
        result = self._session.execute(update(BackgroundJobModel).where(*self._owned(job_id, claim_token)).values(
            status="completed", finished_at=_now(), lease_until=None, progress=progress,
        ))
        if result.rowcount != 1:
            raise JobLeaseLostError("background job lease was replaced")

    def fail(self, job_id: UUID, claim_token: UUID) -> None:
        result = self._session.execute(update(BackgroundJobModel).where(*self._owned(job_id, claim_token)).values(
            status="failed", finished_at=_now(), lease_until=None,
        ))
        if result.rowcount != 1:
            raise JobLeaseLostError("background job lease was replaced")
