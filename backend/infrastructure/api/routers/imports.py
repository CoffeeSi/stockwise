from pathlib import PureWindowsPath
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError

from backend.application.use_cases.import_data import ImportData, ImportDataCommand, ImportDataFile
from backend.application.use_cases.import_file import MAX_IMPORT_FILE_SIZE
from backend.application.use_cases.get_import_status import GetImportStatus
from backend.domain.entities.catalog import User
from backend.domain.enums import ImportSourceType
from backend.infrastructure.api import dependencies as deps
from backend.infrastructure.api.errors import ERROR_RESPONSES, invoke, safe_issues
from backend.infrastructure.api.schemas.imports import ImportResponse, ImportStatusResponse

router = APIRouter(prefix="/api/imports", tags=["imports"],
                   dependencies=[Depends(deps.get_audit_actor)], responses=ERROR_RESPONSES)


@router.get("/{batch_id}", response_model=ImportStatusResponse)
def get_import_status(batch_id: UUID, use_case: GetImportStatus = Depends(deps.get_import_status)):
    batch = invoke(use_case.execute, batch_id)
    return ImportStatusResponse(
        batch_id=batch.id, source_type=batch.source_type, status=batch.status, row_count=batch.row_count,
        file_checksum=batch.file_checksum, file_name=PureWindowsPath(batch.file_name).name,
        validation_errors=safe_issues((batch.error_details or {}).get("validation_errors", [])),
        error_details={"code": "import_failed"} if batch.error_details else None,
    )


@router.post("", response_model=ImportResponse, status_code=201)
def import_file(source_type: Annotated[ImportSourceType, Form()], file: Annotated[UploadFile, File()],
                user: User = Depends(deps.get_audit_actor), use_case: ImportData = Depends(deps.get_import_data)):
    try:
        name = PureWindowsPath(file.filename or "").name.strip()
        if not name.lower().endswith(".xlsx") or len(name) > 500 or (file.size or 0) > MAX_IMPORT_FILE_SIZE:
            raise HTTPException(422, detail={"code": "invalid_import_file"})
        content = file.file.read(MAX_IMPORT_FILE_SIZE + 1)
        if not content or len(content) > MAX_IMPORT_FILE_SIZE:
            raise HTTPException(422, detail={"code": "invalid_import_file"})
        try:
            result = invoke(use_case.execute, ImportDataCommand(
                source_type=source_type, file=ImportDataFile(name, content), user_id=user.id,
            ))
        except IntegrityError:
            raise HTTPException(422, detail={"code": "invalid_import_data"}) from None
        return ImportResponse(batch_id=result.batch_id, source_type=result.source_type, status=result.status,
                              row_count=result.row_count, file_checksum=result.file_checksum,
                              validation_errors=safe_issues(result.validation_errors))
    finally:
        file.file.close()
