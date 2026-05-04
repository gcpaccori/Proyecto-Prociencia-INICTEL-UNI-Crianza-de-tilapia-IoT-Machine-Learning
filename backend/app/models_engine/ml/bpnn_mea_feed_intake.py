from collections.abc import Callable

from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.ml.preprocessing import (
    require_non_negative_feature,
    require_positive_feature,
)


class ModelArtifactPendingError(RuntimeError):
    pass


class BPNNMEAFeedIntake(BaseModelRunner):
    model_code = "BPNN_MEA_FEED_INTAKE"
    model_version = "0.1.0"
    source_report = "INFORME017"

    required_inputs = {
        "water_temperature_c": "degC",
        "dissolved_oxygen_mg_l": "mg/L",
        "average_fish_weight_g": "g",
        "fish_number": "count",
    }
    required_outputs = {
        "feed_intake_g": "g",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="machine_learning",
        name="Prediccion de consumo de alimento con BPNN-MEA",
        source_reference="Chen et al., 2020; Informe017 BPNN 4-10-1",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "Arquitectura reportada: 4-10-1.",
            "Preprocesamiento reportado: min-max normalization.",
            "Los pesos y umbrales optimizados por MEA no estan incluidos en el informe.",
            "La inferencia productiva requiere artefacto entrenado versionado.",
        ],
    )

    def __init__(
        self,
        predictor: Callable[[dict[str, float], dict[str, object]], float] | None = None,
    ) -> None:
        self.predictor = predictor

    def validate_inputs(self, model_input: ModelInput) -> None:
        missing = set(self.required_inputs) - set(model_input.inputs)
        if missing:
            raise ValueError(f"Missing required inputs: {', '.join(sorted(missing))}")

        for input_name, expected_unit in self.required_inputs.items():
            input_value = model_input.inputs[input_name]
            if input_value.unit != expected_unit:
                raise ValueError(
                    f"{input_name} must use unit {expected_unit}; "
                    f"received {input_value.unit}"
                )

        require_non_negative_feature(
            "dissolved_oxygen_mg_l",
            model_input.inputs["dissolved_oxygen_mg_l"].value,
        )
        require_positive_feature(
            "average_fish_weight_g",
            model_input.inputs["average_fish_weight_g"].value,
        )
        fish_number = require_positive_feature(
            "fish_number",
            model_input.inputs["fish_number"].value,
        )
        if fish_number != int(fish_number):
            raise ValueError("fish_number must be an integer count")

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        metadata_only = bool(model_input.parameters.get("metadata_only", False))
        dry_run = bool(model_input.parameters.get("dry_run", False))
        if self.predictor is None:
            if not (metadata_only or dry_run):
                raise ModelArtifactPendingError(
                    "Cannot execute model: trained BPNN-MEA artifact pending."
                )
            return self._artifact_pending_output(context)

        features = {
            input_name: float(model_input.inputs[input_name].value)
            for input_name in self.required_inputs
        }
        feed_intake_g = float(self.predictor(features, model_input.parameters))
        if feed_intake_g < 0:
            raise ValueError("predictor returned negative feed_intake_g")

        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "feed_intake_g": ModelOutputValue(value=feed_intake_g, unit="g")
            },
            unit_map=self.required_outputs,
            confidence=None,
            explanation="BPNN-MEA inference delegated to injected trained artifact.",
            explainability={
                "architecture": "4-10-1",
                "preprocessing": ["minmax_normalization"],
                "features": features,
            },
        )

    def _artifact_pending_output(self, context: ModelRunContext) -> ModelOutput:
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={"feed_intake_g": ModelOutputValue(value=None, unit="g")},
            unit_map=self.required_outputs,
            confidence=None,
            warnings=[
                "MODEL_ARTIFACT_PENDING: trained BPNN-MEA weights and MEA thresholds are not available.",
                "Execution allowed only for dry_run or metadata_only.",
            ],
            explanation="Trained model artifact pending; no feed intake prediction computed.",
            explainability={
                "architecture": "4-10-1",
                "preprocessing": ["minmax_normalization"],
                "artifact_status": "MODEL_ARTIFACT_PENDING",
            },
        )
