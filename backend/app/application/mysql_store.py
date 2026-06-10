from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

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


class MySQLBackendStore:
    def __init__(
        self,
        engine: Engine,
        legacy_database_name: str | None = None,
    ) -> None:
        self.engine = engine
        self.legacy_database_name = legacy_database_name
        self._last_legacy_sync_at = 0.0

    def initialize(self) -> None:
        with self.engine.begin() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(text(statement))
        self.sync_legacy_data(force=True)

    def sync_legacy_data(self, force: bool = False) -> None:
        if not self.legacy_database_name:
            return
        now = time.monotonic()
        if not force and now - self._last_legacy_sync_at < 30:
            return
        if not self._legacy_database_exists():
            return
        with self.engine.begin() as connection:
            legacy = self._quoted_legacy_database()
            connection.execute(
                text(
                    f"""
                    INSERT IGNORE INTO farms (
                        id, code, name, location_name, latitude, longitude,
                        extra_metadata, created_at, updated_at
                    )
                    SELECT
                        CONCAT('LEGACY-FARM-', id),
                        CONCAT('LEGACY-FARM-', id),
                        nombre,
                        direccion,
                        NULLIF(latitud, ''),
                        NULLIF(longitud, ''),
                        JSON_OBJECT(
                            'source_database', :legacy_database,
                            'source_table', 'piscigranjas',
                            'source_id', id,
                            'owner', propietario,
                            'contact_phone', telefono_contacto,
                            'contact_email', email_contacto,
                            'active', activo
                        ),
                        COALESCE(created_at, UTC_TIMESTAMP()),
                        COALESCE(updated_at, UTC_TIMESTAMP())
                    FROM {legacy}.piscigranjas
                    WHERE deleted_at IS NULL
                    """
                ),
                {"legacy_database": self.legacy_database_name},
            )
            connection.execute(
                text(
                    f"""
                    INSERT IGNORE INTO ponds (
                        id, farm_id, code, name, pond_type, water_volume_l,
                        surface_area_m2, extra_metadata, created_at, updated_at
                    )
                    SELECT
                        CONCAT('LEGACY-POND-', id),
                        CONCAT('LEGACY-FARM-', piscigranja_id),
                        CONCAT('LEGACY-POND-', id),
                        nombre,
                        estado,
                        volumen_m3 * 1000,
                        superficie_m2,
                        JSON_OBJECT(
                            'source_database', :legacy_database,
                            'source_table', 'piscinas',
                            'source_id', id,
                            'depth_m', profundidad_m,
                            'description', descripcion
                        ),
                        COALESCE(created_at, UTC_TIMESTAMP()),
                        COALESCE(updated_at, UTC_TIMESTAMP())
                    FROM {legacy}.piscinas
                    WHERE deleted_at IS NULL
                    """
                ),
                {"legacy_database": self.legacy_database_name},
            )
            for actuator_type in ("aerator", "feeder", "pump"):
                connection.execute(
                    text(
                        f"""
                        INSERT IGNORE INTO actuators (
                            id, farm_id, pond_id, actuator_code, actuator_type,
                            manufacturer, status, extra_metadata, created_at, updated_at
                        )
                        SELECT
                            CONCAT('LEGACY-ACTUATOR-', id, '-', :actuator_type),
                            CONCAT('LEGACY-FARM-', piscigranja_id),
                            CONCAT('LEGACY-POND-', id),
                            CONCAT('LEGACY-', UPPER(:actuator_type), '-', id),
                            :actuator_type,
                            'virtual_backend',
                            'active',
                            JSON_OBJECT(
                                'source_database', :legacy_database,
                                'source_table', 'piscinas',
                                'source_id', id,
                                'virtual', true,
                                'dispatch_mode', 'manual_approval_required'
                            ),
                            UTC_TIMESTAMP(),
                            UTC_TIMESTAMP()
                        FROM {legacy}.piscinas
                        WHERE deleted_at IS NULL
                        """
                    ),
                    {
                        "legacy_database": self.legacy_database_name,
                        "actuator_type": actuator_type,
                    },
                )
            for source_column, variable_code, unit in LEGACY_WATER_VARIABLES:
                connection.execute(
                    text(
                        f"""
                        INSERT IGNORE INTO sensors (
                            id, farm_id, pond_id, sensor_code, variable_code,
                            sensor_type, manufacturer, model_name, serial_number,
                            status, extra_metadata, created_at, updated_at
                        )
                        SELECT DISTINCT
                            CONCAT('LEGACY-SENSOR-', pa.piscina_id, '-', :variable_code),
                            CONCAT('LEGACY-FARM-', p.piscigranja_id),
                            CONCAT('LEGACY-POND-', pa.piscina_id),
                            CONCAT('LEGACY-SENSOR-', pa.piscina_id, '-', :variable_code),
                            :variable_code,
                            'legacy_mysql_table',
                            NULL,
                            NULL,
                            NULL,
                            'active',
                            JSON_OBJECT(
                                'source_database', :legacy_database,
                                'source_table', 'parametro_aguas',
                                'source_column', :source_column
                            ),
                            UTC_TIMESTAMP(),
                            UTC_TIMESTAMP()
                        FROM {legacy}.parametro_aguas pa
                        JOIN {legacy}.piscinas p ON p.id = pa.piscina_id
                        WHERE pa.piscina_id IS NOT NULL
                          AND pa.{source_column} IS NOT NULL
                          AND pa.deleted_at IS NULL
                        """
                    ),
                    {
                        "legacy_database": self.legacy_database_name,
                        "source_column": source_column,
                        "variable_code": variable_code,
                    },
                )
                connection.execute(
                    text(
                        f"""
                        INSERT IGNORE INTO raw_measurements (
                            id, time, farm_id, pond_id, sensor_id, variable_code,
                            raw_value, raw_unit, raw_payload, source_type, created_at
                        )
                        SELECT
                            CONCAT('LEGACY-RAW-', pa.id, '-', :variable_code),
                            COALESCE(pa.fecha_medicion, pa.created_at, UTC_TIMESTAMP()),
                            CONCAT('LEGACY-FARM-', p.piscigranja_id),
                            CONCAT('LEGACY-POND-', pa.piscina_id),
                            CONCAT('LEGACY-SENSOR-', pa.piscina_id, '-', :variable_code),
                            :variable_code,
                            pa.{source_column},
                            :unit,
                            JSON_OBJECT(
                                'source_database', :legacy_database,
                                'source_table', 'parametro_aguas',
                                'source_id', pa.id,
                                'source_column', :source_column
                            ),
                            'legacy_mysql',
                            COALESCE(pa.created_at, UTC_TIMESTAMP())
                        FROM {legacy}.parametro_aguas pa
                        JOIN {legacy}.piscinas p ON p.id = pa.piscina_id
                        WHERE pa.piscina_id IS NOT NULL
                          AND pa.{source_column} IS NOT NULL
                          AND pa.deleted_at IS NULL
                        """
                    ),
                    {
                        "legacy_database": self.legacy_database_name,
                        "source_column": source_column,
                        "variable_code": variable_code,
                        "unit": unit,
                    },
                )
                connection.execute(
                    text(
                        f"""
                        INSERT IGNORE INTO clean_measurements (
                            id, raw_measurement_id, time, farm_id, pond_id, sensor_id,
                            variable_code, clean_value, standard_unit, quality_flag,
                            validation_status, cleaning_method, created_at
                        )
                        SELECT
                            CONCAT('LEGACY-CLEAN-', pa.id, '-', :variable_code),
                            CONCAT('LEGACY-RAW-', pa.id, '-', :variable_code),
                            COALESCE(pa.fecha_medicion, pa.created_at, UTC_TIMESTAMP()),
                            CONCAT('LEGACY-FARM-', p.piscigranja_id),
                            CONCAT('LEGACY-POND-', pa.piscina_id),
                            CONCAT('LEGACY-SENSOR-', pa.piscina_id, '-', :variable_code),
                            :variable_code,
                            pa.{source_column},
                            :unit,
                            'legacy_valid',
                            'accepted',
                            'legacy_pass_through_no_unit_conversion',
                            COALESCE(pa.created_at, UTC_TIMESTAMP())
                        FROM {legacy}.parametro_aguas pa
                        JOIN {legacy}.piscinas p ON p.id = pa.piscina_id
                        WHERE pa.piscina_id IS NOT NULL
                          AND pa.{source_column} IS NOT NULL
                          AND pa.deleted_at IS NULL
                        """
                    ),
                    {
                        "source_column": source_column,
                        "variable_code": variable_code,
                        "unit": unit,
                    },
                )
        self._last_legacy_sync_at = now

    def create_farm(self, payload: FarmCreate) -> FarmRead:
        farm = FarmRead(id=self._new_id("FARM"), **payload.model_dump())
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO farms (
                        id, code, name, location_name, latitude, longitude,
                        extra_metadata, created_at, updated_at
                    )
                    VALUES (
                        :id, :code, :name, :location_name, :latitude, :longitude,
                        :extra_metadata, :created_at, :updated_at
                    )
                    """
                ),
                self._dump_model(farm),
            )
        return farm

    def list_farms(self) -> list[FarmRead]:
        self.sync_legacy_data()
        rows = self._fetch_all("SELECT * FROM farms ORDER BY name")
        return [self._farm_from_row(row) for row in rows]

    def get_farm(self, farm_id: str) -> FarmRead | None:
        self.sync_legacy_data()
        row = self._fetch_one("SELECT * FROM farms WHERE id = :id", {"id": farm_id})
        return self._farm_from_row(row) if row else None

    def create_pond(self, payload: PondCreate) -> PondRead:
        if self.get_farm(payload.farm_id) is None:
            raise ValueError("farm_id does not exist")
        pond = PondRead(id=self._new_id("POND"), **payload.model_dump())
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ponds (
                        id, farm_id, code, name, pond_type, water_volume_l,
                        surface_area_m2, extra_metadata, created_at, updated_at
                    )
                    VALUES (
                        :id, :farm_id, :code, :name, :pond_type, :water_volume_l,
                        :surface_area_m2, :extra_metadata, :created_at, :updated_at
                    )
                    """
                ),
                self._dump_model(pond),
            )
        return pond

    def list_ponds(self, farm_id: str | None = None) -> list[PondRead]:
        self.sync_legacy_data()
        if farm_id is None:
            rows = self._fetch_all("SELECT * FROM ponds ORDER BY name")
        else:
            rows = self._fetch_all(
                "SELECT * FROM ponds WHERE farm_id = :farm_id ORDER BY name",
                {"farm_id": farm_id},
            )
        return [self._pond_from_row(row) for row in rows]

    def get_pond(self, pond_id: str) -> PondRead | None:
        self.sync_legacy_data()
        row = self._fetch_one("SELECT * FROM ponds WHERE id = :id", {"id": pond_id})
        return self._pond_from_row(row) if row else None

    def create_sensor(self, payload: SensorCreate) -> SensorRead:
        if self.get_farm(payload.farm_id) is None:
            raise ValueError("farm_id does not exist")
        if payload.pond_id is not None and self.get_pond(payload.pond_id) is None:
            raise ValueError("pond_id does not exist")
        sensor = SensorRead(id=self._new_id("SENSOR"), **payload.model_dump())
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO sensors (
                        id, farm_id, pond_id, sensor_code, variable_code,
                        sensor_type, manufacturer, model_name, serial_number, status,
                        extra_metadata, created_at, updated_at
                    )
                    VALUES (
                        :id, :farm_id, :pond_id, :sensor_code, :variable_code,
                        :sensor_type, :manufacturer, :model_name, :serial_number,
                        :status, :extra_metadata, :created_at, :updated_at
                    )
                    """
                ),
                self._dump_model(sensor),
            )
        return sensor

    def list_sensors(self, pond_id: str | None = None) -> list[SensorRead]:
        self.sync_legacy_data()
        if pond_id is None:
            rows = self._fetch_all("SELECT * FROM sensors ORDER BY sensor_code")
        else:
            rows = self._fetch_all(
                "SELECT * FROM sensors WHERE pond_id = :pond_id ORDER BY sensor_code",
                {"pond_id": pond_id},
            )
        return [self._sensor_from_row(row) for row in rows]

    def get_sensor(self, sensor_id: str) -> SensorRead | None:
        self.sync_legacy_data()
        row = self._fetch_one("SELECT * FROM sensors WHERE id = :id", {"id": sensor_id})
        return self._sensor_from_row(row) if row else None

    def ingest_measurement(
        self,
        payload: RawMeasurementCreate,
    ) -> MeasurementIngestionResult:
        if self.get_farm(payload.farm_id) is None:
            raise ValueError("farm_id does not exist")
        if payload.pond_id is not None and self.get_pond(payload.pond_id) is None:
            raise ValueError("pond_id does not exist")
        if payload.sensor_id is not None and self.get_sensor(payload.sensor_id) is None:
            raise ValueError("sensor_id does not exist")
        raw = RawMeasurementRead(id=self._new_id("RAW"), **payload.model_dump())
        clean = None
        warnings: list[str] = []
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO raw_measurements (
                        id, time, farm_id, pond_id, sensor_id, variable_code,
                        raw_value, raw_unit, raw_payload, source_type, created_at
                    )
                    VALUES (
                        :id, :time, :farm_id, :pond_id, :sensor_id, :variable_code,
                        :raw_value, :raw_unit, :raw_payload, :source_type, :created_at
                    )
                    """
                ),
                self._dump_model(raw),
            )
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
                connection.execute(
                    text(
                        """
                        INSERT INTO clean_measurements (
                            id, raw_measurement_id, time, farm_id, pond_id, sensor_id,
                            variable_code, clean_value, standard_unit, quality_flag,
                            validation_status, cleaning_method, created_at
                        )
                        VALUES (
                            :id, :raw_measurement_id, :time, :farm_id, :pond_id,
                            :sensor_id, :variable_code, :clean_value, :standard_unit,
                            :quality_flag, :validation_status, :cleaning_method,
                            :created_at
                        )
                        """
                    ),
                    self._dump_model(clean),
                )
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
        self.sync_legacy_data()
        where, params = self._measurement_filters(pond_id, variable_code, limit)
        rows = self._fetch_all(
            f"SELECT * FROM raw_measurements {where} ORDER BY time DESC LIMIT :limit",
            params,
        )
        return [self._raw_from_row(row) for row in rows]

    def list_clean_measurements(
        self,
        pond_id: str | None = None,
        variable_code: str | None = None,
        limit: int = 100,
    ) -> list[CleanMeasurementRead]:
        self.sync_legacy_data()
        where, params = self._measurement_filters(pond_id, variable_code, limit)
        rows = self._fetch_all(
            f"SELECT * FROM clean_measurements {where} ORDER BY time DESC LIMIT :limit",
            params,
        )
        return [self._clean_from_row(row) for row in rows]

    def latest_clean_by_variable(self, pond_id: str) -> dict[str, CleanMeasurementRead]:
        self.sync_legacy_data()
        rows = self._fetch_all(
            """
            SELECT cm.*
            FROM clean_measurements cm
            JOIN (
                SELECT variable_code, MAX(time) AS max_time
                FROM clean_measurements
                WHERE pond_id = :pond_id
                GROUP BY variable_code
            ) latest
              ON latest.variable_code = cm.variable_code
             AND latest.max_time = cm.time
            WHERE cm.pond_id = :pond_id
            ORDER BY cm.variable_code
            """,
            {"pond_id": pond_id},
        )
        return {row["variable_code"]: self._clean_from_row(row) for row in rows}

    def save_snapshot(self, snapshot: DigitalTwinSnapshot) -> DigitalTwinSnapshot:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO digital_twin_snapshots (
                        snapshot_id, pond_id, timestamp, payload_json, created_at
                    )
                    VALUES (
                        :snapshot_id, :pond_id, :timestamp, :payload_json, :created_at
                    )
                    ON DUPLICATE KEY UPDATE
                        payload_json = VALUES(payload_json),
                        timestamp = VALUES(timestamp)
                    """
                ),
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "pond_id": snapshot.pond_id,
                    "timestamp": snapshot.timestamp,
                    "payload_json": snapshot.model_dump_json(),
                    "created_at": self._now(),
                },
            )
        return snapshot

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
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ras_operational_events (
                        event_id, pond_id, event_type, event_time, amount_kg,
                        operator_name, notes, details_json, created_at
                    )
                    VALUES (
                        :event_id, :pond_id, :event_type, :event_time, :amount_kg,
                        :operator, :notes, :details, :created_at
                    )
                    """
                ),
                self._dump_model(event),
            )
        return event

    def list_ras_operational_events(
        self,
        pond_id: str,
        limit: int = 50,
    ) -> list[RasOperationalEventRead]:
        rows = self._fetch_all(
            """
            SELECT event_id, pond_id, event_type, event_time, amount_kg,
                   operator_name, notes, details_json, created_at
            FROM ras_operational_events
            WHERE pond_id = :pond_id
            ORDER BY event_time DESC
            LIMIT :limit
            """,
            {"pond_id": pond_id, "limit": limit},
        )
        return [
            RasOperationalEventRead(
                event_id=row["event_id"],
                pond_id=row["pond_id"],
                event_type=row["event_type"],
                event_time=row["event_time"],
                amount_kg=self._float_or_none(row["amount_kg"]),
                operator=row["operator_name"],
                notes=row["notes"],
                details=self._json(row["details_json"]),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def get_snapshot(self, snapshot_id: str) -> DigitalTwinSnapshot | None:
        row = self._fetch_one(
            "SELECT payload_json FROM digital_twin_snapshots WHERE snapshot_id = :id",
            {"id": snapshot_id},
        )
        return self._snapshot_from_row(row) if row else None

    def latest_snapshot(self, pond_id: str) -> DigitalTwinSnapshot | None:
        row = self._fetch_one(
            """
            SELECT payload_json
            FROM digital_twin_snapshots
            WHERE pond_id = :pond_id
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            {"pond_id": pond_id},
        )
        return self._snapshot_from_row(row) if row else None

    def list_alerts(
        self,
        pond_id: str | None = None,
        severity: str | None = None,
    ) -> list[AlertRead]:
        alerts: list[AlertRead] = []
        for snapshot in self._list_snapshots(pond_id):
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
        for snapshot in self._list_snapshots(pond_id):
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
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO actuators (
                        id, farm_id, pond_id, actuator_code, actuator_type,
                        manufacturer, status, extra_metadata, created_at, updated_at
                    )
                    VALUES (
                        :id, :farm_id, :pond_id, :actuator_code, :actuator_type,
                        :manufacturer, :status, :extra_metadata, :created_at,
                        :updated_at
                    )
                    """
                ),
                self._dump_model(payload),
            )
        return payload

    def list_actuators(self, pond_id: str | None = None) -> list[ActuatorRead]:
        self.sync_legacy_data()
        if pond_id is None:
            rows = self._fetch_all("SELECT * FROM actuators ORDER BY actuator_code")
        else:
            rows = self._fetch_all(
                "SELECT * FROM actuators WHERE pond_id = :pond_id ORDER BY actuator_code",
                {"pond_id": pond_id},
            )
        return [self._actuator_from_row(row) for row in rows]

    def get_actuator(self, actuator_id: str) -> ActuatorRead | None:
        self.sync_legacy_data()
        row = self._fetch_one(
            "SELECT * FROM actuators WHERE id = :id",
            {"id": actuator_id},
        )
        return self._actuator_from_row(row) if row else None

    def save_command(self, command: ActuationCommandDraft) -> ActuationCommandDraft:
        command_id = self._new_id("COMMAND")
        stored_command = command.model_copy(
            update={
                "command_id": command_id,
                "audit_record": {
                    **command.audit_record,
                    "command_id": command_id,
                },
            }
        )
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO actuation_commands (
                        command_id, payload_json, requested_at, execution_status
                    )
                    VALUES (
                        :command_id, :payload_json, :requested_at, :execution_status
                    )
                    """
                ),
                {
                    "command_id": command_id,
                    "payload_json": stored_command.model_dump_json(),
                    "requested_at": stored_command.requested_at,
                    "execution_status": stored_command.execution_status,
                },
            )
        return stored_command

    def list_commands(self) -> list[ActuationCommandDraft]:
        rows = self._fetch_all(
            "SELECT payload_json FROM actuation_commands ORDER BY requested_at DESC"
        )
        return [
            ActuationCommandDraft.model_validate_json(str(row["payload_json"]))
            for row in rows
        ]

    def save_model_output(self, output: ModelOutput) -> ModelOutput:
        run_id = self._new_id("RUN")
        stored_output = output.model_copy(
            update={
                "run_id": run_id,
                "traceability": {**output.traceability, "model_run_id": run_id},
            }
        )
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO model_outputs (
                        run_id, model_code, payload_json, created_at
                    )
                    VALUES (
                        :run_id, :model_code, :payload_json, :created_at
                    )
                    """
                ),
                {
                    "run_id": run_id,
                    "model_code": stored_output.model_code,
                    "payload_json": stored_output.model_dump_json(),
                    "created_at": self._now(),
                },
            )
        return stored_output

    def list_model_outputs(
        self,
        model_code: str | None = None,
        limit: int = 100,
    ) -> list[ModelOutput]:
        if model_code is None:
            rows = self._fetch_all(
                """
                SELECT payload_json
                FROM model_outputs
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {"limit": limit},
            )
        else:
            rows = self._fetch_all(
                """
                SELECT payload_json
                FROM model_outputs
                WHERE model_code = :model_code
                ORDER BY created_at DESC
                LIMIT :limit
                """,
                {"model_code": model_code, "limit": limit},
            )
        return [ModelOutput.model_validate_json(str(row["payload_json"])) for row in rows]

    def save_clean_measurements(
        self,
        rows: list[CleanMeasurementRead],
        overwrite_ids: bool = False,
    ) -> list[CleanMeasurementRead]:
        if not rows:
            return rows
        with self.engine.begin() as connection:
            for row in rows:
                statement = """
                    INSERT INTO clean_measurements (
                        id, raw_measurement_id, time, farm_id, pond_id, sensor_id,
                        variable_code, clean_value, standard_unit, quality_flag,
                        validation_status, cleaning_method, created_at
                    )
                    VALUES (
                        :id, :raw_measurement_id, :time, :farm_id, :pond_id,
                        :sensor_id, :variable_code, :clean_value, :standard_unit,
                        :quality_flag, :validation_status, :cleaning_method,
                        :created_at
                    )
                    ON DUPLICATE KEY UPDATE
                        clean_value = IF(:overwrite_ids, VALUES(clean_value), clean_value),
                        quality_flag = IF(:overwrite_ids, VALUES(quality_flag), quality_flag),
                        validation_status = IF(:overwrite_ids, VALUES(validation_status), validation_status),
                        cleaning_method = IF(:overwrite_ids, VALUES(cleaning_method), cleaning_method)
                """
                payload = self._dump_model(row)
                payload["overwrite_ids"] = overwrite_ids
                connection.execute(text(statement), payload)
        return rows

    def save_cleaning_run_measurements(
        self,
        run_id: str,
        rows: list[CleanMeasurementRead],
    ) -> list[CleanMeasurementRead]:
        if not rows:
            return rows
        with self.engine.begin() as connection:
            connection.execute(
                text("DELETE FROM cleaning_run_measurements WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            payloads = []
            for row in rows:
                payload = self._dump_model(row)
                payload["run_id"] = run_id
                payloads.append(payload)
            connection.execute(
                text(
                    """
                    INSERT INTO cleaning_run_measurements (
                        run_id, row_id, raw_measurement_id, time, farm_id, pond_id,
                        sensor_id, variable_code, clean_value, standard_unit,
                        quality_flag, validation_status, cleaning_method, created_at
                    )
                    VALUES (
                        :run_id, :id, :raw_measurement_id, :time, :farm_id, :pond_id,
                        :sensor_id, :variable_code, :clean_value, :standard_unit,
                        :quality_flag, :validation_status, :cleaning_method, :created_at
                    )
                    """
                ),
                payloads,
            )
        return rows

    def list_cleaning_run_measurements(
        self,
        run_id: str,
        pond_id: str | None = None,
        variable_code: str | None = None,
        limit: int = 100,
    ) -> list[CleanMeasurementRead]:
        clauses = ["run_id = :run_id"]
        params: dict[str, Any] = {"run_id": run_id, "limit": limit}
        if pond_id is not None:
            clauses.append("pond_id = :pond_id")
            params["pond_id"] = pond_id
        if variable_code is not None:
            clauses.append("variable_code = :variable_code")
            params["variable_code"] = variable_code
        where = f"WHERE {' AND '.join(clauses)}"
        rows = self._fetch_all(
            f"""
            SELECT
                row_id AS id, raw_measurement_id, time, farm_id, pond_id, sensor_id,
                variable_code, clean_value, standard_unit, quality_flag,
                validation_status, cleaning_method, created_at
            FROM cleaning_run_measurements
            {where}
            ORDER BY time DESC
            LIMIT :limit
            """,
            params,
        )
        return [self._clean_from_row(row) for row in rows]

    def save_cleaning_run(self, cleaning_run: CleaningRunRead) -> CleaningRunRead:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO cleaning_runs (
                        run_id, payload_json, status, started_at, finished_at
                    )
                    VALUES (
                        :run_id, :payload_json, :status, :started_at, :finished_at
                    )
                    ON DUPLICATE KEY UPDATE
                        payload_json = VALUES(payload_json),
                        status = VALUES(status),
                        finished_at = VALUES(finished_at)
                    """
                ),
                {
                    "run_id": cleaning_run.run_id,
                    "payload_json": cleaning_run.model_dump_json(),
                    "status": cleaning_run.status,
                    "started_at": cleaning_run.started_at,
                    "finished_at": cleaning_run.finished_at,
                },
            )
        return cleaning_run

    def get_cleaning_run(self, run_id: str) -> CleaningRunRead | None:
        row = self._fetch_one(
            "SELECT payload_json FROM cleaning_runs WHERE run_id = :run_id",
            {"run_id": run_id},
        )
        return CleaningRunRead.model_validate_json(str(row["payload_json"])) if row else None

    def list_cleaning_runs(self) -> list[CleaningRunRead]:
        rows = self._fetch_all(
            "SELECT payload_json FROM cleaning_runs ORDER BY started_at DESC"
        )
        return [CleaningRunRead.model_validate_json(str(row["payload_json"])) for row in rows]

    def save_feature_set(self, feature_set: FeatureSetRead) -> FeatureSetRead:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO feature_sets (
                        feature_set_id, pond_id, target_variable, payload_json,
                        status, created_at
                    )
                    VALUES (
                        :feature_set_id, :pond_id, :target_variable, :payload_json,
                        :status, :created_at
                    )
                    ON DUPLICATE KEY UPDATE
                        payload_json = VALUES(payload_json),
                        status = VALUES(status)
                    """
                ),
                {
                    "feature_set_id": feature_set.feature_set_id,
                    "pond_id": feature_set.pond_id,
                    "target_variable": feature_set.target_variable,
                    "payload_json": feature_set.model_dump_json(),
                    "status": feature_set.status,
                    "created_at": feature_set.created_at,
                },
            )
            connection.execute(
                text("DELETE FROM feature_set_rows WHERE feature_set_id = :feature_set_id"),
                {"feature_set_id": feature_set.feature_set_id},
            )
            row_payloads = []
            for row in feature_set.rows:
                row_index = int(row.get("row_index", 0))
                split_name = "train"
                if row_index >= feature_set.train_rows + feature_set.validation_rows:
                    split_name = "test"
                elif row_index >= feature_set.train_rows:
                    split_name = "validation"
                row_payloads.append(
                    {
                        "feature_set_id": feature_set.feature_set_id,
                        "row_index": row_index,
                        "split_name": split_name,
                        "row_payload_json": json.dumps(row),
                        "target_value": row.get("target"),
                        "created_at": feature_set.created_at,
                    }
                )
            if row_payloads:
                connection.execute(
                    text(
                        """
                        INSERT INTO feature_set_rows (
                            feature_set_id, row_index, split_name, row_payload_json,
                            target_value, created_at
                        )
                        VALUES (
                            :feature_set_id, :row_index, :split_name, :row_payload_json,
                            :target_value, :created_at
                        )
                        """
                    ),
                    row_payloads,
                )
        return feature_set

    def get_feature_set(self, feature_set_id: str) -> FeatureSetRead | None:
        row = self._fetch_one(
            "SELECT payload_json FROM feature_sets WHERE feature_set_id = :id",
            {"id": feature_set_id},
        )
        return FeatureSetRead.model_validate_json(str(row["payload_json"])) if row else None

    def list_feature_sets(self) -> list[FeatureSetRead]:
        rows = self._fetch_all(
            "SELECT payload_json FROM feature_sets LIMIT 50"
        )
        feature_sets = [
            FeatureSetRead.model_validate_json(str(row["payload_json"])) for row in rows
        ]
        return [
            feature_set.model_copy(update={"rows": []})
            for feature_set in sorted(
                feature_sets,
                key=lambda item: item.created_at,
                reverse=True,
            )
        ]

    def save_training_job(self, job: TrainingJobRead) -> TrainingJobRead:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO training_jobs (
                        job_id, model_code, feature_set_id, payload_json,
                        status, requested_at, finished_at
                    )
                    VALUES (
                        :job_id, :model_code, :feature_set_id, :payload_json,
                        :status, :requested_at, :finished_at
                    )
                    ON DUPLICATE KEY UPDATE
                        payload_json = VALUES(payload_json),
                        status = VALUES(status),
                        finished_at = VALUES(finished_at)
                    """
                ),
                {
                    "job_id": job.job_id,
                    "model_code": job.model_code,
                    "feature_set_id": job.feature_set_id,
                    "payload_json": job.model_dump_json(),
                    "status": job.status,
                    "requested_at": job.requested_at,
                    "finished_at": job.finished_at,
                },
            )
        return job

    def get_training_job(self, job_id: str) -> TrainingJobRead | None:
        row = self._fetch_one(
            "SELECT payload_json FROM training_jobs WHERE job_id = :job_id",
            {"job_id": job_id},
        )
        return TrainingJobRead.model_validate_json(str(row["payload_json"])) if row else None

    def list_training_jobs(self) -> list[TrainingJobRead]:
        rows = self._fetch_all(
            "SELECT payload_json FROM training_jobs ORDER BY requested_at DESC"
        )
        return [TrainingJobRead.model_validate_json(str(row["payload_json"])) for row in rows]

    def append_training_job_event(
        self,
        event: TrainingJobEventRead,
    ) -> TrainingJobEventRead:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO training_job_events (
                        event_id, job_id, payload_json, event_type, created_at
                    )
                    VALUES (
                        :event_id, :job_id, :payload_json, :event_type, :created_at
                    )
                    """
                ),
                {
                    "event_id": event.event_id,
                    "job_id": event.job_id,
                    "payload_json": event.model_dump_json(),
                    "event_type": event.event_type,
                    "created_at": event.created_at,
                },
            )
        return event

    def list_training_job_events(self, job_id: str) -> list[TrainingJobEventRead]:
        rows = self._fetch_all(
            """
            SELECT payload_json
            FROM training_job_events
            WHERE job_id = :job_id
            ORDER BY created_at
            """,
            {"job_id": job_id},
        )
        return [
            TrainingJobEventRead.model_validate_json(str(row["payload_json"]))
            for row in rows
        ]

    def save_model_asset(self, asset: ModelAssetRead) -> ModelAssetRead:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO model_assets (
                        asset_id, model_code, version, artifact_path,
                        status, payload_json, created_at, activated_at, deprecated_at
                    )
                    VALUES (
                        :asset_id, :model_code, :version, :artifact_path,
                        :status, :payload_json, :created_at, :activated_at, :deprecated_at
                    )
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        payload_json = VALUES(payload_json),
                        activated_at = VALUES(activated_at),
                        deprecated_at = VALUES(deprecated_at)
                    """
                ),
                {
                    "asset_id": asset.asset_id,
                    "model_code": asset.model_code,
                    "version": asset.version,
                    "artifact_path": asset.artifact_path,
                    "status": asset.status,
                    "payload_json": asset.model_dump_json(),
                    "created_at": asset.created_at,
                    "activated_at": asset.activated_at,
                    "deprecated_at": asset.deprecated_at,
                },
            )
        return asset

    def get_model_asset(self, asset_id: str) -> ModelAssetRead | None:
        row = self._fetch_one(
            "SELECT payload_json FROM model_assets WHERE asset_id = :asset_id",
            {"asset_id": asset_id},
        )
        return ModelAssetRead.model_validate_json(str(row["payload_json"])) if row else None

    def list_model_assets(
        self,
        model_code: str | None = None,
        status: str | None = None,
    ) -> list[ModelAssetRead]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if model_code is not None:
            clauses.append("model_code = :model_code")
            params["model_code"] = model_code
        if status is not None:
            clauses.append("status = :status")
            params["status"] = status
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetch_all(
            f"SELECT payload_json FROM model_assets {where} LIMIT 100",
            params,
        )
        assets = [
            ModelAssetRead.model_validate_json(str(row["payload_json"])) for row in rows
        ]
        return sorted(assets, key=lambda item: item.created_at, reverse=True)

    def active_model_asset(self, model_code: str) -> ModelAssetRead | None:
        assets = self.list_model_assets(model_code=model_code, status="active")
        return assets[0] if assets else None

    def activate_model_asset(self, asset_id: str) -> ModelAssetRead:
        asset = self.get_model_asset(asset_id)
        if asset is None:
            raise ValueError("asset_id does not exist")
        now = self._now()
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE model_assets
                    SET status = 'deprecated',
                        deprecated_at = :now,
                        payload_json = JSON_SET(payload_json, '$.status', 'deprecated')
                    WHERE model_code = :model_code AND status = 'active'
                    """
                ),
                {"now": now, "model_code": asset.model_code},
            )
        activated = asset.model_copy(update={"status": "active", "activated_at": now})
        return self.save_model_asset(activated)

    def deprecate_model_asset(self, asset_id: str) -> ModelAssetRead:
        asset = self.get_model_asset(asset_id)
        if asset is None:
            raise ValueError("asset_id does not exist")
        deprecated = asset.model_copy(
            update={"status": "deprecated", "deprecated_at": self._now()}
        )
        return self.save_model_asset(deprecated)

    def save_model_asset_prediction(
        self,
        *,
        asset: ModelAssetRead,
        features: dict[str, float],
        prediction: float | int | str,
        status: str = "completed",
    ) -> str:
        prediction_id = self._new_id("PRED")
        created_at = self._now()
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO model_asset_predictions (
                        prediction_id, asset_id, model_code, version, feature_set_id,
                        training_job_id, input_json, prediction_json, status, created_at
                    )
                    VALUES (
                        :prediction_id, :asset_id, :model_code, :version, :feature_set_id,
                        :training_job_id, :input_json, :prediction_json, :status, :created_at
                    )
                    """
                ),
                {
                    "prediction_id": prediction_id,
                    "asset_id": asset.asset_id,
                    "model_code": asset.model_code,
                    "version": asset.version,
                    "feature_set_id": asset.feature_set_id,
                    "training_job_id": asset.training_job_id,
                    "input_json": json.dumps(features),
                    "prediction_json": json.dumps({"prediction": prediction}),
                    "status": status,
                    "created_at": created_at,
                },
            )
        return prediction_id

    def list_model_asset_predictions(
        self,
        model_code: str | None = None,
        asset_id: str | None = None,
        limit: int = 25,
    ) -> list[ModelAssetPredictionHistoryRead]:
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if model_code is not None:
            clauses.append("model_code = :model_code")
            params["model_code"] = model_code
        if asset_id is not None:
            clauses.append("asset_id = :asset_id")
            params["asset_id"] = asset_id
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetch_all(
            f"""
            SELECT prediction_id, asset_id, model_code, version, feature_set_id,
                   training_job_id, input_json, prediction_json, status, created_at
            FROM model_asset_predictions
            {where}
            ORDER BY created_at DESC
            LIMIT :limit
            """,
            params,
        )
        return [self._prediction_from_row(row) for row in rows]

    def _list_snapshots(self, pond_id: str | None = None) -> list[DigitalTwinSnapshot]:
        if pond_id is None:
            rows = self._fetch_all(
                "SELECT payload_json FROM digital_twin_snapshots ORDER BY timestamp DESC"
            )
        else:
            rows = self._fetch_all(
                """
                SELECT payload_json
                FROM digital_twin_snapshots
                WHERE pond_id = :pond_id
                ORDER BY timestamp DESC
                """,
                {"pond_id": pond_id},
            )
        return [self._snapshot_from_row(row) for row in rows]

    def _legacy_database_exists(self) -> bool:
        row = self._fetch_one(
            """
            SELECT SCHEMA_NAME
            FROM information_schema.SCHEMATA
            WHERE SCHEMA_NAME = :database_name
            """,
            {"database_name": self.legacy_database_name},
        )
        return row is not None

    def _quoted_legacy_database(self) -> str:
        if self.legacy_database_name is None:
            raise ValueError("legacy_database_name is not configured")
        safe_name = self.legacy_database_name.replace("`", "``")
        return f"`{safe_name}`"

    def _fetch_all(
        self,
        statement: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        with self.engine.connect() as connection:
            rows = connection.execute(text(statement), params or {}).mappings().all()
        return [dict(row) for row in rows]

    def _fetch_one(
        self,
        statement: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self.engine.connect() as connection:
            row = connection.execute(text(statement), params or {}).mappings().first()
        return dict(row) if row else None

    def _measurement_filters(
        self,
        pond_id: str | None,
        variable_code: str | None,
        limit: int,
    ) -> tuple[str, dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit}
        if pond_id is not None:
            clauses.append("pond_id = :pond_id")
            params["pond_id"] = pond_id
        if variable_code is not None:
            clauses.append("variable_code = :variable_code")
            params["variable_code"] = variable_code
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def _farm_from_row(self, row: dict[str, Any]) -> FarmRead:
        return FarmRead(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            location_name=row["location_name"],
            latitude=self._float_or_none(row["latitude"]),
            longitude=self._float_or_none(row["longitude"]),
            extra_metadata=self._json(row["extra_metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _pond_from_row(self, row: dict[str, Any]) -> PondRead:
        return PondRead(
            id=row["id"],
            farm_id=row["farm_id"],
            code=row["code"],
            name=row["name"],
            pond_type=row["pond_type"],
            water_volume_l=self._float_or_none(row["water_volume_l"]),
            surface_area_m2=self._float_or_none(row["surface_area_m2"]),
            extra_metadata=self._json(row["extra_metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _sensor_from_row(self, row: dict[str, Any]) -> SensorRead:
        return SensorRead(
            id=row["id"],
            farm_id=row["farm_id"],
            pond_id=row["pond_id"],
            sensor_code=row["sensor_code"],
            variable_code=row["variable_code"],
            sensor_type=row["sensor_type"],
            manufacturer=row["manufacturer"],
            model_name=row["model_name"],
            serial_number=row["serial_number"],
            status=row["status"],
            extra_metadata=self._json(row["extra_metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _raw_from_row(self, row: dict[str, Any]) -> RawMeasurementRead:
        return RawMeasurementRead(
            id=row["id"],
            time=row["time"],
            farm_id=row["farm_id"],
            pond_id=row["pond_id"],
            sensor_id=row["sensor_id"],
            variable_code=row["variable_code"],
            raw_value=self._float_or_none(row["raw_value"]),
            raw_unit=row["raw_unit"],
            raw_payload=self._json(row["raw_payload"]),
            source_type=row["source_type"],
            created_at=row["created_at"],
        )

    def _clean_from_row(self, row: dict[str, Any]) -> CleanMeasurementRead:
        return CleanMeasurementRead(
            id=row["id"],
            raw_measurement_id=row["raw_measurement_id"],
            time=row["time"],
            farm_id=row["farm_id"],
            pond_id=row["pond_id"],
            sensor_id=row["sensor_id"],
            variable_code=row["variable_code"],
            clean_value=float(row["clean_value"]),
            standard_unit=row["standard_unit"],
            quality_flag=row["quality_flag"],
            validation_status=row["validation_status"],
            cleaning_method=row["cleaning_method"],
            created_at=row["created_at"],
        )

    def _prediction_from_row(self, row: dict[str, Any]) -> ModelAssetPredictionHistoryRead:
        prediction_payload = self._json(row["prediction_json"])
        return ModelAssetPredictionHistoryRead(
            prediction_id=row["prediction_id"],
            asset_id=row["asset_id"],
            model_code=row["model_code"],
            version=row["version"],
            feature_set_id=row["feature_set_id"],
            training_job_id=row["training_job_id"],
            features={key: float(value) for key, value in self._json(row["input_json"]).items()},
            prediction=prediction_payload.get("prediction"),
            status=row["status"],
            created_at=row["created_at"],
        )

    def _actuator_from_row(self, row: dict[str, Any]) -> ActuatorRead:
        return ActuatorRead(
            id=row["id"],
            farm_id=row["farm_id"],
            pond_id=row["pond_id"],
            actuator_code=row["actuator_code"],
            actuator_type=row["actuator_type"],
            manufacturer=row["manufacturer"],
            status=row["status"],
            extra_metadata=self._json(row["extra_metadata"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _snapshot_from_row(row: dict[str, Any]) -> DigitalTwinSnapshot:
        return DigitalTwinSnapshot.model_validate_json(str(row["payload_json"]))

    @staticmethod
    def _dump_model(model: Any) -> dict[str, Any]:
        payload = model.model_dump()
        for key, value in list(payload.items()):
            if isinstance(value, (dict, list)):
                payload[key] = json.dumps(value)
        return payload

    @staticmethod
    def _json(value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        return json.loads(str(value))

    @staticmethod
    def _float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4()}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)


LEGACY_WATER_VARIABLES = [
    ("temperatura", "water_temperature_c", "degC"),
    ("ph", "ph", "pH"),
    ("oxigeno_disuelto", "dissolved_oxygen_mg_l", "mg/L"),
    ("ion_nitrato", "nitrate_ion", "source_unit"),
]


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS farms (
        id VARCHAR(128) PRIMARY KEY,
        code VARCHAR(128) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL,
        location_name VARCHAR(255),
        latitude DOUBLE,
        longitude DOUBLE,
        extra_metadata JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ponds (
        id VARCHAR(128) PRIMARY KEY,
        farm_id VARCHAR(128) NOT NULL,
        code VARCHAR(128) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL,
        pond_type VARCHAR(128),
        water_volume_l DOUBLE,
        surface_area_m2 DOUBLE,
        extra_metadata JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        INDEX ix_ponds_farm_id (farm_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sensors (
        id VARCHAR(128) PRIMARY KEY,
        farm_id VARCHAR(128) NOT NULL,
        pond_id VARCHAR(128),
        sensor_code VARCHAR(128) NOT NULL UNIQUE,
        variable_code VARCHAR(128) NOT NULL,
        sensor_type VARCHAR(128),
        manufacturer VARCHAR(255),
        model_name VARCHAR(255),
        serial_number VARCHAR(255),
        status VARCHAR(64) NOT NULL,
        extra_metadata JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        INDEX ix_sensors_pond_id (pond_id),
        INDEX ix_sensors_variable_code (variable_code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_measurements (
        id VARCHAR(160) PRIMARY KEY,
        time DATETIME NOT NULL,
        farm_id VARCHAR(128) NOT NULL,
        pond_id VARCHAR(128),
        sensor_id VARCHAR(128),
        variable_code VARCHAR(128) NOT NULL,
        raw_value DOUBLE,
        raw_unit VARCHAR(64),
        raw_payload JSON NOT NULL,
        source_type VARCHAR(64) NOT NULL,
        created_at DATETIME NOT NULL,
        INDEX ix_raw_pond_time (pond_id, time),
        INDEX ix_raw_variable_time (variable_code, time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS clean_measurements (
        id VARCHAR(160) PRIMARY KEY,
        raw_measurement_id VARCHAR(160) NOT NULL UNIQUE,
        time DATETIME NOT NULL,
        farm_id VARCHAR(128) NOT NULL,
        pond_id VARCHAR(128),
        sensor_id VARCHAR(128),
        variable_code VARCHAR(128) NOT NULL,
        clean_value DOUBLE NOT NULL,
        standard_unit VARCHAR(64) NOT NULL,
        quality_flag VARCHAR(64) NOT NULL,
        validation_status VARCHAR(64) NOT NULL,
        cleaning_method VARCHAR(128),
        created_at DATETIME NOT NULL,
        INDEX ix_clean_pond_time (pond_id, time),
        INDEX ix_clean_variable_time (variable_code, time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS digital_twin_snapshots (
        snapshot_id VARCHAR(160) PRIMARY KEY,
        pond_id VARCHAR(128) NOT NULL,
        timestamp DATETIME NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        INDEX ix_snapshots_pond_time (pond_id, timestamp)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ras_operational_events (
        event_id VARCHAR(160) PRIMARY KEY,
        pond_id VARCHAR(128) NOT NULL,
        event_type VARCHAR(32) NOT NULL,
        event_time DATETIME(6) NOT NULL,
        amount_kg DOUBLE,
        operator_name VARCHAR(128),
        notes TEXT,
        details_json JSON NOT NULL,
        created_at DATETIME(6) NOT NULL,
        INDEX ix_ras_events_pond_time (pond_id, event_time),
        INDEX ix_ras_events_type_time (event_type, event_time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_outputs (
        run_id VARCHAR(160) PRIMARY KEY,
        model_code VARCHAR(128) NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        INDEX ix_model_outputs_code_time (model_code, created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cleaning_runs (
        run_id VARCHAR(160) PRIMARY KEY,
        payload_json JSON NOT NULL,
        status VARCHAR(64) NOT NULL,
        started_at DATETIME NOT NULL,
        finished_at DATETIME,
        INDEX ix_cleaning_runs_status_time (status, started_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cleaning_run_measurements (
        run_id VARCHAR(160) NOT NULL,
        row_id VARCHAR(255) NOT NULL,
        raw_measurement_id VARCHAR(160) NOT NULL,
        time DATETIME NOT NULL,
        farm_id VARCHAR(128) NOT NULL,
        pond_id VARCHAR(128),
        sensor_id VARCHAR(128),
        variable_code VARCHAR(128) NOT NULL,
        clean_value DOUBLE NOT NULL,
        standard_unit VARCHAR(64) NOT NULL,
        quality_flag VARCHAR(64) NOT NULL,
        validation_status VARCHAR(64) NOT NULL,
        cleaning_method VARCHAR(128),
        created_at DATETIME NOT NULL,
        PRIMARY KEY (run_id, row_id),
        INDEX ix_cleaning_run_measurements_run_var_time (run_id, variable_code, time),
        INDEX ix_cleaning_run_measurements_pond_time (pond_id, time)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_sets (
        feature_set_id VARCHAR(160) PRIMARY KEY,
        pond_id VARCHAR(128) NOT NULL,
        target_variable VARCHAR(128) NOT NULL,
        payload_json JSON NOT NULL,
        status VARCHAR(64) NOT NULL,
        created_at DATETIME NOT NULL,
        INDEX ix_feature_sets_pond_time (pond_id, created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS feature_set_rows (
        feature_set_id VARCHAR(160) NOT NULL,
        row_index INT NOT NULL,
        split_name VARCHAR(32) NOT NULL,
        row_payload_json JSON NOT NULL,
        target_value DOUBLE,
        created_at DATETIME NOT NULL,
        PRIMARY KEY (feature_set_id, row_index),
        INDEX ix_feature_set_rows_split (feature_set_id, split_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_jobs (
        job_id VARCHAR(160) PRIMARY KEY,
        model_code VARCHAR(128) NOT NULL,
        feature_set_id VARCHAR(160) NOT NULL,
        payload_json JSON NOT NULL,
        status VARCHAR(64) NOT NULL,
        requested_at DATETIME NOT NULL,
        finished_at DATETIME,
        INDEX ix_training_jobs_model_time (model_code, requested_at),
        INDEX ix_training_jobs_status_time (status, requested_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS training_job_events (
        event_id VARCHAR(160) PRIMARY KEY,
        job_id VARCHAR(160) NOT NULL,
        payload_json JSON NOT NULL,
        event_type VARCHAR(64) NOT NULL,
        created_at DATETIME NOT NULL,
        INDEX ix_training_job_events_job_time (job_id, created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_assets (
        asset_id VARCHAR(160) PRIMARY KEY,
        model_code VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        artifact_path TEXT NOT NULL,
        status VARCHAR(64) NOT NULL,
        payload_json JSON NOT NULL,
        created_at DATETIME NOT NULL,
        activated_at DATETIME,
        deprecated_at DATETIME,
        INDEX ix_model_assets_model_status (model_code, status),
        INDEX ix_model_assets_created_at (created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS model_asset_predictions (
        prediction_id VARCHAR(160) PRIMARY KEY,
        asset_id VARCHAR(160) NOT NULL,
        model_code VARCHAR(128) NOT NULL,
        version VARCHAR(64) NOT NULL,
        feature_set_id VARCHAR(160) NOT NULL,
        training_job_id VARCHAR(160) NOT NULL,
        input_json JSON NOT NULL,
        prediction_json JSON NOT NULL,
        status VARCHAR(64) NOT NULL,
        created_at DATETIME NOT NULL,
        INDEX ix_model_asset_predictions_model_time (model_code, created_at),
        INDEX ix_model_asset_predictions_asset_time (asset_id, created_at)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actuators (
        id VARCHAR(128) PRIMARY KEY,
        farm_id VARCHAR(128) NOT NULL,
        pond_id VARCHAR(128),
        actuator_code VARCHAR(128) NOT NULL UNIQUE,
        actuator_type VARCHAR(128) NOT NULL,
        manufacturer VARCHAR(255),
        status VARCHAR(64) NOT NULL,
        extra_metadata JSON NOT NULL,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        INDEX ix_actuators_pond_id (pond_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actuation_commands (
        command_id VARCHAR(160) PRIMARY KEY,
        payload_json JSON NOT NULL,
        requested_at DATETIME NOT NULL,
        execution_status VARCHAR(64) NOT NULL,
        INDEX ix_commands_requested_at (requested_at)
    )
    """,
]
