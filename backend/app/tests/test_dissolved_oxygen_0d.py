from datetime import datetime, timezone

import pytest

from backend.app.models_engine.base import ModelInput, ModelInputValue, ModelRunContext
from backend.app.models_engine.mechanistic import (
    DissolvedOxygen0DRoyer2021,
)


def build_model_input(**parameters: object) -> ModelInput:
    return ModelInput(
        model_code="DO_DYNAMIC_0D_ROYER_2021",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={
            "do_initial_mg_l": ModelInputValue(value=6.2, unit="mg/L"),
            "do_influent_mg_l": ModelInputValue(value=7.1, unit="mg/L"),
            "water_temperature_c": ModelInputValue(value=18.5, unit="degC"),
            "flow_rate_l_h": ModelInputValue(value=1200.0, unit="L/h"),
            "raceway_volume_l": ModelInputValue(value=1280.0, unit="L"),
            "fish_biomass_kg": ModelInputValue(value=120.0, unit="kg"),
            "fish_respiration_rate_mg_h_kg": ModelInputValue(
                value=20.0,
                unit="mg/h/kg",
            ),
            "oxygen_supply_rate_mg_l_h": ModelInputValue(
                value=0.2,
                unit="mg/L/h",
            ),
            "reaeration_rate_h_1": ModelInputValue(value=0.046, unit="h^-1"),
            "simulation_horizon_minutes": ModelInputValue(value=60, unit="min"),
        },
        parameters=parameters,
    )


def build_context() -> ModelRunContext:
    return ModelRunContext(
        model_code="DO_DYNAMIC_0D_ROYER_2021",
        model_version="1.0.0",
        source_report="INFORME016",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
    )


def test_model_metadata_matches_catalog_contract() -> None:
    model = DissolvedOxygen0DRoyer2021()

    assert model.metadata.model_code == "DO_DYNAMIC_0D_ROYER_2021"
    assert model.metadata.source_report == "INFORME016"
    assert "do_initial_mg_l" in model.metadata.inputs
    assert "do_forecast_mg_l" in model.metadata.outputs


def test_model_executes_0d_euler_forecast() -> None:
    model = DissolvedOxygen0DRoyer2021()

    result = model.run(build_model_input(dt_minutes=60), build_context())

    assert result.outputs["do_forecast_mg_l"].value == pytest.approx(5.52094, rel=1e-4)
    assert result.outputs["oxygen_consumption_rate"].value == pytest.approx(1.875)
    assert result.outputs["oxygen_demand"].value == pytest.approx(1.875)
    assert result.outputs["do_saturation_mg_l"].value > 9


def test_model_returns_required_outputs() -> None:
    model = DissolvedOxygen0DRoyer2021()

    result = model.run(build_model_input(), build_context())

    assert result.model_code == "DO_DYNAMIC_0D_ROYER_2021"
    assert result.outputs["do_forecast_mg_l"].unit == "mg/L"
    assert result.outputs["oxygen_consumption_rate"].unit == "mg/L/h"
    assert result.outputs["oxygen_demand"].unit == "mg/L"
    assert result.outputs["hypoxia_risk"].value in {"low", "medium", "high"}
    assert "dx/dt" in result.explainability["formula"]


def test_model_validates_units() -> None:
    model_input = build_model_input(metadata_only=True)
    model_input.inputs["water_temperature_c"] = ModelInputValue(value=18.5, unit="C")

    with pytest.raises(ValueError, match="water_temperature_c"):
        DissolvedOxygen0DRoyer2021().run(model_input, build_context())


def test_model_requires_positive_volume_and_horizon() -> None:
    model_input = build_model_input(metadata_only=True)
    model_input.inputs["raceway_volume_l"] = ModelInputValue(value=0, unit="L")

    with pytest.raises(ValueError, match="raceway_volume_l"):
        DissolvedOxygen0DRoyer2021().run(model_input, build_context())
