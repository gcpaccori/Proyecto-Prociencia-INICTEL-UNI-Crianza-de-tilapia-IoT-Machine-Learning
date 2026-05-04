from alembic.config import Config
from alembic.script import ScriptDirectory

from backend.app.core.database import Base
from backend.app.infrastructure.db import models as db_models


def test_phase_2_tables_are_registered() -> None:
    assert db_models is not None
    expected_tables = {
        "actuation.actuator",
        "actuation.command",
        "aquaculture.biomass_sampling",
        "aquaculture.channel",
        "aquaculture.farm",
        "aquaculture.feed_composition",
        "aquaculture.feed_product",
        "aquaculture.feeding_event",
        "aquaculture.fish_batch",
        "aquaculture.mortality_event",
        "aquaculture.pond",
        "aquaculture.species",
        "audit.audit_log",
        "decision.alert_event",
        "decision.recommendation",
        "iot.sensor",
        "iot.sensor_calibration",
        "iot.sensor_measurement_clean",
        "iot.sensor_measurement_raw",
        "models.model_definition",
        "models.model_input_schema",
        "models.model_output_schema",
        "models.model_parameter",
        "models.model_parameter_set",
        "models.model_run",
        "models.model_run_input",
        "models.model_run_output",
        "models.model_source_reference",
        "models.model_version",
        "timeseries.model_prediction",
    }

    assert expected_tables.issubset(set(Base.metadata.tables))


def test_raw_and_clean_measurement_layers_are_separate() -> None:
    raw_columns = Base.metadata.tables["iot.sensor_measurement_raw"].columns
    clean_columns = Base.metadata.tables["iot.sensor_measurement_clean"].columns

    for column_name in (
        "time",
        "farm_id",
        "pond_id",
        "sensor_id",
        "variable_code",
        "raw_value",
        "raw_unit",
        "raw_payload",
        "source_type",
    ):
        assert column_name in raw_columns

    for column_name in (
        "raw_measurement_id",
        "time",
        "clean_value",
        "standard_unit",
        "quality_flag",
        "validation_status",
        "cleaning_method",
    ):
        assert column_name in clean_columns


def test_model_run_traceability_columns_exist() -> None:
    columns = Base.metadata.tables["models.model_run"].columns

    for column_name in (
        "run_code",
        "model_code",
        "model_version",
        "source_report",
        "source_reference",
        "input_data",
        "parameters",
        "output_data",
        "warnings",
        "confidence",
        "execution_status",
        "error_message",
    ):
        assert column_name in columns


def test_predictions_link_to_model_run_and_model_version() -> None:
    columns = Base.metadata.tables["timeseries.model_prediction"].columns

    assert "model_run_id" in columns
    assert "model_version_id" in columns
    assert "input_window_start" in columns
    assert "input_window_end" in columns
    assert "predicted_variable" in columns
    assert "unit" in columns


def test_alembic_phase_2_revision_is_registered() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == "0001_phase_2"
