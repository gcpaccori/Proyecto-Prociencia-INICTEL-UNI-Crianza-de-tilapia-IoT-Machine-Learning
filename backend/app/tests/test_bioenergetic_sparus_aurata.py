from datetime import datetime, timezone

import pytest

from backend.app.models_engine.base import ModelInput, ModelInputValue, ModelRunContext
from backend.app.models_engine.bioenergetic import (
    BioenergeticSparusAurataBrigolin2010,
)


def build_model_input(**parameters: object) -> ModelInput:
    return ModelInput(
        model_code="BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={
            "wet_weight_g": ModelInputValue(value=120.0, unit="g"),
            "water_temperature_c": ModelInputValue(value=22.0, unit="degC"),
            "feed_ration_day_1": ModelInputValue(value=0.03, unit="day^-1"),
            "protein_fraction": ModelInputValue(value=0.45, unit="fraction"),
            "lipid_fraction": ModelInputValue(value=0.18, unit="fraction"),
            "carbohydrate_fraction": ModelInputValue(value=0.22, unit="fraction"),
            "protein_digestibility": ModelInputValue(value=0.88, unit="fraction"),
            "lipid_digestibility": ModelInputValue(value=0.9, unit="fraction"),
            "carbohydrate_digestibility": ModelInputValue(
                value=0.75,
                unit="fraction",
            ),
            "energy_content_somatic_tissue_kj_g": ModelInputValue(
                value=6.1,
                unit="kJ/g",
            ),
        },
        parameters=parameters,
    )


def build_context() -> ModelRunContext:
    return ModelRunContext(
        model_code="BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010",
        model_version="1.0.0",
        source_report="INFORME018",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
    )


def test_model_metadata_matches_catalog_contract() -> None:
    model = BioenergeticSparusAurataBrigolin2010()

    assert model.metadata.model_code == "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010"
    assert model.metadata.source_report == "INFORME018"
    assert "wet_weight_g" in model.metadata.inputs
    assert "predicted_weight_g" in model.metadata.outputs


def test_model_executes_brigolin_step() -> None:
    model = BioenergeticSparusAurataBrigolin2010()

    result = model.run(build_model_input(), build_context())

    assert result.outputs["predicted_weight_g"].value > 0
    assert result.outputs["net_anabolism_j_day"].value >= 0
    assert result.outputs["fasting_catabolism_j_day"].value >= 0
    assert result.outputs["temperature_effect"].value >= 0


def test_model_returns_required_outputs() -> None:
    model = BioenergeticSparusAurataBrigolin2010()

    result = model.run(build_model_input(), build_context())

    assert result.model_code == "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010"
    assert result.outputs["predicted_weight_g"].unit == "g"
    assert result.outputs["net_anabolism_j_day"].unit == "J/day"
    assert result.outputs["fasting_catabolism_j_day"].unit == "J/day"
    assert result.outputs["feed_intake_day_1"].unit == "day^-1"
    assert result.outputs["uneaten_feed_g"].unit == "g"
    assert result.outputs["feces_production_g_day"].unit == "g/day"
    assert result.explainability["formula"] == "dw/dt = (A - C) / epsilon_T"


def test_model_validates_units() -> None:
    model_input = build_model_input(metadata_only=True)
    model_input.inputs["wet_weight_g"] = ModelInputValue(value=120.0, unit="kg")

    with pytest.raises(ValueError, match="wet_weight_g"):
        BioenergeticSparusAurataBrigolin2010().run(model_input, build_context())


def test_model_validates_fraction_bounds() -> None:
    model_input = build_model_input(metadata_only=True)
    model_input.inputs["protein_digestibility"] = ModelInputValue(
        value=1.2,
        unit="fraction",
    )

    with pytest.raises(ValueError, match="protein_digestibility"):
        BioenergeticSparusAurataBrigolin2010().run(model_input, build_context())


def test_model_rejects_diet_fraction_sum_above_one() -> None:
    model_input = build_model_input(metadata_only=True)
    model_input.inputs["carbohydrate_fraction"] = ModelInputValue(
        value=0.5,
        unit="fraction",
    )

    with pytest.raises(ValueError, match="diet fractions"):
        BioenergeticSparusAurataBrigolin2010().run(model_input, build_context())
