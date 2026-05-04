from datetime import datetime, timezone

import pytest

from backend.app.models_engine.base import ModelInput, ModelInputValue, ModelRunContext
from backend.app.models_engine.vision import (
    FishCountingArtifactPendingError,
    FishCountingModel,
    FishSizeWeightArtifactPendingError,
    FishSizeWeightEstimation,
)


def build_counting_input(**parameters: object) -> ModelInput:
    return ModelInput(
        model_code="FISH_COUNTING_MODEL",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={
            "image": ModelInputValue(value="s3://bucket/frame-001.jpg", unit="image_ref"),
            "camera_calibration": ModelInputValue(
                value={"camera_id": "CAM-001", "scale_px_cm": 12.0},
                unit="calibration_json",
            ),
        },
        parameters=parameters,
    )


def build_counting_context() -> ModelRunContext:
    return ModelRunContext(
        model_code="FISH_COUNTING_MODEL",
        model_version="0.1.0",
        source_report="INFORME015",
    )


def build_size_input(**parameters: object) -> ModelInput:
    return ModelInput(
        model_code="FISH_SIZE_WEIGHT_ESTIMATION",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={
            "video_frame": ModelInputValue(
                value="s3://bucket/frame-002.jpg",
                unit="frame_ref",
            ),
            "calibration_parameters": ModelInputValue(
                value={"camera_id": "CAM-001", "scale_px_cm": 12.0},
                unit="calibration_json",
            ),
            "species": ModelInputValue(value="Sparus aurata", unit="text"),
        },
        parameters=parameters,
    )


def build_size_context() -> ModelRunContext:
    return ModelRunContext(
        model_code="FISH_SIZE_WEIGHT_ESTIMATION",
        model_version="0.1.0",
        source_report="INFORME015",
    )


def test_fish_counting_blocks_execution_without_artifact() -> None:
    with pytest.raises(FishCountingArtifactPendingError, match="artifact pending"):
        FishCountingModel().run(build_counting_input(), build_counting_context())


def test_fish_counting_allows_metadata_only_output() -> None:
    result = FishCountingModel().run(
        build_counting_input(metadata_only=True),
        build_counting_context(),
    )

    assert result.model_code == "FISH_COUNTING_MODEL"
    assert result.outputs["fish_count"].unit == "count"
    assert result.outputs["confidence"].unit == "probability"
    assert result.explainability["artifact_status"] == "VISION_ARTIFACT_PENDING"


def test_fish_counting_delegates_to_injected_detector() -> None:
    def detector(
        payload: dict[str, object],
        parameters: dict[str, object],
    ) -> dict[str, object]:
        assert "image" in payload
        assert parameters["artifact_version"] == "test"
        return {"fish_count": 42, "confidence": 0.86}

    result = FishCountingModel(detector=detector).run(
        build_counting_input(artifact_version="test"),
        build_counting_context(),
    )

    assert result.outputs["fish_count"].value == 42
    assert result.confidence == 0.86


def test_fish_counting_validates_media_reference() -> None:
    model_input = build_counting_input(metadata_only=True)
    del model_input.inputs["image"]

    with pytest.raises(ValueError, match="image or video_frame"):
        FishCountingModel().run(model_input, build_counting_context())


def test_fish_size_weight_blocks_execution_without_artifact() -> None:
    with pytest.raises(FishSizeWeightArtifactPendingError, match="artifact pending"):
        FishSizeWeightEstimation().run(build_size_input(), build_size_context())


def test_fish_size_weight_allows_metadata_only_output() -> None:
    result = FishSizeWeightEstimation().run(
        build_size_input(metadata_only=True),
        build_size_context(),
    )

    assert result.model_code == "FISH_SIZE_WEIGHT_ESTIMATION"
    assert result.outputs["fish_length"].unit == "cm"
    assert result.outputs["fish_weight"].unit == "g"
    assert result.outputs["estimated_biomass"].unit == "kg"
    assert result.explainability["artifact_status"] == "VISION_ARTIFACT_PENDING"


def test_fish_size_weight_delegates_to_injected_estimator() -> None:
    def estimator(
        payload: dict[str, object],
        parameters: dict[str, object],
    ) -> dict[str, object]:
        assert payload["species"]["value"] == "Sparus aurata"
        assert parameters["artifact_version"] == "test"
        return {
            "fish_length": 18.4,
            "fish_weight": 120.0,
            "estimated_biomass": 5.04,
            "confidence": 0.8,
        }

    result = FishSizeWeightEstimation(estimator=estimator).run(
        build_size_input(artifact_version="test"),
        build_size_context(),
    )

    assert result.outputs["fish_length"].value == 18.4
    assert result.outputs["fish_weight"].value == 120.0
    assert result.outputs["estimated_biomass"].value == 5.04
    assert result.confidence == 0.8


def test_fish_size_weight_validates_species() -> None:
    model_input = build_size_input(metadata_only=True)
    model_input.inputs["species"] = ModelInputValue(value="", unit="text")

    with pytest.raises(ValueError, match="species"):
        FishSizeWeightEstimation().run(model_input, build_size_context())
