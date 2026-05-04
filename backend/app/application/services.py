from datetime import datetime, timezone

from backend.app.application.store import InMemoryBackendStore
from backend.app.domains.models import ModelCatalogItem, ModelRunRequest
from backend.app.models_engine.base import (
    ModelInput,
    ModelInputValue,
    ModelOutput,
    ModelRunContext,
)
from backend.app.models_engine.orchestrators import DigitalTwinOrchestrator
from backend.app.models_engine.orchestrators.model_suite import build_default_model_suite
from backend.app.models_engine.orchestrators.schemas import (
    DigitalTwinSnapshot,
    DigitalTwinState,
)


BIOMASS_VARIABLES = {
    "biomass_kg",
    "average_weight_g",
    "fish_weight_g",
    "fish_length_cm",
    "fish_count",
}
FEEDING_VARIABLES = {
    "feed_amount_g",
    "feed_amount_kg",
    "feed_amount_g_day",
    "daily_ration_g_day",
}


class ModelCatalogService:
    def __init__(self) -> None:
        self.runners = {
            runner.model_code: runner for runner in build_default_model_suite()
        }

    def list_models(self) -> list[ModelCatalogItem]:
        return [self._to_catalog_item(runner) for runner in self.runners.values()]

    def get_model(self, model_code: str) -> ModelCatalogItem | None:
        runner = self.runners.get(model_code)
        if runner is None:
            return None
        return self._to_catalog_item(runner)

    def run_model(self, model_code: str, request: ModelRunRequest) -> ModelOutput:
        runner = self.runners.get(model_code)
        if runner is None:
            raise KeyError(model_code)

        model_input = ModelInput(
            model_code=model_code,
            timestamp=request.timestamp,
            pond_id=request.pond_id,
            farm_id=request.farm_id,
            inputs=request.inputs,
            parameters=request.parameters,
        )
        context = ModelRunContext(
            model_code=runner.model_code,
            model_version=runner.model_version,
            source_report=runner.source_report,
            pond_id=request.pond_id,
            timestamp=request.timestamp,
            metadata={"api": "models_run"},
        )
        return runner.run(model_input=model_input, context=context)

    def _to_catalog_item(self, runner: object) -> ModelCatalogItem:
        metadata = runner.metadata
        return ModelCatalogItem(
            model_code=metadata.model_code,
            model_version=metadata.model_version,
            model_type=metadata.model_type,
            name=metadata.name,
            source_report=metadata.source_report,
            source_reference=metadata.source_reference,
            inputs=metadata.inputs,
            outputs=metadata.outputs,
            units=metadata.units,
            assumptions=metadata.assumptions,
            readiness_status=self._readiness_status(runner),
        )

    @staticmethod
    def _readiness_status(runner: object) -> str:
        module_name = runner.__class__.__module__
        if "ml" in module_name or "vision" in module_name:
            return "requires_external_artifact"
        if getattr(runner, "formula_pending", None):
            return "metadata_or_dry_run_only"
        return "ready"


class StoreBackedDigitalTwinStateProvider:
    def __init__(self, store: InMemoryBackendStore) -> None:
        self.store = store

    def load_water_quality_current(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, ModelInputValue]:
        latest = self.store.latest_clean_by_variable(pond_id)
        return {
            variable_code: self._to_input_value(row)
            for variable_code, row in latest.items()
            if variable_code not in BIOMASS_VARIABLES | FEEDING_VARIABLES
        }

    def load_recent_sensor_measurements(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> list[dict[str, object]]:
        return [
            row.model_dump(mode="json")
            for row in self.store.list_clean_measurements(pond_id=pond_id, limit=200)
        ]

    def load_current_biomass(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, ModelInputValue]:
        latest = self.store.latest_clean_by_variable(pond_id)
        return {
            variable_code: self._to_input_value(row)
            for variable_code, row in latest.items()
            if variable_code in BIOMASS_VARIABLES
        }

    def load_recent_feeding(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        latest = self.store.latest_clean_by_variable(pond_id)
        return {
            variable_code: row.model_dump(mode="json")
            for variable_code, row in latest.items()
            if variable_code in FEEDING_VARIABLES
        }

    def load_sensor_status(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        return {
            sensor.sensor_code: sensor.status
            for sensor in self.store.list_sensors(pond_id=pond_id)
        }

    @staticmethod
    def _to_input_value(row: object) -> ModelInputValue:
        return ModelInputValue(
            value=row.clean_value,
            unit=row.standard_unit,
            source_measurement_id=None,
            quality_flag=row.quality_flag,
        )


class DigitalTwinApplicationService:
    def __init__(self, store: InMemoryBackendStore) -> None:
        self.store = store

    def load_state(
        self,
        pond_id: str,
        timestamp: datetime | None = None,
    ) -> DigitalTwinState:
        state_time = timestamp or datetime.now(timezone.utc)
        provider = StoreBackedDigitalTwinStateProvider(self.store)
        orchestrator = DigitalTwinOrchestrator(state_provider=provider)
        return orchestrator._load_state(pond_id, state_time)

    def create_snapshot(
        self,
        pond_id: str,
        timestamp: datetime | None = None,
        state_overrides: dict[str, object] | None = None,
        model_inputs: dict[str, ModelInput] | None = None,
        operational_constraints: dict[str, object] | None = None,
    ) -> DigitalTwinSnapshot:
        provider = StoreBackedDigitalTwinStateProvider(self.store)
        orchestrator = DigitalTwinOrchestrator(
            model_runners=build_default_model_suite(),
            state_provider=provider,
        )
        snapshot = orchestrator.create_snapshot(
            pond_id=pond_id,
            timestamp=timestamp,
            state_overrides=state_overrides,
            model_inputs=model_inputs,
            operational_constraints=operational_constraints,
        )
        return self.store.save_snapshot(snapshot)
