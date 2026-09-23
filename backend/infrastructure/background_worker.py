"""Durable DB queue consumer with renewable leases and fenced result commits."""

from __future__ import annotations

import logging
import time
from hashlib import sha256
from pathlib import Path
from threading import Event, Thread
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.application.dto.imports import ImportFileCommand
from backend.application.use_cases.run_calculation import RunCalculation
from backend.domain.entities.background_job import BackgroundJob, JobLeaseLostError
from backend.domain.entities.enums import CalculationRunStatus
from backend.domain.enums import ImportStatus
from backend.infrastructure.excel.import_spool import FileImportSpool
from backend.infrastructure.excel.ai_mapping import AiExcelMappingAssistant
from backend.infrastructure.excel.readers import ExcelImportReader
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.persistence.application_uow import create_application_uow_factory
from backend.infrastructure.persistence.background_job_repository import SqlAlchemyBackgroundJobRepository
from backend.infrastructure.persistence.database import Database
from backend.infrastructure.persistence.import_gateway import SqlAlchemyImportGateway
from backend.infrastructure.persistence.import_repository import SqlAlchemyImportRepository

logger = logging.getLogger(__name__)


class BackgroundWorker:
    def __init__(self, database: Database, spool_directory: Path, settings: Settings) -> None:
        self._database = database
        self._factory = create_application_uow_factory(database)
        self.spool = FileImportSpool(spool_directory)
        self._ai_mapper = AiExcelMappingAssistant(
            settings.openai_api_key, settings.openai_model, settings.openai_timeout_seconds,
        )
        self._stop = Event()
        self._wake = Event()
        self._thread = Thread(target=self._run, name="stockwise-background-jobs", daemon=True)
        self._started = False
        self._next_cleanup = 0.0

    def start(self) -> None:
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        # Complete in-flight work before the application's database pool is disposed.
        if self._started:
            self._thread.join()

    def notify(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if time.monotonic() >= self._next_cleanup:
                    try:
                        self._cleanup_spool()
                    except OSError as error:
                        logger.error("Import spool cleanup failed (%s)", type(error).__name__)
                    self._next_cleanup = time.monotonic() + 60
                with self._database.session() as session:
                    job = SqlAlchemyBackgroundJobRepository(session).claim()
                if job is None:
                    self._wake.wait(2)
                    self._wake.clear()
                    continue
                self._process(job)
            except SQLAlchemyError as error:
                logger.error("Background queue database operation failed (%s)", type(error).__name__)
                self._stop.wait(5)
            except Exception as error:
                logger.error("Background queue operation failed (%s)", type(error).__name__)
                self._stop.wait(5)

    def _process(self, job: BackgroundJob) -> None:
        if job.claim_token is None:
            raise ValueError("a claimed job must have an ownership token")
        heartbeat_stop = Event()
        lease_lost = Event()

        def heartbeat() -> None:
            while not heartbeat_stop.wait(10):
                try:
                    self._progress(job, None)
                except JobLeaseLostError:
                    lease_lost.set()
                    return
                except SQLAlchemyError as error:
                    logger.error("Job heartbeat failed (%s)", type(error).__name__)

        heartbeat_thread = Thread(target=heartbeat, name=f"job-heartbeat-{job.id}", daemon=True)
        heartbeat_thread.start()
        terminal = False
        try:
            if job.kind == "calculation":
                def progress(phase: str, completed: int, total: int) -> None:
                    if lease_lost.is_set():
                        raise JobLeaseLostError("job lease was replaced")
                    self._progress(job, {"phase": phase, "completed": completed, "total": total})

                def finalize(uow, run) -> None:
                    if run.status is CalculationRunStatus.FAILED:
                        # assert_owned fences the run failure update in this transaction.
                        uow.jobs.assert_owned(job.id, job.claim_token)
                        uow.jobs.fail(job.id, job.claim_token)
                    else:
                        uow.jobs.complete(job.id, job.claim_token, progress={"phase": "completed", "completed": 1, "total": 1})

                RunCalculation(self._factory).process(job.resource_id, progress=progress, finalize=finalize)
            elif job.kind == "import":
                self._import(job)
            else:
                raise ValueError("unsupported background job kind")
            terminal = True
        except JobLeaseLostError:
            logger.info("Stopped stale job attempt %s", job.id)
        except SQLAlchemyError as error:
            if isinstance(error, IntegrityError):
                terminal = self._record_failure(job, error)
            else:
                # Keep the saved input and running lease for recovery after transient DB loss.
                logger.error("Job %s lost database access (%s)", job.id, type(error).__name__)
        except Exception as error:
            terminal = self._record_failure(job, error)
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join()
            if terminal and job.kind == "import":
                self.spool.remove(job.resource_id)

    def _record_failure(self, job: BackgroundJob, error: Exception) -> bool:
        try:
            self._fail(job, error)
            return True
        except JobLeaseLostError:
            logger.info("Another worker owns failed attempt %s", job.id)
        except SQLAlchemyError as persistence_error:
            logger.error("Could not save failure for job %s (%s)", job.id, type(persistence_error).__name__)
        return False

    def _cleanup_spool(self) -> None:
        for path in self.spool.directory.glob("*.xlsx"):
            try:
                batch_id = UUID(path.stem)
            except ValueError:
                continue
            with self._database.session() as session:
                job = SqlAlchemyBackgroundJobRepository(session).get_for_resource("import", batch_id)
            if job is not None and job.status in {"completed", "failed"}:
                self.spool.remove(batch_id)
            elif job is None:
                try:
                    expired = path.stat().st_mtime < time.time() - 86400
                except FileNotFoundError:
                    continue
                if expired:
                    self.spool.remove(batch_id)
        for path in self.spool.directory.glob("*.tmp"):
            try:
                expired = path.stat().st_mtime < time.time() - 86400
            except FileNotFoundError:
                continue
            if expired:
                path.unlink(missing_ok=True)

    def _progress(self, job: BackgroundJob, progress: dict | None) -> None:
        with self._database.session() as session:
            SqlAlchemyBackgroundJobRepository(session).heartbeat(job.id, job.claim_token, progress=progress)

    def _import(self, job: BackgroundJob) -> None:
        with self._database.session() as session:
            jobs = SqlAlchemyBackgroundJobRepository(session)
            jobs.assert_owned(job.id, job.claim_token)
            repository = SqlAlchemyImportRepository(session)
            batch = repository.get(job.resource_id)
            if batch is None:
                raise LookupError("queued import batch was not found")
            if batch.status is ImportStatus.COMPLETED:
                jobs.complete(job.id, job.claim_token,
                              progress={"stage": "completed", "processed_rows": batch.row_count, "total_rows": batch.row_count})
                return
            if batch.status is ImportStatus.FAILED:
                jobs.fail(job.id, job.claim_token)
                return
            if batch.status is ImportStatus.PENDING:
                batch = repository.mark_processing(batch.id)
        self._progress(job, {"stage": "validating", "processed_rows": 0, "total_rows": None})
        content = self.spool.read(batch.id)
        if sha256(content).hexdigest() != batch.file_checksum:
            raise ValueError("persisted upload checksum mismatch")
        parsed = ExcelImportReader(self._ai_mapper).read(ImportFileCommand(
            source_type=batch.source_type, file_name=batch.file_name,
            content=content, imported_by=batch.imported_by,
        ))
        self._progress(job, {"stage": "persisting", "processed_rows": 0, "total_rows": len(parsed.rows)})

        def finish(session, count: int) -> None:
            SqlAlchemyBackgroundJobRepository(session).complete(job.id, job.claim_token,
                progress={"stage": "completed", "processed_rows": count, "total_rows": count})

        SqlAlchemyImportGateway(self._database.session_factory, complete_hook=finish).complete(batch, parsed)

    def _fail(self, job: BackgroundJob, error: Exception) -> None:
        with self._factory() as uow:
            uow.jobs.assert_owned(job.id, job.claim_token)
            code = getattr(error, "code", "processing_failed")
            allowed_codes = {"budget_price_missing", "budget_currency_mismatch", "budget_currency_missing", "supplier_terms_missing"}
            details = {"code": code if code in allowed_codes else "processing_failed", "error_type": type(error).__name__}
            if job.kind == "calculation":
                run = uow.calculation_runs.get(job.resource_id)
                if run is not None and run.status in {CalculationRunStatus.PENDING, CalculationRunStatus.RUNNING}:
                    run.fail(details)
                    uow.calculation_runs.save(run)
            else:
                batch = uow.imports.get(job.resource_id)
                if batch is not None and batch.status in {ImportStatus.PENDING, ImportStatus.PROCESSING}:
                    if hasattr(error, "issues"):
                        from backend.infrastructure.api.errors import safe_issues
                        details["validation_errors"] = safe_issues(error.issues)
                    uow.imports.mark_failed(batch.id, error_details=details)
            uow.jobs.fail(job.id, job.claim_token)
            uow.commit()
