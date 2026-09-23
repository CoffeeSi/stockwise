import os
from pathlib import Path
from uuid import UUID, uuid4

from backend.application.use_cases.import_file import MAX_IMPORT_FILE_SIZE


class FileImportSpool:
    """Private durable upload storage; paths contain generated UUIDs, never client filenames."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)

    def _path(self, batch_id: UUID) -> Path:
        if not isinstance(batch_id, UUID):
            raise ValueError("import batch ID must be a UUID")
        return self.directory / f"{batch_id}.xlsx"

    def write(self, batch_id: UUID, content: bytes) -> None:
        if not content or len(content) > MAX_IMPORT_FILE_SIZE:
            raise ValueError("invalid import file size")
        destination = self._path(batch_id)
        temporary = self.directory / f"{batch_id}.{uuid4().hex}.tmp"
        try:
            with temporary.open("xb") as stream:
                os.chmod(temporary, 0o600)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, batch_id: UUID) -> bytes:
        with self._path(batch_id).open("rb") as stream:
            content = stream.read(MAX_IMPORT_FILE_SIZE + 1)
        if not content or len(content) > MAX_IMPORT_FILE_SIZE:
            raise ValueError("invalid persisted import file size")
        return content

    def remove(self, batch_id: UUID) -> None:
        self._path(batch_id).unlink(missing_ok=True)
