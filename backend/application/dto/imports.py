from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.domain.enums import ImportSourceType, ImportStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportFileCommand:
    source_type: ImportSourceType
    file_name: str
    content: bytes
    imported_by: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ParsedImport:
    source_type: ImportSourceType
    rows: tuple[dict[str, Any], ...]
    warnings: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ImportFileResult:
    batch_id: UUID
    source_type: ImportSourceType
    status: ImportStatus
    row_count: int
    file_checksum: str
    validation_errors: tuple[dict[str, Any], ...] = ()
