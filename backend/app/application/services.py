from datetime import datetime, timezone

from backend.app.application.store import InMemoryBackendStore
from backend.app.domains.models import (
    ModelCatalogItem,
    ModelInputAudit,
    ModelInputFieldAudit,
    ModelRunRequest,
)
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
    "feed_kg",
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

    def audit_inputs(
        self,
        model_code: str,
        store: InMemoryBackendStore,
        pond_id: str | None = None,
    ) -> ModelInputAudit | None:
        runner = self.runners.get(model_code)
        if runner is None:
            return None

        readiness_status = self._readiness_status(runner)
        auto_inputs = self._auto_inputs_for_runner(runner, store, pond_id)
        form_fields: list[ModelInputFieldAudit] = []
        missing_inputs: list[str] = []

        for input_name, unit in runner.metadata.inputs.items():
            auto_input = auto_inputs.get(input_name)
            if auto_input is None:
                missing_inputs.append(input_name)
            form_fields.append(
                ModelInputFieldAudit(
                    input_name=input_name,
                    unit=unit,
                    status="auto_available" if auto_input is not None else "form_required",
                    control=self._control_for_input(model_code, input_name, unit),
                    source=self._source_for_input(input_name) if auto_input else None,
                    value_preview=self._value_preview(auto_input) if auto_input else None,
                    options=self._options_for_input(input_name),
                    note=self._note_for_input(model_code, input_name, auto_input is not None),
                )
            )

        blocked_by: list[str] = []
        if readiness_status == "requires_external_artifact":
            blocked_by.append("trained_artifact_pending")
        if readiness_status == "metadata_or_dry_run_only":
            blocked_by.append("formula_pending_extraction")

        can_run_now = not missing_inputs and not blocked_by
        can_run_dry_run = not missing_inputs and bool(blocked_by)
        if can_run_now:
            frontend_status = "ready"
        elif missing_inputs and blocked_by:
            frontend_status = "needs_form_inputs_and_model_asset_or_formula"
        elif missing_inputs:
            frontend_status = "needs_form_inputs"
        else:
            frontend_status = "blocked_by_model_readiness"

        return ModelInputAudit(
            model_code=model_code,
            readiness_status=readiness_status,
            pond_id=pond_id,
            can_run_now=can_run_now,
            can_run_dry_run=can_run_dry_run,
            auto_inputs=auto_inputs,
            form_fields=form_fields,
            missing_inputs=missing_inputs,
            blocked_by=blocked_by,
            frontend_status=frontend_status,
        )

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

    def _auto_inputs_for_runner(
        self,
        runner: object,
        store: InMemoryBackendStore,
        pond_id: str | None,
    ) -> dict[str, ModelInputValue]:
        if pond_id is None:
            return {}
        if runner.model_code == "PEARSON_LSTM_ATTENTION_WQ":
            return self._auto_timeseries_inputs(runner, store, pond_id)

        latest = store.latest_clean_by_variable(pond_id)
        pond = store.get_pond(pond_id)
        auto_inputs: dict[str, ModelInputValue] = {}
        for input_name, unit in runner.metadata.inputs.items():
            row = self._latest_measurement_for_input(input_name, latest)
            if row is not None and row.standard_unit == unit:
                auto_inputs[input_name] = ModelInputValue(
                    value=row.clean_value,
                    unit=unit,
                    quality_flag=row.quality_flag,
                )
                continue
            if input_name == "raceway_volume_l" and pond and pond.water_volume_l:
                if pond.water_volume_l > 0:
                    auto_inputs[input_name] = ModelInputValue(
                        value=pond.water_volume_l,
                        unit=unit,
                        quality_flag="pond_metadata",
                    )
        return auto_inputs

    def _auto_timeseries_inputs(
        self,
        runner: object,
        store: InMemoryBackendStore,
        pond_id: str,
    ) -> dict[str, ModelInputValue]:
        auto_inputs: dict[str, ModelInputValue] = {}
        for input_name, unit in runner.metadata.inputs.items():
            variable_code = self._measurement_variable_for_input(input_name)
            if variable_code is None:
                continue
            rows = store.list_clean_measurements(
                pond_id=pond_id,
                variable_code=variable_code,
                limit=96,
            )
            rows = sorted(rows, key=lambda row: row.time)
            if rows and all(row.standard_unit == unit for row in rows):
                auto_inputs[input_name] = ModelInputValue(
                    value=[row.clean_value for row in rows],
                    unit=unit,
                    quality_flag="timeseries",
                )
        return auto_inputs

    @staticmethod
    def _latest_measurement_for_input(
        input_name: str,
        latest: dict[str, object],
    ) -> object | None:
        variable_code = ModelCatalogService._measurement_variable_for_input(input_name)
        if variable_code is None:
            return None
        return latest.get(variable_code)

    @staticmethod
    def _measurement_variable_for_input(input_name: str) -> str | None:
        aliases = {
            "do_initial_mg_l": "dissolved_oxygen_mg_l",
            "wet_weight_g": "fish_weight_g",
            "average_fish_weight_g": "average_weight_g",
            "fish_number": "fish_count",
            "fish_length": "fish_length_cm",
            "fish_weight": "fish_weight_g",
        }
        return aliases.get(input_name, input_name)

    @staticmethod
    def _control_for_input(model_code: str, input_name: str, unit: str) -> str:
        if model_code == "PEARSON_LSTM_ATTENTION_WQ":
            return "timeseries"
        if unit == "boolean":
            return "checkbox"
        if unit == "category":
            return "select"
        if unit == "calibration_json":
            return "json_editor"
        if unit in {"image_ref", "frame_ref"}:
            return "media_reference"
        if unit == "text":
            return "text"
        return "number"

    @staticmethod
    def _options_for_input(input_name: str) -> list[str]:
        if input_name == "feeding_behavior_category":
            return [
                "ACTIVE_CONTINUOUS_FEEDING",
                "MOVE_AND_RETURN",
                "ONLY_FRONT_FEEDING",
                "NO_REACTION",
            ]
        if input_name == "species":
            return ["tilapia"]
        return []

    @staticmethod
    def _source_for_input(input_name: str) -> str:
        if input_name == "raceway_volume_l":
            return "pond.water_volume_l"
        variable_code = ModelCatalogService._measurement_variable_for_input(input_name)
        if variable_code == input_name:
            return f"clean_measurements.{variable_code}"
        return f"clean_measurements.{variable_code}"

    @staticmethod
    def _value_preview(input_value: ModelInputValue) -> object:
        if isinstance(input_value.value, list):
            return {
                "points": len(input_value.value),
                "last_value": input_value.value[-1] if input_value.value else None,
            }
        return input_value.value

    @staticmethod
    def _note_for_input(
        model_code: str,
        input_name: str,
        is_auto_available: bool,
    ) -> str | None:
        if is_auto_available:
            return None
        if model_code in {"FISH_COUNTING_MODEL", "FISH_SIZE_WEIGHT_ESTIMATION"}:
            return "Requiere referencia de imagen/frame, calibracion y artefacto de vision."
        if model_code == "PEARSON_LSTM_ATTENTION_WQ":
            return "Requiere serie temporal alineada y artefacto LSTM."
        if input_name in {
            "feed_conversion_ratio",
            "daily_growth",
            "feed_ration_day_1",
            "protein_fraction",
            "lipid_fraction",
            "carbohydrate_fraction",
            "protein_digestibility",
            "lipid_digestibility",
            "carbohydrate_digestibility",
            "energy_content_somatic_tissue_kj_g",
        }:
            return "Debe capturarse en formulario operativo."
        return None

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
