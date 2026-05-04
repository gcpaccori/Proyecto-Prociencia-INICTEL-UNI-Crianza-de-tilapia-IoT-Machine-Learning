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
    require_non_negative_float,
    require_probability,
    require_text,
)


class FishSizeWeightEstimation(BaseModelRunner):
    model_code = "FISH_SIZE_WEIGHT_ESTIMATION"
    model_version = "0.1.0"
    source_report = "INFORME015"

    required_inputs = {
        "image": "image_ref",
        "video_frame": "frame_ref",
        "calibration_parameters": "calibration_json",
        "species": "text",
    }
    required_outputs = {
        "fish_length": "cm",
        "fish_weight": "g",
        "estimated_biomass": "kg",
        "confidence": "probability",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="computer_vision",
        name="Estimacion de tamano, peso y biomasa",
        source_reference="Informe015 fish metrics and biomass estimation",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "La entrada puede ser una imagen o un frame de video.",
            "La estimacion requiere parametros de calibracion externos.",
            "La inferencia productiva requiere artefacto de vision entrenado.",
            "La biomasa estimada debe trazarse al conteo o detecciones usadas.",
        ],
    )

    def __init__(
        self,
        estimator: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
        | None = None,
    ) -> None:
        self.estimator = estimator

    def validate_inputs(self, model_input: ModelInput) -> None:
        require_media_reference(model_input)
        calibration = model_input.inputs.get("calibration_parameters")
        if calibration is None:
            raise ValueError("calibration_parameters is required")
        if calibration.unit != "calibration_json":
            raise ValueError(
                "calibration_parameters must use unit calibration_json; "
                f"received {calibration.unit}"
            )
        require_mapping("calibration_parameters", calibration.value)

        species = model_input.inputs.get("species")
        if species is None:
            raise ValueError("species is required")
        if species.unit != "text":
            raise ValueError(f"species must use unit text; received {species.unit}")
        require_text("species", species.value)

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        metadata_only = bool(model_input.parameters.get("metadata_only", False))
        dry_run = bool(model_input.parameters.get("dry_run", False))
        if self.estimator is None:
            if not (metadata_only or dry_run):
                raise VisionArtifactPendingError(
                    "Cannot execute model: trained fish size artifact pending."
                )
            return self._artifact_pending_output(context)

        estimation = self.estimator(
            self._payload(model_input),
            model_input.parameters,
        )
        fish_length = require_non_negative_float("fish_length", estimation["fish_length"])
        fish_weight = require_non_negative_float("fish_weight", estimation["fish_weight"])
        estimated_biomass = require_non_negative_float(
            "estimated_biomass",
            estimation["estimated_biomass"],
        )
        confidence = require_probability("confidence", estimation["confidence"])

        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "fish_length": ModelOutputValue(value=fish_length, unit="cm"),
                "fish_weight": ModelOutputValue(value=fish_weight, unit="g"),
                "estimated_biomass": ModelOutputValue(
                    value=estimated_biomass,
                    unit="kg",
                ),
                "confidence": ModelOutputValue(
                    value=confidence,
                    unit="probability",
                ),
            },
            unit_map=self.required_outputs,
            confidence=confidence,
            explanation=(
                "Fish size, weight, and biomass delegated to injected trained "
                "vision artifact."
            ),
            explainability={
                "artifact": "injected_estimator",
                "species": model_input.inputs["species"].value,
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
                "fish_length": ModelOutputValue(value=None, unit="cm"),
                "fish_weight": ModelOutputValue(value=None, unit="g"),
                "estimated_biomass": ModelOutputValue(value=None, unit="kg"),
                "confidence": ModelOutputValue(value=None, unit="probability"),
            },
            unit_map=self.required_outputs,
            confidence=None,
            warnings=[
                "VISION_ARTIFACT_PENDING: trained fish size/weight artifact is not available.",
                "Execution allowed only for dry_run or metadata_only.",
            ],
            explanation="Trained vision artifact pending; fish metrics not computed.",
            explainability={"artifact_status": "VISION_ARTIFACT_PENDING"},
        )

    def _payload(self, model_input: ModelInput) -> dict[str, object]:
        return {
            name: value.model_dump(mode="json")
            for name, value in model_input.inputs.items()
            if name
            in {"image", "video_frame", "calibration_parameters", "species"}
        }
