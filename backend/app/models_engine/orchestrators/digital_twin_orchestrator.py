from datetime import datetime, timezone
from typing import Protocol

from backend.app.domains.decision.alert_engine import AlertEngine
from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelOutput,
    ModelRunContext,
)
from backend.app.models_engine.base.model_contract import ModelRunRepositoryProtocol
from backend.app.models_engine.orchestrators.recommendation_engine import (
    RecommendationEngine,
)
from backend.app.models_engine.orchestrators.risk_engine import RiskEngine
from backend.app.models_engine.orchestrators.schemas import (
    DigitalTwinSnapshot,
    DigitalTwinState,
)


class DigitalTwinStateProviderProtocol(Protocol):
    def load_water_quality_current(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        ...

    def load_recent_sensor_measurements(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> list[dict[str, object]]:
        ...

    def load_current_biomass(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        ...

    def load_recent_feeding(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        ...

    def load_sensor_status(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        ...


class DigitalTwinSnapshotRepositoryProtocol(Protocol):
    def save_snapshot(self, snapshot: DigitalTwinSnapshot) -> str:
        ...


class DigitalTwinOrchestrator:
    def __init__(
        self,
        model_runners: list[BaseModelRunner] | None = None,
        risk_engine: RiskEngine | None = None,
        recommendation_engine: RecommendationEngine | None = None,
        alert_engine: AlertEngine | None = None,
        state_provider: DigitalTwinStateProviderProtocol | None = None,
        snapshot_repository: DigitalTwinSnapshotRepositoryProtocol | None = None,
        model_run_repository: ModelRunRepositoryProtocol | None = None,
    ) -> None:
        self.model_runners = {
            runner.model_code: runner for runner in model_runners or []
        }
        self.risk_engine = risk_engine or RiskEngine()
        self.recommendation_engine = recommendation_engine or RecommendationEngine()
        self.alert_engine = alert_engine or AlertEngine()
        self.state_provider = state_provider
        self.snapshot_repository = snapshot_repository
        self.model_run_repository = model_run_repository

    def create_snapshot(
        self,
        pond_id: str,
        timestamp: datetime | None = None,
        model_inputs: dict[str, ModelInput] | None = None,
        model_contexts: dict[str, ModelRunContext] | None = None,
        state_overrides: dict[str, object] | None = None,
        operational_constraints: dict[str, object] | None = None,
    ) -> DigitalTwinSnapshot:
        snapshot_time = timestamp or datetime.now(timezone.utc)
        current_state = self._load_state(pond_id, snapshot_time)
        if state_overrides:
            current_state = self._apply_state_overrides(current_state, state_overrides)

        model_outputs, traceability = self._execute_models(
            pond_id=pond_id,
            timestamp=snapshot_time,
            model_inputs=model_inputs or {},
            model_contexts=model_contexts or {},
        )
        risk_assessments = self.risk_engine.assess(current_state, model_outputs)
        recommendations = self.recommendation_engine.generate(
            risk_assessments=risk_assessments,
            model_outputs=model_outputs,
            operational_constraints=operational_constraints,
        )
        alerts = self.alert_engine.build_alerts(
            risk_assessments=risk_assessments,
            recommendations=recommendations,
        )
        snapshot = DigitalTwinSnapshot(
            pond_id=pond_id,
            timestamp=snapshot_time,
            current_state=current_state,
            model_outputs=model_outputs,
            risk_assessments=risk_assessments,
            recommendations=recommendations,
            alerts=alerts,
            state_summary=self._build_state_summary(current_state),
            data_quality_report=self._build_data_quality_report(current_state),
            missing_data_report={"missing_data": current_state.missing_data},
            traceability=traceability,
        )
        if self.snapshot_repository is not None:
            saved_id = self.snapshot_repository.save_snapshot(snapshot)
            snapshot = snapshot.model_copy(update={"snapshot_id": saved_id})
        return snapshot

    def _load_state(self, pond_id: str, timestamp: datetime) -> DigitalTwinState:
        if self.state_provider is None:
            return DigitalTwinState(
                pond_id=pond_id,
                timestamp=timestamp,
                missing_data=[
                    "water_quality_current",
                    "sensor_timeseries",
                    "biomass_current",
                    "feeding_current",
                    "sensor_status",
                ],
            )

        water_quality = self.state_provider.load_water_quality_current(
            pond_id,
            timestamp,
        )
        sensor_timeseries = self.state_provider.load_recent_sensor_measurements(
            pond_id,
            timestamp,
        )
        biomass = self.state_provider.load_current_biomass(pond_id, timestamp)
        feeding = self.state_provider.load_recent_feeding(pond_id, timestamp)
        sensor_status = self.state_provider.load_sensor_status(pond_id, timestamp)
        has_mortality_loader = hasattr(self.state_provider, "load_current_mortality")
        has_events_loader = hasattr(
            self.state_provider,
            "load_recent_operational_events",
        )
        mortality = self._load_optional_state_section(
            "load_current_mortality",
            pond_id,
            timestamp,
            default={},
        )
        operational_events = self._load_optional_state_section(
            "load_recent_operational_events",
            pond_id,
            timestamp,
            default=[],
        )
        missing_data = [
            section
            for section, value in {
                "water_quality_current": water_quality,
                "sensor_timeseries": sensor_timeseries,
                "biomass_current": biomass,
                "feeding_current": feeding,
                "sensor_status": sensor_status,
            }.items()
            if not value
        ]
        if has_mortality_loader and not mortality:
            missing_data.append("mortality_current")
        if has_events_loader and not operational_events:
            missing_data.append("operational_events")
        return DigitalTwinState(
            pond_id=pond_id,
            timestamp=timestamp,
            water_quality_current=water_quality,
            sensor_timeseries=sensor_timeseries,
            biomass_current=biomass,
            feeding_current=feeding,
            mortality_current=mortality,
            sensor_status=sensor_status,
            operational_events=operational_events,
            missing_data=missing_data,
        )

    def _execute_models(
        self,
        pond_id: str,
        timestamp: datetime,
        model_inputs: dict[str, ModelInput],
        model_contexts: dict[str, ModelRunContext],
    ) -> tuple[list[ModelOutput], dict[str, object]]:
        model_outputs: list[ModelOutput] = []
        skipped: list[str] = []
        errors: list[dict[str, str]] = []

        for model_code, runner in self.model_runners.items():
            model_input = model_inputs.get(model_code)
            if model_input is None:
                skipped.append(model_code)
                continue

            context = model_contexts.get(
                model_code,
                ModelRunContext(
                    model_code=runner.model_code,
                    model_version=runner.model_version,
                    source_report=runner.source_report,
                    pond_id=pond_id,
                    timestamp=timestamp,
                    metadata={"orchestrator": "digital_twin"},
                ),
            )
            try:
                model_outputs.append(
                    runner.run(
                        model_input=model_input,
                        context=context,
                        run_repository=self.model_run_repository,
                    )
                )
            except Exception as exc:
                errors.append({"model_code": model_code, "error": str(exc)})

        return model_outputs, {
            "model_codes_registered": sorted(self.model_runners),
            "model_codes_executed": [output.model_code for output in model_outputs],
            "model_codes_skipped": skipped,
            "model_errors": errors,
            "model_run_ids": [
                output.run_id for output in model_outputs if output.run_id is not None
            ],
        }

    def _load_optional_state_section(
        self,
        loader_name: str,
        pond_id: str,
        timestamp: datetime,
        default: object,
    ) -> object:
        if self.state_provider is None or not hasattr(self.state_provider, loader_name):
            return default
        loader = getattr(self.state_provider, loader_name)
        value = loader(pond_id, timestamp)
        return value if value is not None else default

    def _apply_state_overrides(
        self,
        state: DigitalTwinState,
        overrides: dict[str, object],
    ) -> DigitalTwinState:
        updates = state.model_dump()
        for key, value in overrides.items():
            if key not in updates:
                continue
            if isinstance(updates[key], dict) and isinstance(value, dict):
                updates[key] = {**updates[key], **value}
            else:
                updates[key] = value
        return DigitalTwinState(**updates)

    def _build_state_summary(self, state: DigitalTwinState) -> dict[str, object]:
        return {
            "water_quality_variables": sorted(state.water_quality_current),
            "sensor_measurements_count": len(state.sensor_timeseries),
            "biomass_variables": sorted(state.biomass_current),
            "has_feeding_data": bool(state.feeding_current),
            "has_mortality_data": bool(state.mortality_current),
            "operational_events_count": len(state.operational_events),
            "sensor_count": len(state.sensor_status),
        }

    def _build_data_quality_report(self, state: DigitalTwinState) -> dict[str, object]:
        return {
            "missing_sections": state.missing_data,
            "sensor_status": state.sensor_status,
            "sensor_timeseries_count": len(state.sensor_timeseries),
        }
