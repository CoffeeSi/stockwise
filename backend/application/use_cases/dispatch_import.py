from datetime import datetime, timezone
from hashlib import sha256

from backend.application.dto.imports import ImportFileCommand
from backend.application.ports.import_spool import ImportSpool
from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.use_cases.import_file import MAX_IMPORT_FILE_SIZE, InvalidImportFileError
from backend.domain.entities.background_job import BackgroundJob
from backend.domain.entities.imports import ImportBatch
from backend.domain.enums import ImportStatus


class DispatchImport:
    def __init__(self, factory: UnitOfWorkFactory, spool: ImportSpool) -> None:
        self._factory = factory
        self._spool = spool

    def execute(self, command: ImportFileCommand) -> ImportBatch:
        if (not command.file_name.strip().lower().endswith(".xlsx") or not command.content
                or len(command.content) > MAX_IMPORT_FILE_SIZE):
            raise InvalidImportFileError("only nonempty .xlsx files up to 25 MiB are supported")
        batch = ImportBatch(source_type=command.source_type, file_name=command.file_name,
                            file_checksum=sha256(command.content).hexdigest(), status=ImportStatus.PENDING,
                            imported_by=command.imported_by, imported_at=datetime.now(timezone.utc))
        self._spool.write(batch.id, command.content)
        try:
            with self._factory() as uow:
                uow.imports.create_batch(batch)
                uow.jobs.add(BackgroundJob(kind="import", resource_id=batch.id, created_by=command.imported_by,
                                          request_fingerprint=batch.file_checksum,
                                          progress={"stage": "uploaded", "processed_rows": 0, "total_rows": None}))
                uow.commit()
        except Exception:
            self._spool.remove(batch.id)
            raise
        return batch
