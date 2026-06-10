from datetime import datetime, timezone
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from backend.app.domains.actuation.schemas import (
    ActuationCommandDraft,
    ActuatorRead,
)
from backend.app.domains.aquaculture import (
    FarmCreate,
    FarmRead,
    PondCreate,
    PondRead,
    SensorCreate,
    SensorRead,
)
from backend.app.domains.decision.schemas import AlertRead, RecommendationRead
from backend.app.domains.digital_twin import RasOperationalEventCreate, RasOperationalEventRead
from backend.app.domains.measurements import (
    CleanMeasurementRead,
    MeasurementIngestionResult,
    RawMeasurementCreate,
    RawMeasurementRead,
)
from backend.app.domains.ml_lifecycle import (
    CleaningRunRead,
    FeatureSetRead,
    ModelAssetRead,
    ModelAssetPredictionHistoryRead,
    TrainingJobEventRead,
    TrainingJobRead,
)
from backend.app.models_engine.base import ModelOutput
from backend.app.models_engine.orchestrators.schemas import DigitalTwinSnapshot


class InMemoryBackendStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.farms: dict[str, FarmRead] = {}
        self.ponds: dict[str, PondRead] = {}
        self.sensors: dict[str, SensorRead] = {}
        self.raw_measurements: dict[str, RawMeasurementRead] = {}
        self.clean_measurements: dict[str, CleanMeasurementRead] = {}
        self.snapshots: dict[str, DigitalTwinSnapshot] = {}
        self.model_outputs: dict[str, ModelOutput] = {}
        self.actuators: dict[str, ActuatorRead] = {}
        self.commands: dict[str, ActuationCommandDraft] = {}
        self.cleaning_runs: dict[str, CleaningRunRead] = {}
        self.feature_sets: dict[str, FeatureSetRead] = {}
        self.training_jobs: dict[str, TrainingJobRead] = {}
        self.training_job_events: dict[str, list[TrainingJobEventRead]] = {}
        self.model_assets: dict[str, ModelAssetRead] = {}
        self.model_asset_predictions: dict[str, ModelAssetPredictionHistoryRead] = {}
        self.ras_operational_events: dict[str, RasOperationalEventRead] = {}

    def create_farm(self, payload: FarmCreate) -> FarmRead:
        with self._lock:
            self._ensure_unique_code(self.farms.values(), "code", payload.code)
            farm = FarmRead(id=self._new_id("FARM"), **payload.model_dump())
            self.farms[farm.id] = farm
            return farm

    def list_farms(self) -> list[FarmRead]:
        with self._lock:
            return list(self.farms.values())

    def get_farm(self, farm_id: str) -> FarmRead | None:
        with self._lock:
            return self.farms.get(farm_id)

    def create_pond(self, payload: PondCreate) -> PondRead:
        with self._lock:
            if payload.farm_id not in self.farms:
                raise ValueError("farm_id does not exist")
            self._ensure_unique_code(self.ponds.values(), "code", payload.code)
            pond = PondRead(id=self._new_id("POND"), **payload.model_dump())
            self.ponds[pond.id] = pond
            return pond

    def list_ponds(self, farm_id: str | None = None) -> list[PondRead]:
        with self._lock:
            ponds = list(self.ponds.values())
        if farm_id is None:
            return ponds
        return [pond for pond in ponds if pond.farm_id == farm_id]

    def get_pond(self, pond_id: str) -> PondRead | None:
        with self._lock:
            return self.ponds.get(pond_id)

    def create_sensor(self, payload: SensorCreate) -> SensorRead:
        with self._lock:
            if payload.farm_id not in self.farms:
                raise ValueError("farm_id does not exist")
            if payload.pond_id is not None and payload.pond_id not in self.ponds:
                raise ValueError("pond_id does not exist")
            self._ensure_unique_code(
                self.sensors.values(),
                "sensor_code",
                payload.sensor_code,
            )
            sensor = SensorRead(id=self._new_id("SENSOR"), **payload.model_dump())
            self.sensors[sensor.id] = sensor
            return sensor

    def list_sensors(self, pond_id: str | None = None) -> list[SensorRead]:
        with self._lock:
            sensors = list(self.sensors.values())
        if pond_id is None:
            return sensors
        return [sensor for sensor in sensors if sensor.pond_id == pond_id]

    def get_sensor(self, sensor_id: str) -> SensorRead | None:
        with self._lock:
            return self.sensors.get(sensor_id)

    def ingest_measurement(
        self,
        payload: RawMeasurementCreate,
    ) -> MeasurementIngestionResult:
        with self._lock:
            if payload.farm_id not in self.farms:
                raise ValueError("farm_id does not exist")
            if payload.pond_id is not None and payload.pond_id not in self.ponds:
                raise ValueError("pond_id does not exist")
            if payload.sensor_id is not None and payload.sensor_id not in self.sensors:
                raise ValueError("sensor_id does not exist")

            raw = RawMeasurementRead(id=self._new_id("RAW"), **payload.model_dump())
            self.raw_measurements[raw.id] = raw

            warnings: list[str] = []
            clean = None
            if raw.raw_value is None:
                warnings.append("raw_value is null; clean measurement was not generated.")
            else:
                clean = CleanMeasurementRead(
                    id=self._new_id("CLEAN"),
                    raw_measurement_id=raw.id,
                    time=raw.time,
                    farm_id=raw.farm_id,
                    pond_id=raw.pond_id,
                    sensor_id=raw.sensor_id,
                    variable_code=raw.variable_code,
                    clean_value=raw.raw_value,
                    standard_unit=raw.raw_unit or "unknown",
                    quality_flag="valid",
                    validation_status="accepted",
                    cleaning_method="pass_through_no_unit_conversion",
                )
                self.clean_measurements[clean.id] = clean

            return MeasurementIngestionResult(
                raw_measurement=raw,
                clean_measurement=clean,
                warnings=warnings,
            )

    def list_raw_measurements(
        self,
        pond_id: str | None = None,
        variable_code: str | None = None,
        limit: int = 100,
    ) -> list[RawMeasurementRead]:
        with self._lock:
            rows = list(self.raw_measurements.values())
        rows = self._filter_measurements(rows, pond_id, variable_code)
        return rows[-limit:]

    def list_clean_measurements(
        self,
        pond_id: str | None = None,
        variable_code: str | None = None,
        limit: int = 100,
    ) -> list[CleanMeasurementRead]:
        with self._lock:
            rows = list(self.clean_measurements.values())
        rows = self._filter_measurements(rows, pond_id, variable_code)
        return rows[-limit:]

    def latest_clean_by_variable(self, pond_id: str) -> dict[str, CleanMeasurementRead]:
        rows = self.list_clean_measurements(pond_id=pond_id, limit=1000)
        latest: dict[str, CleanMeasurementRead] = {}
        for row in sorted(rows, key=lambda item: item.time):
            latest[row.variable_code] = row
        return latest

    def save_snapshot(self, snapshot: DigitalTwinSnapshot) -> DigitalTwinSnapshot:
        with self._lock:
            self.snapshots[snapshot.snapshot_id] = snapshot
            return snapshot

    def get_snapshot(self, snapshot_id: str) -> DigitalTwinSnapshot | None:
        with self._lock:
            return self.snapshots.get(snapshot_id)

    def latest_snapshot(self, pond_id: str) -> DigitalTwinSnapshot | None:
        with self._lock:
            snapshots = [
                snapshot
                for snapshot in self.snapshots.values()
                if snapshot.pond_id == pond_id
            ]
        if not snapshots:
            return None
        return max(snapshots, key=lambda snapshot: snapshot.timestamp)

    def save_ras_operational_event(
        self,
        pond_id: str,
        payload: RasOperationalEventCreate,
    ) -> RasOperationalEventRead:
        now = self._now()
        event = RasOperationalEventRead(
            event_id=self._new_id("RAS-EVENT"),
            pond_id=pond_id,
            event_type=payload.event_type,
            event_time=payload.event_time or now,
            amount_kg=payload.amount_kg,
            operator=payload.operator,
            notes=payload.notes,
            details=payload.details,
            created_at=now,
        )
        with self._lock:
            self.ras_operational_events[event.event_id] = event
        return event

    def list_ras_operational_events(
        self,
        pond_id: str,
        limit: int = 50,
    ) -> list[RasOperationalEventRead]:
        with self._lock:
            events = [
                event
                for event in self.ras_operational_events.values()
                if event.pond_id == pond_id
            ]
        return sorted(events, key=lambda event: event.event_time, reverse=True)[:limit]

    def list_alerts(
        self,
        pond_id: str | None = None,
        severity: str | None = None,
    ) -> list[AlertRead]:
        alerts: list[AlertRead] = []
        with self._lock:
            snapshots = list(self.snapshots.values())
        for snapshot in snapshots:
            if pond_id is not None and snapshot.pond_id != pond_id:
                continue
            for alert in snapshot.alerts:
                if severity is not None and alert.severity != severity:
                    continue
                alerts.append(
                    AlertRead(
                        id=f"{snapshot.snapshot_id}:{alert.alert_code}",
                        snapshot_id=snapshot.snapshot_id,
                        pond_id=snapshot.pond_id,
                        **alert.model_dump(),
                    )
                )
        return alerts

    def list_recommendations(
        self,
        pond_id: str | None = None,
        priority: str | None = None,
    ) -> list[RecommendationRead]:
        recommendations: list[RecommendationRead] = []
        with self._lock:
            snapshots = list(self.snapshots.values())
        for snapshot in snapshots:
            if pond_id is not None and snapshot.pond_id != pond_id:
                continue
            for recommendation in snapshot.recommendations:
                if priority is not None and recommendation.priority != priority:
                    continue
                recommendations.append(
                    RecommendationRead(
                        id=f"{snapshot.snapshot_id}:{recommendation.recommendation_code}",
                        snapshot_id=snapshot.snapshot_id,
                        pond_id=snapshot.pond_id,
                        **recommendation.model_dump(),
                    )
                )
        return recommendations

    def get_recommendation(self, recommendation_code: str) -> RecommendationRead | None:
        for recommendation in self.list_recommendations():
            if recommendation.recommendation_code == recommendation_code:
                return recommendation
        return None

    def create_actuator(self, payload: ActuatorRead) -> ActuatorRead:
        with self._lock:
            self._ensure_unique_code(
                self.actuators.values(),
                "actuator_code",
                payload.actuator_code,
            )
            self.actuators[payload.id] = payload
            return payload

    def list_actuators(self, pond_id: str | None = None) -> list[ActuatorRead]:
        with self._lock:
            actuators = list(self.actuators.values())
        if pond_id is None:
            return actuators
        return [actuator for actuator in actuators if actuator.pond_id == pond_id]

    def get_actuator(self, actuator_id: str) -> ActuatorRead | None:
        with self._lock:
            return self.actuators.get(actuator_id)

    def save_command(self, command: ActuationCommandDraft) -> ActuationCommandDraft:
        with self._lock:
            command_id = self._new_id("COMMAND")
            stored_command = command.model_copy(
                update={
                    "command_id": command_id,
                    "audit_record": {
                        **command.audit_record,
                        "command_id": command_id,
                    }
                }
            )
            self.commands[command_id] = stored_command
            return stored_command

    def list_commands(self) -> list[ActuationCommandDraft]:
        with self._lock:
            return list(self.commands.values())

    def save_model_output(self, output: ModelOutput) -> ModelOutput:
        with self._lock:
            run_id = self._new_id("RUN")
            stored_output = output.model_copy(
                update={
                    "run_id": run_id,
                    "traceability": {
                        **output.traceability,
                        "model_run_id": run_id,
                    },
                }
            )
            self.model_outputs[run_id] = stored_output
            return stored_output

    def list_model_outputs(
        self,
        model_code: str | None = None,
        limit: int = 100,
    ) -> list[ModelOutput]:
        with self._lock:
            outputs = list(self.model_outputs.values())
        if model_code is not None:
            outputs = [output for output in outputs if output.model_code == model_code]
        return list(reversed(outputs[-limit:]))

    def save_clean_measurements(
        self,
        rows: list[CleanMeasurementRead],
        overwrite_ids: bool = False,
    ) -> list[CleanMeasurementRead]:
        with self._lock:
            for row in rows:
                if overwrite_ids or row.id not in self.clean_measurements:
                    self.clean_measurements[row.id] = row
            return rows

    def save_cleaning_run(self, cleaning_run: CleaningRunRead) -> CleaningRunRead:
        with self._lock:
            self.cleaning_runs[cleaning_run.run_id] = cleaning_run
            return cleaning_run

    def get_cleaning_run(self, run_id: str) -> CleaningRunRead | None:
        with self._lock:
            return self.cleaning_runs.get(run_id)

    def list_cleaning_runs(self) -> list[CleaningRunRead]:
        with self._lock:
            return sorted(
                self.cleaning_runs.values(),
                key=lambda run: run.started_at,
                reverse=True,
            )

    def save_feature_set(self, feature_set: FeatureSetRead) -> FeatureSetRead:
        with self._lock:
            self.feature_sets[feature_set.feature_set_id] = feature_set
            return feature_set

    def get_feature_set(self, feature_set_id: str) -> FeatureSetRead | None:
        with self._lock:
            return self.feature_sets.get(feature_set_id)

    def list_feature_sets(self) -> list[FeatureSetRead]:
        with self._lock:
            return sorted(
                self.feature_sets.values(),
                key=lambda feature_set: feature_set.created_at,
                reverse=True,
            )

    def save_training_job(self, job: TrainingJobRead) -> TrainingJobRead:
        with self._lock:
            self.training_jobs[job.job_id] = job
            return job

    def get_training_job(self, job_id: str) -> TrainingJobRead | None:
        with self._lock:
            return self.training_jobs.get(job_id)

    def list_training_jobs(self) -> list[TrainingJobRead]:
        with self._lock:
            return sorted(
                self.training_jobs.values(),
                key=lambda job: job.requested_at,
                reverse=True,
            )

    def append_training_job_event(
        self,
        event: TrainingJobEventRead,
    ) -> TrainingJobEventRead:
        with self._lock:
            self.training_job_events.setdefault(event.job_id, []).append(event)
            return event

    def list_training_job_events(self, job_id: str) -> list[TrainingJobEventRead]:
        with self._lock:
            return list(self.training_job_events.get(job_id, []))

    def save_model_asset(self, asset: ModelAssetRead) -> ModelAssetRead:
        with self._lock:
            self.model_assets[asset.asset_id] = asset
            return asset

    def get_model_asset(self, asset_id: str) -> ModelAssetRead | None:
        with self._lock:
            return self.model_assets.get(asset_id)

    def list_model_assets(
        self,
        model_code: str | None = None,
        status: str | None = None,
    ) -> list[ModelAssetRead]:
        with self._lock:
            assets = list(self.model_assets.values())
        if model_code is not None:
            assets = [asset for asset in assets if asset.model_code == model_code]
        if status is not None:
            assets = [asset for asset in assets if asset.status == status]
        return sorted(assets, key=lambda asset: asset.created_at, reverse=True)

    def active_model_asset(self, model_code: str) -> ModelAssetRead | None:
        assets = self.list_model_assets(model_code=model_code, status="active")
        return assets[0] if assets else None

    def activate_model_asset(self, asset_id: str) -> ModelAssetRead:
        with self._lock:
            asset = self.model_assets.get(asset_id)
            if asset is None:
                raise ValueError("asset_id does not exist")
            for existing_id, existing in list(self.model_assets.items()):
                if existing.model_code == asset.model_code and existing.status == "active":
                    self.model_assets[existing_id] = existing.model_copy(
                        update={
                            "status": "deprecated",
                            "deprecated_at": self._now(),
                        }
                    )
            activated = asset.model_copy(
                update={"status": "active", "activated_at": self._now()}
            )
            self.model_assets[asset_id] = activated
            return activated

    def deprecate_model_asset(self, asset_id: str) -> ModelAssetRead:
        with self._lock:
            asset = self.model_assets.get(asset_id)
            if asset is None:
                raise ValueError("asset_id does not exist")
            deprecated = asset.model_copy(
                update={"status": "deprecated", "deprecated_at": self._now()}
            )
            self.model_assets[asset_id] = deprecated
            return deprecated

    def save_model_asset_prediction(
        self,
        *,
        asset: ModelAssetRead,
        features: dict[str, float],
        prediction: float | int | str,
        status: str = "completed",
    ) -> str:
        prediction_id = self._new_id("PRED")
        record = ModelAssetPredictionHistoryRead(
            prediction_id=prediction_id,
            asset_id=asset.asset_id,
            model_code=asset.model_code,
            version=asset.version,
            feature_set_id=asset.feature_set_id,
            training_job_id=asset.training_job_id,
            features=features,
            prediction=prediction,
            status=status,
            created_at=self._now(),
        )
        with self._lock:
            self.model_asset_predictions[prediction_id] = record
        return prediction_id

    def list_model_asset_predictions(
        self,
        model_code: str | None = None,
        asset_id: str | None = None,
        limit: int = 25,
    ) -> list[ModelAssetPredictionHistoryRead]:
        with self._lock:
            records = list(self.model_asset_predictions.values())
        if model_code is not None:
            records = [record for record in records if record.model_code == model_code]
        if asset_id is not None:
            records = [record for record in records if record.asset_id == asset_id]
        return sorted(records, key=lambda record: record.created_at, reverse=True)[:limit]

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4()}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_unique_code(rows: object, field_name: str, value: str) -> None:
        for row in rows:
            if getattr(row, field_name) == value:
                raise ValueError(f"{field_name} already exists")

    @staticmethod
    def _filter_measurements(
        rows: list[RawMeasurementRead] | list[CleanMeasurementRead],
        pond_id: str | None,
        variable_code: str | None,
    ) -> list[RawMeasurementRead] | list[CleanMeasurementRead]:
        filtered = rows
        if pond_id is not None:
            filtered = [row for row in filtered if row.pond_id == pond_id]
        if variable_code is not None:
            filtered = [row for row in filtered if row.variable_code == variable_code]
        return sorted(filtered, key=lambda row: row.time)
