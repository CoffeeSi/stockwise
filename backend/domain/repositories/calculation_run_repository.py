from typing import Protocol
from uuid import UUID

from backend.domain.entities.calculation_run import CalculationRun
from backend.domain.entities.enums import CalculationRunStatus
from backend.domain.entities.demand_forecast import DemandForecast
from backend.domain.entities.detected_anomaly import DetectedAnomaly
from backend.domain.value_objects.analytics import Outlier


class CalculationRunRepository(Protocol):
    def get(self, run_id: UUID) -> CalculationRun | None: ...

    def list_runs(
        self, *, status: CalculationRunStatus | None = None,
        warehouse_id: UUID | None = None, category_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[CalculationRun], int]: ...

    def add(self, run: CalculationRun) -> None: ...

    def save(self, run: CalculationRun) -> None: ...

    def add_results(
        self,
        forecasts: list[DemandForecast],
        anomalies: list[DetectedAnomaly],
    ) -> None: ...

    def get_forecast(
        self, run_id: UUID, product_id: UUID, warehouse_id: UUID
    ) -> DemandForecast | None: ...

    def list_forecasts(self, run_id: UUID) -> list[DemandForecast]: ...

    def list_outliers(
        self, run_id: UUID, *, supplier_id: UUID | None = None,
        product_id: UUID | None = None, warehouse_id: UUID | None = None,
        category_id: UUID | None = None,
        limit: int = 50, offset: int = 0,
    ) -> tuple[list[Outlier], int]: ...

    def list_anomalies(
        self, run_id: UUID, product_id: UUID, warehouse_id: UUID
    ) -> list[DetectedAnomaly]: ...
