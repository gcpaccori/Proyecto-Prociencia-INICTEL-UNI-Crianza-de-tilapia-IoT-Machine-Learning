from collections.abc import Callable

from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.vision.common import (
    VisionArtifactPendingError,
    require_mapping,
    require_media_reference,
    require_non_negative_int,
    require_probability,
)


class FishCountingModel(BaseModelRunner):
    model_code = "FISH_COUNTING_MODEL"
    model_version = "0.1.0"
    source_report = "INFORME015"

    required_inputs = {
        "image": "image_ref",
        "video_frame": "frame_ref",
        "camera_calibration": "calibration_json",
    }
    required_outputs = {
        "fish_count": "count",
        "confidence": "probability",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="computer_vision",
        name="Conteo de peces",
        source_reference="Informe015 computer vision fish counting",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "La entrada puede ser una imagen o un frame de video.",
            "La calibracion de camara debe provenir de un proceso externo validado.",
            "La inferencia productiva requiere artefacto de vision entrenado.",
        ],
    )

    def __init__(
        self,
        detector: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
        | None = None,
    ) -> None:
        self.detector = detector

    def validate_inputs(self, model_input: ModelInput) -> None:
        require_media_reference(model_input)
        calibration = model_input.inputs.get("camera_calibration")
        if calibration is None:
            raise ValueError("camera_calibration is required")
        if calibration.unit != "calibration_json":
            raise ValueError(
                "camera_calibration must use unit calibration_json; "
                f"received {calibration.unit}"
            )
        require_mapping("camera_calibration", calibration.value)

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        metadata_only = bool(model_input.parameters.get("metadata_only", False))
        dry_run = bool(model_input.parameters.get("dry_run", False))
        if self.detector is None:
            if not (metadata_only or dry_run):
                raise VisionArtifactPendingError(
                    "Cannot execute model: trained fish counting artifact pending."
                )
            return self._artifact_pending_output(context)

        detection = self.detector(
            self._payload(model_input),
            model_input.parameters,
        )
        fish_count = require_non_negative_int("fish_count", detection["fish_count"])
        confidence = require_probability("confidence", detection["confidence"])

        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "fish_count": ModelOutputValue(value=fish_count, unit="count"),
                "confidence": ModelOutputValue(
                    value=confidence,
                    unit="probability",
                ),
            },
            unit_map=self.required_outputs,
            confidence=confidence,
            explanation="Fish counting delegated to injected trained vision artifact.",
            explainability={
                "artifact": "injected_detector",
                "media_inputs": sorted(
                    name for name in ("image", "video_frame") if name in model_input.inputs
                ),
            },
        )

    def _artifact_pending_output(self, context: ModelRunContext) -> ModelOutput:
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "fish_count": ModelOutputValue(value=None, unit="count"),
                "confidence": ModelOutputValue(value=None, unit="probability"),
            },
            unit_map=self.required_outputs,
            confidence=None,
            warnings=[
                "VISION_ARTIFACT_PENDING: trained fish counting artifact is not available.",
                "Execution allowed only for dry_run or metadata_only.",
            ],
            explanation="Trained vision artifact pending; fish count not computed.",
            explainability={"artifact_status": "VISION_ARTIFACT_PENDING"},
        )

    def _payload(self, model_input: ModelInput) -> dict[str, object]:
        return {
            name: value.model_dump(mode="json")
            for name, value in model_input.inputs.items()
            if name in {"image", "video_frame", "camera_calibration"}
        }
