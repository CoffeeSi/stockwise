from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True, kw_only=True)
class BackgroundJob:
    kind: str
    resource_id: UUID
    created_by: UUID
    request_fingerprint: str
    idempotency_key: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    progress: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    claim_token: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobLeaseLostError(RuntimeError):
    """A resumed worker owns this job; the stale attempt cannot commit."""


class IdempotencyConflictError(ValueError):
    """A request key was already used for a different payload."""
