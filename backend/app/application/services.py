from datetime import datetime, timedelta, timezone

from backend.app.application.store import InMemoryBackendStore
from backend.app.domains.digital_twin import (
    DigitalTwinModelParticipation,
    DigitalTwinProjectionPoint,
    DigitalTwinProjectionRequest,
    DigitalTwinProjectionResponse,
)
from backend.app.domains.models import (
    ModelCatalogItem,
    ModelInputAudit,
    ModelInputFieldAudit,
    ModelRunRequest,
    ModelTestPayload,
)
from backend.app.models_engine.base import (
    ModelInput,
    ModelInputValue,
    ModelOutput,
    ModelRunContext,
)
from backend.app.models_engine.deterministic.growth import (
    haskell_feed_rate,
    oxygen_factor_yi,
    soderberg_delta_l,
    temperature_factor_yi,
)
from backend.app.models_engine.orchestrators import DigitalTwinOrchestrator
from backend.app.models_engine.orchestrators.model_suite import (
    build_default_model_suite,
    default_model_codes,
)
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

    def build_test_payload(
        self,
        model_code: str,
        store: InMemoryBackendStore,
        pond_id: str | None = None,
    ) -> ModelTestPayload | None:
        runner = self.runners.get(model_code)
        if runner is None:
            return None

        audit = self.audit_inputs(model_code, store, pond_id=pond_id)
        if audit is None:
            return None

        auto_input_names: list[str] = []
        generated_input_names: list[str] = []
        inputs: dict[str, ModelInputValue] = {}
        notes: list[str] = []

        force_generated = (
            model_code == "PEARSON_LSTM_ATTENTION_WQ"
            and len(audit.auto_inputs) != len(runner.metadata.inputs)
        )
        if force_generated:
            notes.append(
                "Series temporales generadas completas para mantener ventanas alineadas."
            )

        for input_name, unit in runner.metadata.inputs.items():
            auto_input = None if force_generated else audit.auto_inputs.get(input_name)
            if auto_input is not None:
                inputs[input_name] = auto_input
                auto_input_names.append(input_name)
                continue

            sample_value = self._sample_value_for_input(input_name, unit)
            if model_code == "PEARSON_LSTM_ATTENTION_WQ" and not isinstance(
                sample_value,
                list,
            ):
                sample_value = self._sample_timeseries_for_input(input_name)

            inputs[input_name] = ModelInputValue(
                value=sample_value,
                unit=unit,
                quality_flag="generated_test_value",
            )
            generated_input_names.append(input_name)

        parameters = self._sample_parameters_for_model(model_code, audit.blocked_by)
        if generated_input_names:
            notes.append(
                "Valores generados solo para prueba de contrato; no representan medicion real."
            )
        if audit.blocked_by:
            notes.append(
                "Modelo ejecutado en modo dry_run/metadata cuando requiere artefacto externo."
            )

        request = ModelRunRequest(
            pond_id=pond_id,
            inputs=inputs,
            parameters=parameters,
        )
        if auto_input_names and not self._test_request_executes(runner, request):
            notes.append(
                "Inputs automaticos fuera del dominio de prueba; se usaron valores generados validos."
            )
            auto_input_names = []
            generated_input_names = list(runner.metadata.inputs)
            inputs = {
                input_name: ModelInputValue(
                    value=self._sample_value_for_input(input_name, unit),
                    unit=unit,
                    quality_flag="generated_test_value",
                )
                for input_name, unit in runner.metadata.inputs.items()
            }
            if model_code == "PEARSON_LSTM_ATTENTION_WQ":
                inputs = {
                    input_name: input_value.model_copy(
                        update={
                            "value": self._sample_timeseries_for_input(input_name),
                        }
                    )
                    for input_name, input_value in inputs.items()
                }
            request = ModelRunRequest(
                pond_id=pond_id,
                inputs=inputs,
                parameters=parameters,
            )

        return ModelTestPayload(
            model_code=model_code,
            pond_id=pond_id,
            readiness_status=audit.readiness_status,
            request=request,
            auto_input_names=auto_input_names,
            generated_input_names=generated_input_names,
            blocked_by=audit.blocked_by,
            test_mode="generated_with_auto_inputs" if auto_input_names else "generated",
            notes=notes,
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

    def _test_request_executes(
        self,
        runner: object,
        request: ModelRunRequest,
    ) -> bool:
        try:
            model_input = ModelInput(
                model_code=runner.model_code,
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
                metadata={"api": "models_test_payload_probe"},
            )
            runner.run(model_input=model_input, context=context)
        except (RuntimeError, ValueError):
            return False
        return True

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
    def _sample_value_for_input(input_name: str, unit: str) -> object:
        if unit.endswith("_series"):
            series_values = {
                "concentrations_mg_l": [6.4, 6.1, 5.9, 5.7],
                "saturation_mg_l": [8.6, 8.6, 8.5, 8.5],
                "biomass_kg": [20.0, 30.0, 40.0, 50.0],
            }
            return series_values.get(input_name, [1.0, 1.1, 1.2, 1.3])

        named_values: dict[str, object] = {
            "do_initial_mg_l": 6.2,
            "do_influent_mg_l": 7.0,
            "dissolved_oxygen_mg_l": 6.2,
            "do_previous_mg_l": 6.5,
            "water_temperature_c": 27.0,
            "flow_rate_l_h": 1200.0,
            "raceway_volume_l": 1280.0,
            "fish_biomass_kg": 96.0,
            "biomass_kg": 96.0,
            "fish_respiration_rate_mg_h_kg": 20.0,
            "oxygen_supply_rate_mg_l_h": 0.2,
            "reaeration_rate_h_1": 0.046,
            "simulation_horizon_minutes": 60.0,
            "q_over_area_m_h": 0.4,
            "area_m2": 12.0,
            "dx_m": 2.0,
            "dt_h": 1.0,
            "average_weight_g": 80.0,
            "average_fish_weight_g": 80.0,
            "fish_weight_g": 80.0,
            "wet_weight_g": 80.0,
            "fish_weight": 80.0,
            "fish_number": 1000,
            "fish_count": 1000,
            "stocking_density_kg_m3": 3.2,
            "volume_m3": 30.0,
            "t_min_c": 18.0,
            "t_opti_c": 28.0,
            "t_max_c": 34.0,
            "do_min_mg_l": 3.0,
            "do_crit_mg_l": 5.0,
            "k_min": 0.001,
            "s": 0.05,
            "kappa": 1.0,
            "phi": 1.0,
            "h": 1.0,
            "feeding_level": 0.8,
            "m": 0.67,
            "n": 0.8,
            "fish_length_mm": 120.0,
            "fish_length": 12.0,
            "final_weight_g": 120.0,
            "initial_weight_g": 80.0,
            "final_length_cm": 18.0,
            "days": 30.0,
            "final_fish_count": 950,
            "initial_fish_count": 1000,
            "feed_consumed_g": 30000.0,
            "feed_ration_day_1": 0.03,
            "protein_fraction": 0.42,
            "lipid_fraction": 0.14,
            "carbohydrate_fraction": 0.18,
            "protein_digestibility": 0.85,
            "lipid_digestibility": 0.92,
            "carbohydrate_digestibility": 0.55,
            "energy_content_somatic_tissue_kj_g": 5.5,
            "feed_conversion_ratio": 1.5,
            "daily_growth": 0.15,
            "feeding_behavior_category": "ACTIVE_CONTINUOUS_FEEDING",
            "feed_remaining": False,
            "fish_reaction": "active feeding response",
            "ph": [7.6, 7.7, 7.6, 7.8, 7.7, 7.7, 7.6, 7.8],
            "ammonia_nitrogen_mg_l": [0.12, 0.13, 0.12, 0.14, 0.13, 0.12, 0.13, 0.12],
            "nitrite_mg_l": [0.04, 0.05, 0.04, 0.05, 0.04, 0.04, 0.05, 0.04],
            "orp_mv": [220.0, 222.0, 221.0, 223.0, 224.0, 222.0, 221.0, 223.0],
            "turbidity_ntu": [12.0, 12.4, 12.2, 12.6, 12.5, 12.3, 12.1, 12.4],
            "image": "demo://images/fish-frame-001.jpg",
            "video_frame": "demo://video/frame-001",
            "camera_calibration": {"pixels_per_cm": 10.0, "camera_id": "demo"},
            "calibration_parameters": {"pixels_per_cm": 10.0, "camera_id": "demo"},
            "species": "tilapia",
        }
        if input_name in named_values:
            return named_values[input_name]

        unit_values: dict[str, object] = {
            "mg/L": 6.0,
            "degC": 27.0,
            "L/h": 1200.0,
            "L": 1280.0,
            "kg": 96.0,
            "mg/h/kg": 20.0,
            "mg/L/h": 0.2,
            "h^-1": 0.046,
            "min": 60.0,
            "m/h": 0.4,
            "m2": 12.0,
            "m": 2.0,
            "h": 1.0,
            "g": 80.0,
            "count": 1000,
            "m3": 30.0,
            "kg/m3": 3.2,
            "coefficient": 1.0,
            "fraction": 0.8,
            "cm/day": 0.15,
            "cm": 12.0,
            "mm": 120.0,
            "day": 30.0,
            "ratio": 1.5,
            "day^-1": 0.03,
            "kJ/g": 5.5,
            "category": "ACTIVE_CONTINUOUS_FEEDING",
            "boolean": False,
            "text": "demo",
            "pH": [7.6, 7.7, 7.6, 7.8, 7.7, 7.7, 7.6, 7.8],
            "mV": [220.0, 222.0, 221.0, 223.0, 224.0, 222.0, 221.0, 223.0],
            "NTU": [12.0, 12.4, 12.2, 12.6, 12.5, 12.3, 12.1, 12.4],
            "image_ref": "demo://images/fish-frame-001.jpg",
            "frame_ref": "demo://video/frame-001",
            "calibration_json": {"pixels_per_cm": 10.0, "camera_id": "demo"},
        }
        return unit_values.get(unit, 1.0)

    @staticmethod
    def _sample_timeseries_for_input(input_name: str) -> list[float]:
        values = {
            "water_temperature_c": [26.8, 26.9, 27.0, 27.1, 27.0, 26.9, 27.1, 27.2],
            "dissolved_oxygen_mg_l": [6.4, 6.3, 6.2, 6.1, 6.2, 6.3, 6.2, 6.1],
            "ph": [7.6, 7.7, 7.6, 7.8, 7.7, 7.7, 7.6, 7.8],
            "ammonia_nitrogen_mg_l": [0.12, 0.13, 0.12, 0.14, 0.13, 0.12, 0.13, 0.12],
            "nitrite_mg_l": [0.04, 0.05, 0.04, 0.05, 0.04, 0.04, 0.05, 0.04],
            "orp_mv": [220.0, 222.0, 221.0, 223.0, 224.0, 222.0, 221.0, 223.0],
            "turbidity_ntu": [12.0, 12.4, 12.2, 12.6, 12.5, 12.3, 12.1, 12.4],
        }
        return values.get(input_name, [1.0, 1.1, 1.2, 1.3, 1.2, 1.1, 1.0, 1.1])

    @staticmethod
    def _sample_parameters_for_model(
        model_code: str,
        blocked_by: list[str],
    ) -> dict[str, object]:
        parameters_by_model: dict[str, dict[str, object]] = {
            "DO_DYNAMIC_0D_ROYER_2021": {"dt_minutes": 1.0},
            "RAS_OXYGEN_BALANCE": {
                "feed_rate_percent_body_weight_day": 2.0,
                "bod5_mg_o2_kg_day": 2160.0,
                "pump_cycle_h": 0.5,
                "pump_frequency_h_1": 1.0,
                "pump_efficiency": 0.8,
                "oxygen_transfer_rate_g_h": 120.0,
            },
            "SODERBERG_LINEAR_GROWTH": {
                "species": "nile tilapia",
                "feed_conversion_ratio": 1.5,
            },
            "ZOOTECHNIC_INDEXES": {
                "biomass_removed_mortality_g": 500.0,
                "biomass_sampled_g": 0.0,
                "tank_to_m3_factor": 1.666,
            },
            "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010": {"dt_day": 1.0},
        }
        parameters = dict(parameters_by_model.get(model_code, {}))
        if blocked_by:
            parameters.update({"dry_run": True, "metadata_only": True})
        return parameters

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

    def project_scenario(
        self,
        pond_id: str,
        request: DigitalTwinProjectionRequest,
    ) -> DigitalTwinProjectionResponse:
        generated_at = datetime.now(timezone.utc)
        state = self.load_state(pond_id, generated_at)
        baseline = {
            code: float(value.value)
            for code, value in state.water_quality_current.items()
            if isinstance(value.value, (int, float))
        }
        latest_measurements = self.store.latest_clean_by_variable(pond_id)
        baseline_measurements = {
            code: measurement
            for code, measurement in latest_measurements.items()
            if code in baseline
        }
        trends = {
            code: self._observed_trend_per_hour(pond_id, code)
            for code in baseline
        }
        adjustments = {
            code: float(value)
            for code, value in request.variable_adjustments_per_hour.items()
            if code in baseline
        }
        participation = self._model_participation(request.selected_models)
        productive = self._productive_simulation(
            pond_id=pond_id,
            baseline=baseline,
            trends=trends,
            adjustments=adjustments,
            controls=request.operational_controls,
            horizon_hours=request.horizon_hours,
            step_hours=request.step_hours,
        )
        points = [
            DigitalTwinProjectionPoint(
                timestamp=generated_at + timedelta(hours=hour),
                hour=hour,
                values={
                    code: float(
                        productive["points"][hour]["operational_state"].get(
                            "projected_oxygen_mg_l"
                            if code == "dissolved_oxygen_mg_l"
                            else "projected_nitrate_mg_l"
                            if code == "nitrate_ion"
                            else f"projected_{code}",
                            baseline_value
                            + (trends.get(code, 0.0) + adjustments.get(code, 0.0))
                            * hour,
                        )
                    )
                    for code, baseline_value in baseline.items()
                },
                provenance={
                    code: (
                        "clean_measurements+observed_linear_trend+scenario_adjustment"
                        if code in adjustments
                        else "clean_measurements+observed_linear_trend"
                    )
                    for code in baseline
                },
                model_activity={
                    item.model_code: self._model_activity_index(
                        item,
                        hour,
                        baseline,
                        trends,
                        adjustments,
                    )
                    for item in participation
                },
                biological_state=productive["points"][hour]["biological_state"],
                operational_state=productive["points"][hour]["operational_state"],
            )
            for hour in range(0, request.horizon_hours + 1, request.step_hours)
        ]
        warnings = []
        if not baseline:
            warnings.append("No hay mediciones limpias numericas para proyectar.")
        if any(item.status != "available" for item in participation):
            warnings.append(
                "Algunos modelos seleccionados no tienen artefacto o entrada productiva disponible."
            )
        warnings.append(
            "La curva temporal es un escenario operacional basado en tendencia observada; "
            "no sustituye una inferencia cientifica del modelo cuando no existe artefacto productivo."
        )
        return DigitalTwinProjectionResponse(
            pond_id=pond_id,
            generated_at=generated_at,
            horizon_hours=request.horizon_hours,
            step_hours=request.step_hours,
            baseline_values=baseline,
            baseline_observed_at={
                code: measurement.time
                for code, measurement in baseline_measurements.items()
            },
            baseline_ingested_at={
                code: measurement.created_at
                for code, measurement in baseline_measurements.items()
            },
            baseline_units={
                code: measurement.standard_unit
                for code, measurement in baseline_measurements.items()
            },
            baseline_quality_flags={
                code: measurement.quality_flag
                for code, measurement in baseline_measurements.items()
            },
            observed_trends_per_hour=trends,
            scenario_adjustments_per_hour=adjustments,
            operational_controls=request.operational_controls,
            initial_productive_state=productive["initial_state"],
            simulation_summary=productive["summary"],
            derived_indicators=productive["derived_indicators"],
            simulation_assumptions=productive["assumptions"],
            points=points,
            model_participation=participation,
            warnings=warnings,
            traceability={
                "data_origin": "clean_measurements",
                "projection_method": "observed_linear_trend_with_explicit_scenario_adjustments",
                "generated_data_used": False,
                "decision_grade": False,
                "selected_models": [item.model_code for item in participation],
                "model_layer_semantics": "operational_activity_index_not_model_output",
                "operational_controls_semantics": "productive_simulation_inputs_with_explicit_assumptions",
                "operational_controls": request.operational_controls,
                "productive_formulas": [
                    "Soderberg daily length gain for Nile tilapia",
                    "Nile tilapia weight-length W=1.861e-8*L^3",
                    "Haskell feed rate F=(3*C*dL/L)*100",
                ],
                "derived_index_semantics": (
                    "operational_indices_are_simulation_proxies_not_direct_sensor_measurements"
                ),
            },
        )

    def _productive_simulation(
        self,
        pond_id: str,
        baseline: dict[str, float],
        trends: dict[str, float],
        adjustments: dict[str, float],
        controls: dict[str, float | bool | str],
        horizon_hours: int,
        step_hours: int,
    ) -> dict[str, object]:
        pond = self.store.get_pond(pond_id)
        fish_count = self._control_number(controls, "fish_count", 25.0, 1.0)
        initial_weight_g = self._control_number(
            controls, "average_weight_g", 120.0, 0.1
        )
        initial_length_mm = self._control_number(
            controls,
            "fish_length_cm",
            18.6 * ((initial_weight_g / 120.0) ** (1.0 / 3.0)),
            0.1,
        ) * 10.0
        volume_m3 = self._control_number(
            controls,
            "tank_volume_m3",
            float(pond.water_volume_l) / 1000.0
            if pond is not None and pond.water_volume_l
            else 10.0,
            0.1,
        )
        fcr = self._control_number(controls, "feed_conversion_ratio", 1.5, 0.1)
        feed_multiplier = self._control_number(
            controls, "feeding_percent", 100.0, 0.0
        ) / 100.0
        aeration = self._control_number(controls, "aeration_percent", 60.0, 0.0)
        filtration = self._control_number(
            controls, "filtration_percent", 50.0, 0.0
        )
        aeration_effect = self._control_number(
            controls, "aeration_do_effect_mg_l_h_at_100", 0.015, 0.0
        )
        filtration_nitrate_effect = self._control_number(
            controls, "filtration_nitrate_effect_mg_l_h_at_100", 0.02, 0.0
        )
        cleaning_events = self._control_number(
            controls, "siphon_events", 0.0, 0.0
        )
        feeding_events = self._control_number(
            controls, "feed_events", 0.0, 0.0
        )
        points: dict[int, dict[str, object]] = {}
        cumulative_feed_kg = 0.0
        previous_hour = 0
        previous_length_mm = initial_length_mm

        for hour in range(0, horizon_hours + 1, step_hours):
            elapsed_days = hour / 24.0
            elapsed_step_days = (hour - previous_hour) / 24.0
            water = {
                code: value + (trends.get(code, 0.0) + adjustments.get(code, 0.0)) * hour
                for code, value in baseline.items()
            }
            oxygen = water.get("dissolved_oxygen_mg_l", 6.0)
            oxygen += ((aeration - 50.0) / 50.0) * aeration_effect * hour
            temperature = water.get("water_temperature_c", 27.0)
            ph = water.get("ph", 7.5)
            nitrate = water.get("nitrate_ion", 10.0)
            nitrate = max(
                0.0,
                nitrate
                - ((filtration - 50.0) / 50.0)
                * filtration_nitrate_effect
                * hour,
            )
            oxygen_factor = oxygen_factor_yi(oxygen, 3.0, 5.0)
            temperature_factor = temperature_factor_yi(temperature, 20.0, 28.0, 35.0)
            ph_factor = self._range_factor(ph, 6.5, 7.0, 8.5, 9.0)
            nitrate_factor = self._descending_factor(nitrate, 20.0, 50.0)
            water_quality_index = 100.0 * min(
                oxygen_factor, temperature_factor, ph_factor, nitrate_factor
            )
            appetite_index = 100.0 * min(
                oxygen_factor, temperature_factor, ph_factor
            ) * feed_multiplier
            stress_index = 100.0 - water_quality_index

            try:
                daily_length_gain_mm = float(
                    soderberg_delta_l(temperature, "nile tilapia")[
                        "daily_length_gain_mm_day"
                    ]
                )
            except ValueError:
                daily_length_gain_mm = 0.0
            current_length_mm = initial_length_mm + daily_length_gain_mm * elapsed_days
            current_weight_g = initial_weight_g * (
                current_length_mm / initial_length_mm
            ) ** 3
            biomass_kg = current_weight_g * fish_count / 1000.0
            density_kg_m3 = biomass_kg / volume_m3
            feed_rate_percent = haskell_feed_rate(
                fcr, daily_length_gain_mm, max(current_length_mm, 0.1)
            )
            daily_feed_kg = biomass_kg * feed_rate_percent / 100.0 * feed_multiplier
            cumulative_feed_kg += daily_feed_kg * elapsed_step_days
            load_index = min(
                100.0,
                max(
                    0.0,
                    density_kg_m3 * 1.4
                    + daily_feed_kg * 18.0
                    + feeding_events * 2.0
                    - filtration * 0.55
                    - cleaning_events * 12.0,
                ),
            )
            risk_exposed_fish = fish_count * stress_index / 100.0
            behavior = (
                "critical_mortality_risk"
                if water_quality_index < 20
                else "disease_risk"
                if water_quality_index < 45
                else "stressed"
                if water_quality_index < 70
                else "feeding"
                if feeding_events > 0 and appetite_index >= 60
                else "normal"
            )
            points[hour] = {
                "biological_state": {
                    "fish_count": round(fish_count, 2),
                    "average_weight_g": round(current_weight_g, 3),
                    "fish_length_cm": round(current_length_mm / 10.0, 3),
                    "biomass_kg": round(biomass_kg, 3),
                    "density_kg_m3": round(density_kg_m3, 3),
                    "daily_length_gain_mm_day": round(daily_length_gain_mm, 4),
                    "daily_weight_gain_g_fish": round(
                        max(
                            0.0,
                            current_weight_g
                            - initial_weight_g
                            * (previous_length_mm / initial_length_mm) ** 3,
                        ),
                        4,
                    ),
                    "daily_feed_kg": round(daily_feed_kg, 4),
                    "cumulative_feed_kg": round(cumulative_feed_kg, 4),
                    "feed_conversion_ratio": round(fcr, 3),
                },
                "operational_state": {
                    "water_quality_index": round(water_quality_index, 2),
                    "appetite_index": round(appetite_index, 2),
                    "stress_index": round(stress_index, 2),
                    "organic_load_index": round(load_index, 2),
                    "fish_at_risk_proxy": round(risk_exposed_fish, 2),
                    "behavior": behavior,
                    "projected_oxygen_mg_l": round(max(0.0, oxygen), 3),
                    "projected_nitrate_mg_l": round(nitrate, 3),
                },
            }
            previous_hour = hour
            previous_length_mm = current_length_mm

        initial = points[0]["biological_state"]
        final = points[max(points)]["biological_state"]
        final_operational = points[max(points)]["operational_state"]
        return {
            "points": points,
            "initial_state": initial,
            "summary": {
                "horizon_days": round(horizon_hours / 24.0, 2),
                "final_biomass_kg": final["biomass_kg"],
                "biomass_gain_kg": round(
                    float(final["biomass_kg"]) - float(initial["biomass_kg"]), 3
                ),
                "final_average_weight_g": final["average_weight_g"],
                "feed_required_kg": final["cumulative_feed_kg"],
                "final_water_quality_index": final_operational["water_quality_index"],
                "final_behavior": final_operational["behavior"],
            },
            "derived_indicators": {
                "water_quality_index": points[0]["operational_state"]["water_quality_index"],
                "appetite_index": points[0]["operational_state"]["appetite_index"],
                "stress_index": points[0]["operational_state"]["stress_index"],
                "organic_load_index": points[0]["operational_state"]["organic_load_index"],
                "behavior": points[0]["operational_state"]["behavior"],
            },
            "assumptions": {
                "species": "nile tilapia",
                "growth_formula": "Soderberg combined 21-30 C",
                "weight_length_formula": "relative cubic Wt=W0*(Lt/L0)^3 from documented W proportional to L^3",
                "feed_formula": "Haskell F=(3*C*dL/L)*100",
                "aeration_do_effect_mg_l_h_at_100": aeration_effect,
                "filtration_nitrate_effect_mg_l_h_at_100": filtration_nitrate_effect,
                "operational_indices": "simulation proxies, not direct measurements",
                "mortality": "risk exposure only; confirmed deaths require mortality records",
            },
        }

    @staticmethod
    def _control_number(
        controls: dict[str, float | bool | str],
        name: str,
        default: float,
        minimum: float,
    ) -> float:
        try:
            return max(minimum, float(controls.get(name, default)))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _range_factor(
        value: float,
        minimum: float,
        optimal_minimum: float,
        optimal_maximum: float,
        maximum: float,
    ) -> float:
        if value <= minimum or value >= maximum:
            return 0.0
        if optimal_minimum <= value <= optimal_maximum:
            return 1.0
        if value < optimal_minimum:
            return (value - minimum) / (optimal_minimum - minimum)
        return (maximum - value) / (maximum - optimal_maximum)

    @staticmethod
    def _descending_factor(value: float, optimal_maximum: float, maximum: float) -> float:
        if value <= optimal_maximum:
            return 1.0
        if value >= maximum:
            return 0.0
        return (maximum - value) / (maximum - optimal_maximum)

    @staticmethod
    def _model_activity_index(
        participation: DigitalTwinModelParticipation,
        hour: int,
        baseline: dict[str, float],
        trends: dict[str, float],
        adjustments: dict[str, float],
    ) -> float:
        if participation.influence_weight <= 0:
            return 0.0
        impacted = [
            code
            for code in participation.impact_variables
            if code in baseline
        ]
        if not impacted:
            return round(participation.influence_weight * 85, 2)
        relative_changes = [
            abs((trends.get(code, 0.0) + adjustments.get(code, 0.0)) * hour)
            / max(abs(baseline[code]), 1.0)
            for code in impacted
        ]
        scenario_relevance = min(sum(relative_changes) / len(relative_changes), 1.0)
        return round(
            min(100.0, participation.influence_weight * 85 + scenario_relevance * 15),
            2,
        )

    def _observed_trend_per_hour(self, pond_id: str, variable_code: str) -> float:
        measurements = sorted(
            self.store.list_clean_measurements(
                pond_id=pond_id,
                variable_code=variable_code,
                limit=48,
            ),
            key=lambda item: item.time,
        )
        if len(measurements) < 2:
            return 0.0
        first = measurements[0]
        last = measurements[-1]
        elapsed_hours = (last.time - first.time).total_seconds() / 3600
        if elapsed_hours <= 0:
            return 0.0
        return float(last.clean_value - first.clean_value) / elapsed_hours

    def _model_participation(
        self,
        selected_models: list[str],
    ) -> list[DigitalTwinModelParticipation]:
        deterministic_impacts = {
            "DO_DYNAMIC_0D_ROYER_2021": ["dissolved_oxygen_mg_l"],
            "DO_TRANSPORT_1D": ["dissolved_oxygen_mg_l"],
            "RAS_OXYGEN_BALANCE": ["dissolved_oxygen_mg_l"],
            "PEARSON_LSTM_ATTENTION_WQ": [
                "dissolved_oxygen_mg_l",
                "water_temperature_c",
                "ph",
            ],
            "YI_ENVIRONMENTAL_GROWTH": ["water_temperature_c", "dissolved_oxygen_mg_l"],
            "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010": [
                "water_temperature_c",
                "dissolved_oxygen_mg_l",
            ],
            "FEEDING_SATIETY_RULES": ["dissolved_oxygen_mg_l", "water_temperature_c"],
        }
        active_assets = {
            asset.model_code: asset
            for asset in self.store.list_model_assets(status="active")
        }
        requires_artifact = {
            "BPNN_MEA_FEED_INTAKE",
            "FISH_COUNTING_MODEL",
            "FISH_SIZE_WEIGHT_ESTIMATION",
            "PEARSON_LSTM_ATTENTION_WQ",
        }
        available_codes = set(default_model_codes()) | set(active_assets)
        requested = selected_models or sorted(available_codes)
        result = []
        for model_code in requested:
            asset = active_assets.get(model_code)
            if model_code not in available_codes:
                status = "unavailable"
            elif model_code in requires_artifact and asset is None:
                status = "registered_requires_artifact"
            else:
                status = "available"
            influence_weight = (
                1.0
                if status == "available"
                else 0.45
                if status == "registered_requires_artifact"
                else 0.0
            )
            result.append(
                DigitalTwinModelParticipation(
                    model_code=model_code,
                    status=status,
                    impact_variables=deterministic_impacts.get(model_code, []),
                    influence_weight=influence_weight,
                    explanation=(
                        "Disponible para contexto y trazabilidad del escenario."
                        if status == "available"
                        else "Runner registrado, pero requiere artefacto entrenado activo."
                        if status == "registered_requires_artifact"
                        else "No existe runner registrado ni artefacto activo."
                    ),
                    asset_id=asset.asset_id if asset else None,
                )
            )
        return result
