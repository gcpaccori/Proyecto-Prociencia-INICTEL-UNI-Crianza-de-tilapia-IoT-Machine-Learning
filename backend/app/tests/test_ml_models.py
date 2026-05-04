from datetime import datetime, timezone

import pytest

from backend.app.models_engine.base import ModelInput, ModelInputValue, ModelRunContext
from backend.app.models_engine.ml import (
    BPNNMEAFeedIntake,
    BPNNModelArtifactPendingError,
    PearsonLSTMAttentionWaterQuality,
    PearsonLSTMModelArtifactPendingError,
)


def build_bpnn_input(**parameters: object) -> ModelInput:
    return ModelInput(
        model_code="BPNN_MEA_FEED_INTAKE",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={
            "water_temperature_c": ModelInputValue(value=22.0, unit="degC"),
            "dissolved_oxygen_mg_l": ModelInputValue(value=6.4, unit="mg/L"),
            "average_fish_weight_g": ModelInputValue(value=120.0, unit="g"),
            "fish_number": ModelInputValue(value=250, unit="count"),
        },
        parameters=parameters,
    )


def build_bpnn_context() -> ModelRunContext:
    return ModelRunContext(
        model_code="BPNN_MEA_FEED_INTAKE",
        model_version="0.1.0",
        source_report="INFORME017",
    )


def build_lstm_input(**parameters: object) -> ModelInput:
    series = [1.0, 2.0, 3.0]
    return ModelInput(
        model_code="PEARSON_LSTM_ATTENTION_WQ",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={
            "ph": ModelInputValue(value=[7.1, 7.2, 7.3], unit="pH"),
            "water_temperature_c": ModelInputValue(value=[21.0, 21.3, 21.5], unit="degC"),
            "dissolved_oxygen_mg_l": ModelInputValue(value=[6.0, 6.1, 6.2], unit="mg/L"),
            "ammonia_nitrogen_mg_l": ModelInputValue(value=series, unit="mg/L"),
            "nitrite_mg_l": ModelInputValue(value=series, unit="mg/L"),
            "orp_mv": ModelInputValue(value=[250.0, 251.0, 252.0], unit="mV"),
            "turbidity_ntu": ModelInputValue(value=[12.0, 12.5, 13.0], unit="NTU"),
        },
        parameters=parameters,
    )


def build_lstm_context() -> ModelRunContext:
    return ModelRunContext(
        model_code="PEARSON_LSTM_ATTENTION_WQ",
        model_version="0.1.0",
        source_report="INFORME017",
    )


def test_bpnn_blocks_execution_without_trained_artifact() -> None:
    with pytest.raises(BPNNModelArtifactPendingError, match="artifact pending"):
        BPNNMEAFeedIntake().run(build_bpnn_input(), build_bpnn_context())


def test_bpnn_allows_metadata_only_output() -> None:
    result = BPNNMEAFeedIntake().run(
        build_bpnn_input(metadata_only=True),
        build_bpnn_context(),
    )

    assert result.model_code == "BPNN_MEA_FEED_INTAKE"
    assert result.outputs["feed_intake_g"].unit == "g"
    assert result.explainability["architecture"] == "4-10-1"
    assert result.explainability["artifact_status"] == "MODEL_ARTIFACT_PENDING"


def test_bpnn_delegates_to_injected_predictor() -> None:
    def predictor(features: dict[str, float], parameters: dict[str, object]) -> float:
        assert features["fish_number"] == 250.0
        assert parameters["artifact_version"] == "test"
        return 480.0

    model = BPNNMEAFeedIntake(predictor=predictor)

    result = model.run(
        build_bpnn_input(artifact_version="test"),
        build_bpnn_context(),
    )

    assert result.outputs["feed_intake_g"].value == 480.0
    assert result.outputs["feed_intake_g"].unit == "g"


def test_bpnn_validates_units_and_counts() -> None:
    model_input = build_bpnn_input(metadata_only=True)
    model_input.inputs["fish_number"] = ModelInputValue(value=3.5, unit="count")

    with pytest.raises(ValueError, match="fish_number"):
        BPNNMEAFeedIntake().run(model_input, build_bpnn_context())


def test_pearson_lstm_blocks_execution_without_trained_artifact() -> None:
    with pytest.raises(PearsonLSTMModelArtifactPendingError, match="artifact pending"):
        PearsonLSTMAttentionWaterQuality().run(
            build_lstm_input(),
            build_lstm_context(),
        )


def test_pearson_lstm_allows_metadata_only_output() -> None:
    result = PearsonLSTMAttentionWaterQuality().run(
        build_lstm_input(metadata_only=True),
        build_lstm_context(),
    )

    assert result.model_code == "PEARSON_LSTM_ATTENTION_WQ"
    assert result.outputs["dissolved_oxygen_forecast_mg_l"].unit == "mg/L"
    assert result.outputs["water_quality_risk"].value == "not_computed_artifact_pending"
    assert result.explainability["artifact_status"] == "MODEL_ARTIFACT_PENDING"


def test_pearson_lstm_delegates_to_injected_predictor() -> None:
    def predictor(
        features: dict[str, list[float]],
        parameters: dict[str, object],
    ) -> dict[str, object]:
        assert len(features["ph"]) == 3
        assert parameters["artifact_version"] == "test"
        return {
            "dissolved_oxygen_forecast_mg_l": 5.8,
            "water_quality_risk": "medium",
            "attention_weights": {"ph": 0.2, "dissolved_oxygen_mg_l": 0.8},
            "confidence": 0.7,
        }

    model = PearsonLSTMAttentionWaterQuality(predictor=predictor)

    result = model.run(
        build_lstm_input(artifact_version="test"),
        build_lstm_context(),
    )

    assert result.outputs["dissolved_oxygen_forecast_mg_l"].value == 5.8
    assert result.outputs["water_quality_risk"].value == "medium"
    assert result.confidence == 0.7


def test_pearson_lstm_requires_aligned_time_series() -> None:
    model_input = build_lstm_input(metadata_only=True)
    model_input.inputs["ph"] = ModelInputValue(value=[7.1, 7.2], unit="pH")

    with pytest.raises(ValueError, match="same length"):
        PearsonLSTMAttentionWaterQuality().run(model_input, build_lstm_context())
