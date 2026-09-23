from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from backend.domain.enums import ImportSourceType, ImportStatus


class ImportProgressResponse(BaseModel):
    stage: Literal["uploaded", "validating", "persisting", "completed"]
    processed_rows: int = Field(ge=0)
    total_rows: int | None = Field(default=None, ge=0)


class ImportResponse(BaseModel):
    batch_id: UUID
    source_type: ImportSourceType
    status: ImportStatus
    row_count: int
    file_checksum: str
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    progress: ImportProgressResponse | None = None


class ImportStatusResponse(ImportResponse):
    file_name: str
    error_details: dict[str, Any] | None = None
