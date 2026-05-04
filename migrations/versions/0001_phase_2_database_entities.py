"""phase 2 database entities

Revision ID: 0001_phase_2
Revises:
Create Date: 2026-05-04 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_phase_2"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMAS = (
    "aquaculture",
    "iot",
    "models",
    "timeseries",
    "decision",
    "actuation",
    "audit",
)


def uuid_pk() -> sa.Column:
    return sa.Column("id", sa.Uuid(), primary_key=True)


def created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def updated_at() -> sa.Column:
    return sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


def upgrade() -> None:
    for schema in SCHEMAS:
        op.execute(sa.schema.CreateSchema(schema, if_not_exists=True))

    op.create_table(
        "farm",
        uuid_pk(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location_name", sa.String(length=255)),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint("code", name="uq_farm_code"),
        schema="aquaculture",
    )
    op.create_table(
        "pond",
        uuid_pk(),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("pond_type", sa.String(length=64)),
        sa.Column("water_volume_l", sa.Numeric(14, 3)),
        sa.Column("surface_area_m2", sa.Numeric(14, 3)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_pond_farm_id_farm",
            ondelete="CASCADE",
        ),
        schema="aquaculture",
    )
    op.create_table(
        "channel",
        uuid_pk(),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("flow_rate_l_h", sa.Numeric(14, 3)),
        sa.Column("volume_l", sa.Numeric(14, 3)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_channel_farm_id_farm",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_channel_pond_id_pond",
            ondelete="SET NULL",
        ),
        schema="aquaculture",
    )
    op.create_table(
        "species",
        uuid_pk(),
        sa.Column("scientific_name", sa.String(length=255), nullable=False),
        sa.Column("common_name", sa.String(length=255)),
        sa.Column("source_reference", sa.String(length=255)),
        created_at(),
        updated_at(),
        schema="aquaculture",
    )
    op.create_table(
        "fish_batch",
        uuid_pk(),
        sa.Column("pond_id", sa.Uuid(), nullable=False),
        sa.Column("species_id", sa.Uuid(), nullable=False),
        sa.Column("batch_code", sa.String(length=64), nullable=False),
        sa.Column("stocking_date", sa.Date()),
        sa.Column("initial_count", sa.Integer()),
        sa.Column("initial_average_weight_g", sa.Numeric(12, 3)),
        sa.Column("current_count", sa.Integer()),
        sa.Column("status", sa.String(length=32), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_fish_batch_pond_id_pond",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["species_id"],
            ["aquaculture.species.id"],
            name="fk_fish_batch_species_id_species",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("batch_code", name="uq_fish_batch_batch_code"),
        schema="aquaculture",
    )
    op.create_table(
        "biomass_sampling",
        uuid_pk(),
        sa.Column("fish_batch_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid(), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_count", sa.Integer()),
        sa.Column("average_weight_g", sa.Numeric(12, 3), nullable=False),
        sa.Column("biomass_kg", sa.Numeric(14, 3), nullable=False),
        sa.Column("method", sa.String(length=128)),
        sa.Column("unit_map", sa.JSON(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["fish_batch_id"],
            ["aquaculture.fish_batch.id"],
            name="fk_biomass_sampling_fish_batch_id_fish_batch",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_biomass_sampling_pond_id_pond",
            ondelete="RESTRICT",
        ),
        schema="aquaculture",
    )
    op.create_index(
        "ix_biomass_sampling_time",
        "biomass_sampling",
        ["time"],
        schema="aquaculture",
    )
    op.create_table(
        "mortality_event",
        uuid_pk(),
        sa.Column("fish_batch_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid(), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mortality_count", sa.Integer(), nullable=False),
        sa.Column("cause", sa.String(length=255)),
        sa.Column("notes", sa.Text()),
        created_at(),
        sa.ForeignKeyConstraint(
            ["fish_batch_id"],
            ["aquaculture.fish_batch.id"],
            name="fk_mortality_event_fish_batch_id_fish_batch",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_mortality_event_pond_id_pond",
            ondelete="RESTRICT",
        ),
        schema="aquaculture",
    )
    op.create_index(
        "ix_mortality_event_time",
        "mortality_event",
        ["time"],
        schema="aquaculture",
    )
    op.create_table(
        "feed_product",
        uuid_pk(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=255)),
        sa.Column("pellet_size_mm", sa.Numeric(8, 3)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint("code", name="uq_feed_product_code"),
        schema="aquaculture",
    )
    op.create_table(
        "feed_composition",
        uuid_pk(),
        sa.Column("feed_product_id", sa.Uuid(), nullable=False),
        sa.Column("protein_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("lipid_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("carbohydrate_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column("energy_kj_g", sa.Numeric(8, 3)),
        sa.Column("digestibility_protein", sa.Numeric(6, 4)),
        sa.Column("digestibility_lipid", sa.Numeric(6, 4)),
        sa.Column("digestibility_carb", sa.Numeric(6, 4)),
        sa.Column("effective_from", sa.Date()),
        sa.Column("source_reference", sa.String(length=255)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["feed_product_id"],
            ["aquaculture.feed_product.id"],
            name="fk_feed_composition_feed_product_id_feed_product",
            ondelete="CASCADE",
        ),
        schema="aquaculture",
    )
    op.create_table(
        "feeding_event",
        uuid_pk(),
        sa.Column("pond_id", sa.Uuid(), nullable=False),
        sa.Column("fish_batch_id", sa.Uuid()),
        sa.Column("feed_product_id", sa.Uuid()),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feed_amount_g", sa.Numeric(12, 3), nullable=False),
        sa.Column("feed_unit", sa.String(length=16), nullable=False),
        sa.Column("feeding_method", sa.String(length=128)),
        sa.Column("operator", sa.String(length=128)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_feeding_event_pond_id_pond",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["fish_batch_id"],
            ["aquaculture.fish_batch.id"],
            name="fk_feeding_event_fish_batch_id_fish_batch",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["feed_product_id"],
            ["aquaculture.feed_product.id"],
            name="fk_feeding_event_feed_product_id_feed_product",
            ondelete="SET NULL",
        ),
        schema="aquaculture",
    )
    op.create_index(
        "ix_feeding_event_time",
        "feeding_event",
        ["time"],
        schema="aquaculture",
    )

    op.create_table(
        "sensor",
        uuid_pk(),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("channel_id", sa.Uuid()),
        sa.Column("sensor_code", sa.String(length=128), nullable=False),
        sa.Column("variable_code", sa.String(length=64), nullable=False),
        sa.Column("sensor_type", sa.String(length=128)),
        sa.Column("manufacturer", sa.String(length=255)),
        sa.Column("model_name", sa.String(length=255)),
        sa.Column("serial_number", sa.String(length=255)),
        sa.Column("installed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_sensor_farm_id_farm",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_sensor_pond_id_pond",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["aquaculture.channel.id"],
            name="fk_sensor_channel_id_channel",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("sensor_code", name="uq_sensor_sensor_code"),
        schema="iot",
    )
    op.create_table(
        "sensor_calibration",
        uuid_pk(),
        sa.Column("sensor_id", sa.Uuid(), nullable=False),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("variable_code", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=128)),
        sa.Column("coefficients", sa.JSON(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("performed_by", sa.String(length=128)),
        sa.Column("notes", sa.Text()),
        created_at(),
        sa.ForeignKeyConstraint(
            ["sensor_id"],
            ["iot.sensor.id"],
            name="fk_sensor_calibration_sensor_id_sensor",
            ondelete="CASCADE",
        ),
        schema="iot",
    )
    op.create_table(
        "sensor_measurement_raw",
        uuid_pk(),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("sensor_id", sa.Uuid()),
        sa.Column("variable_code", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.Numeric(18, 6)),
        sa.Column("raw_unit", sa.String(length=32)),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_sensor_measurement_raw_farm_id_farm",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_sensor_measurement_raw_pond_id_pond",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sensor_id"],
            ["iot.sensor.id"],
            name="fk_sensor_measurement_raw_sensor_id_sensor",
            ondelete="SET NULL",
        ),
        schema="iot",
    )
    op.create_index(
        "ix_sensor_measurement_raw_time",
        "sensor_measurement_raw",
        ["time"],
        schema="iot",
    )
    op.create_index(
        "ix_sensor_measurement_raw_sensor_id_time",
        "sensor_measurement_raw",
        ["sensor_id", "time"],
        schema="iot",
    )
    op.create_table(
        "sensor_measurement_clean",
        uuid_pk(),
        sa.Column("raw_measurement_id", sa.Uuid(), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("sensor_id", sa.Uuid()),
        sa.Column("variable_code", sa.String(length=64), nullable=False),
        sa.Column("clean_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("standard_unit", sa.String(length=32), nullable=False),
        sa.Column("quality_flag", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=64), nullable=False),
        sa.Column("cleaning_method", sa.String(length=128)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["raw_measurement_id"],
            ["iot.sensor_measurement_raw.id"],
            name="fk_sensor_clean_raw_measurement_id_raw",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_sensor_measurement_clean_farm_id_farm",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_sensor_measurement_clean_pond_id_pond",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["sensor_id"],
            ["iot.sensor.id"],
            name="fk_sensor_measurement_clean_sensor_id_sensor",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "raw_measurement_id",
            name="uq_sensor_measurement_clean_raw_measurement_id",
        ),
        schema="iot",
    )
    op.create_index(
        "ix_sensor_measurement_clean_time",
        "sensor_measurement_clean",
        ["time"],
        schema="iot",
    )
    op.create_index(
        "ix_sensor_measurement_clean_sensor_id_time",
        "sensor_measurement_clean",
        ["sensor_id", "time"],
        schema="iot",
    )

    op.create_table(
        "model_definition",
        uuid_pk(),
        sa.Column("model_code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("model_type", sa.String(length=64), nullable=False),
        sa.Column("source_report", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("implementation_status", sa.String(length=64), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.UniqueConstraint("model_code", name="uq_model_definition_model_code"),
        schema="models",
    )
    op.create_table(
        "model_version",
        uuid_pk(),
        sa.Column("model_definition_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255)),
        sa.Column("artifact_uri", sa.String(length=1024)),
        sa.Column("parameters_schema", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["models.model_definition.id"],
            name="fk_model_version_model_definition_id_model_definition",
            ondelete="CASCADE",
        ),
        schema="models",
    )
    op.create_table(
        "model_source_reference",
        uuid_pk(),
        sa.Column("model_definition_id", sa.Uuid(), nullable=False),
        sa.Column("source_report", sa.String(length=64), nullable=False),
        sa.Column("markdown_file", sa.String(length=512), nullable=False),
        sa.Column("reference_detail", sa.String(length=512)),
        sa.Column("equation_status", sa.String(length=128)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_definition_id"],
            ["models.model_definition.id"],
            name="fk_model_source_reference_model_definition_id_model_definition",
            ondelete="CASCADE",
        ),
        schema="models",
    )
    op.create_table(
        "model_parameter",
        uuid_pk(),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("parameter_name", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=32)),
        sa.Column("description", sa.Text()),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["models.model_version.id"],
            name="fk_model_parameter_model_version_id_model_version",
            ondelete="CASCADE",
        ),
        schema="models",
    )
    op.create_table(
        "model_parameter_set",
        uuid_pk(),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("parameter_set_code", sa.String(length=128), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("source_reference", sa.String(length=255)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["models.model_version.id"],
            name="fk_model_parameter_set_model_version_id_model_version",
            ondelete="CASCADE",
        ),
        schema="models",
    )
    op.create_table(
        "model_input_schema",
        uuid_pk(),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("unit_map", sa.JSON(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["models.model_version.id"],
            name="fk_model_input_schema_model_version_id_model_version",
            ondelete="CASCADE",
        ),
        schema="models",
    )
    op.create_table(
        "model_output_schema",
        uuid_pk(),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("unit_map", sa.JSON(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["models.model_version.id"],
            name="fk_model_output_schema_model_version_id_model_version",
            ondelete="CASCADE",
        ),
        schema="models",
    )
    op.create_table(
        "model_run",
        uuid_pk(),
        sa.Column("run_code", sa.String(length=128), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("parameter_set_id", sa.Uuid()),
        sa.Column("model_code", sa.String(length=128), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("source_report", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=255)),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("output_data", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("execution_status", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["models.model_version.id"],
            name="fk_model_run_model_version_id_model_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parameter_set_id"],
            ["models.model_parameter_set.id"],
            name="fk_model_run_parameter_set_id_model_parameter_set",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("run_code", name="uq_model_run_run_code"),
        schema="models",
    )
    op.create_index("ix_model_run_model_code", "model_run", ["model_code"], schema="models")
    op.create_index("ix_model_run_created_at", "model_run", ["created_at"], schema="models")
    op.create_table(
        "model_run_input",
        uuid_pk(),
        sa.Column("model_run_id", sa.Uuid(), nullable=False),
        sa.Column("input_name", sa.String(length=128), nullable=False),
        sa.Column("input_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=32)),
        sa.Column("source_measurement_id", sa.Uuid()),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_run_id"],
            ["models.model_run.id"],
            name="fk_model_run_input_model_run_id_model_run",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_measurement_id"],
            ["iot.sensor_measurement_clean.id"],
            name="fk_model_run_input_source_measurement_id_clean",
            ondelete="SET NULL",
        ),
        schema="models",
    )
    op.create_table(
        "model_run_output",
        uuid_pk(),
        sa.Column("model_run_id", sa.Uuid(), nullable=False),
        sa.Column("output_name", sa.String(length=128), nullable=False),
        sa.Column("output_value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=32)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_run_id"],
            ["models.model_run.id"],
            name="fk_model_run_output_model_run_id_model_run",
            ondelete="CASCADE",
        ),
        schema="models",
    )

    op.create_table(
        "model_prediction",
        uuid_pk(),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("target_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("model_run_id", sa.Uuid(), nullable=False),
        sa.Column("input_window_start", sa.DateTime(timezone=True)),
        sa.Column("input_window_end", sa.DateTime(timezone=True)),
        sa.Column("predicted_variable", sa.String(length=128), nullable=False),
        sa.Column("predicted_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        created_at(),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["models.model_version.id"],
            name="fk_model_prediction_model_version_id_model_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_run_id"],
            ["models.model_run.id"],
            name="fk_model_prediction_model_run_id_model_run",
            ondelete="RESTRICT",
        ),
        schema="timeseries",
    )
    op.create_index(
        "ix_model_prediction_time",
        "model_prediction",
        ["time"],
        schema="timeseries",
    )
    op.create_index(
        "ix_model_prediction_target_time",
        "model_prediction",
        ["target_time"],
        schema="timeseries",
    )

    op.create_table(
        "alert_event",
        uuid_pk(),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("alert_code", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source_model_run_id", sa.Uuid()),
        sa.Column("source_prediction_id", sa.Uuid()),
        created_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_alert_event_farm_id_farm",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_alert_event_pond_id_pond",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_model_run_id"],
            ["models.model_run.id"],
            name="fk_alert_event_source_model_run_id_model_run",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_prediction_id"],
            ["timeseries.model_prediction.id"],
            name="fk_alert_event_source_prediction_id_model_prediction",
            ondelete="SET NULL",
        ),
        schema="decision",
    )
    op.create_index("ix_alert_event_time", "alert_event", ["time"], schema="decision")
    op.create_table(
        "recommendation",
        uuid_pk(),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("recommendation_code", sa.String(length=128), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.Column("model_run_id", sa.Uuid()),
        sa.Column("alert_event_id", sa.Uuid()),
        created_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_recommendation_farm_id_farm",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_recommendation_pond_id_pond",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_run_id"],
            ["models.model_run.id"],
            name="fk_recommendation_model_run_id_model_run",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["alert_event_id"],
            ["decision.alert_event.id"],
            name="fk_recommendation_alert_event_id_alert_event",
            ondelete="SET NULL",
        ),
        schema="decision",
    )
    op.create_index("ix_recommendation_time", "recommendation", ["time"], schema="decision")

    op.create_table(
        "actuator",
        uuid_pk(),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("pond_id", sa.Uuid()),
        sa.Column("actuator_code", sa.String(length=128), nullable=False),
        sa.Column("actuator_type", sa.String(length=64), nullable=False),
        sa.Column("manufacturer", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["aquaculture.farm.id"],
            name="fk_actuator_farm_id_farm",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pond_id"],
            ["aquaculture.pond.id"],
            name="fk_actuator_pond_id_pond",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("actuator_code", name="uq_actuator_actuator_code"),
        schema="actuation",
    )
    op.create_table(
        "command",
        uuid_pk(),
        sa.Column("actuator_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid()),
        sa.Column("command_type", sa.String(length=64), nullable=False),
        sa.Column("command_payload", sa.JSON(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("requested_by", sa.String(length=128)),
        sa.Column("execution_status", sa.String(length=64), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(
            ["actuator_id"],
            ["actuation.actuator.id"],
            name="fk_command_actuator_id_actuator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["decision.recommendation.id"],
            name="fk_command_recommendation_id_recommendation",
            ondelete="SET NULL",
        ),
        schema="actuation",
    )
    op.create_index("ix_command_requested_at", "command", ["requested_at"], schema="actuation")

    op.create_table(
        "audit_log",
        uuid_pk(),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=128)),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_schema", sa.String(length=64), nullable=False),
        sa.Column("entity_table", sa.String(length=128), nullable=False),
        sa.Column("entity_id", sa.String(length=64)),
        sa.Column("source_data_window_start", sa.DateTime(timezone=True)),
        sa.Column("source_data_window_end", sa.DateTime(timezone=True)),
        sa.Column("payload", sa.JSON(), nullable=False),
        created_at(),
        schema="audit",
    )
    op.create_index("ix_audit_log_time", "audit_log", ["time"], schema="audit")


def downgrade() -> None:
    op.drop_index("ix_audit_log_time", table_name="audit_log", schema="audit")
    op.drop_table("audit_log", schema="audit")
    op.drop_index("ix_command_requested_at", table_name="command", schema="actuation")
    op.drop_table("command", schema="actuation")
    op.drop_table("actuator", schema="actuation")
    op.drop_index("ix_recommendation_time", table_name="recommendation", schema="decision")
    op.drop_table("recommendation", schema="decision")
    op.drop_index("ix_alert_event_time", table_name="alert_event", schema="decision")
    op.drop_table("alert_event", schema="decision")
    op.drop_index("ix_model_prediction_target_time", table_name="model_prediction", schema="timeseries")
    op.drop_index("ix_model_prediction_time", table_name="model_prediction", schema="timeseries")
    op.drop_table("model_prediction", schema="timeseries")
    op.drop_table("model_run_output", schema="models")
    op.drop_table("model_run_input", schema="models")
    op.drop_index("ix_model_run_created_at", table_name="model_run", schema="models")
    op.drop_index("ix_model_run_model_code", table_name="model_run", schema="models")
    op.drop_table("model_run", schema="models")
    op.drop_table("model_output_schema", schema="models")
    op.drop_table("model_input_schema", schema="models")
    op.drop_table("model_parameter_set", schema="models")
    op.drop_table("model_parameter", schema="models")
    op.drop_table("model_source_reference", schema="models")
    op.drop_table("model_version", schema="models")
    op.drop_table("model_definition", schema="models")
    op.drop_index("ix_sensor_measurement_clean_sensor_id_time", table_name="sensor_measurement_clean", schema="iot")
    op.drop_index("ix_sensor_measurement_clean_time", table_name="sensor_measurement_clean", schema="iot")
    op.drop_table("sensor_measurement_clean", schema="iot")
    op.drop_index("ix_sensor_measurement_raw_sensor_id_time", table_name="sensor_measurement_raw", schema="iot")
    op.drop_index("ix_sensor_measurement_raw_time", table_name="sensor_measurement_raw", schema="iot")
    op.drop_table("sensor_measurement_raw", schema="iot")
    op.drop_table("sensor_calibration", schema="iot")
    op.drop_table("sensor", schema="iot")
    op.drop_index("ix_feeding_event_time", table_name="feeding_event", schema="aquaculture")
    op.drop_table("feeding_event", schema="aquaculture")
    op.drop_table("feed_composition", schema="aquaculture")
    op.drop_table("feed_product", schema="aquaculture")
    op.drop_index("ix_mortality_event_time", table_name="mortality_event", schema="aquaculture")
    op.drop_table("mortality_event", schema="aquaculture")
    op.drop_index("ix_biomass_sampling_time", table_name="biomass_sampling", schema="aquaculture")
    op.drop_table("biomass_sampling", schema="aquaculture")
    op.drop_table("fish_batch", schema="aquaculture")
    op.drop_table("species", schema="aquaculture")
    op.drop_table("channel", schema="aquaculture")
    op.drop_table("pond", schema="aquaculture")
    op.drop_table("farm", schema="aquaculture")

    for schema in reversed(SCHEMAS):
        op.execute(sa.schema.DropSchema(schema, if_exists=True))
