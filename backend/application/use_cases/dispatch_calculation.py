import json
from dataclasses import asdict
from hashlib import sha256

from backend.application.dto.calculation import RunCalculationCommand
from backend.application.ports.unit_of_work import UnitOfWorkFactory
from backend.application.use_cases.run_calculation import RunCalculation
from backend.domain.entities.background_job import BackgroundJob, IdempotencyConflictError
from backend.domain.entities.calculation_run import CalculationRun


class DispatchCalculation:
    def __init__(self, factory: UnitOfWorkFactory) -> None:
        self._factory = factory

    def execute(self, command: RunCalculationCommand, *, idempotency_key: str) -> CalculationRun:
        if not idempotency_key.strip() or len(idempotency_key) > 128:
            raise ValueError("idempotency key must contain 1..128 characters")
        fingerprint = sha256(json.dumps(asdict(command), sort_keys=True, default=str).encode()).hexdigest()
        with self._factory() as uow:
            existing = uow.jobs.get_for_key("calculation", command.user_id, idempotency_key)
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise IdempotencyConflictError("idempotency key already belongs to another request")
                run = uow.calculation_runs.get(existing.resource_id)
                if run is None:
                    raise LookupError("queued calculation run was not found")
                return run
            run = RunCalculation(self._factory).prepare(command, uow)
            uow.calculation_runs.add(run)
            uow.jobs.add(BackgroundJob(kind="calculation", resource_id=run.id, created_by=command.user_id,
                                      request_fingerprint=fingerprint, idempotency_key=idempotency_key,
                                      progress={"phase": "pending", "completed": 0, "total": 1}))
            uow.commit()
        return run
