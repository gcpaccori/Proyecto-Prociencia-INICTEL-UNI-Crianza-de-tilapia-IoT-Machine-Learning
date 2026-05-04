from collections.abc import Callable

from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.ml.preprocessing import require_numeric_series


class ModelArtifactPendingError(RuntimeError):
    pass


class PearsonLSTMAttentionWaterQuality(BaseModelRunner):
    model_code = "PEARSON_LSTM_ATTENTION_WQ"
    model_version = "0.1.0"
    source_report = "INFORME017"

    required_inputs = {
        "ph": "pH",
        "water_temperature_c": "degC",
        "dissolved_oxygen_mg_l": "mg/L",
        "ammonia_nitrogen_mg_l": "mg/L",
        "nitrite_mg_l": "mg/L",
        "orp_mv": "mV",
        "turbidity_ntu": "NTU",
    }
    required_outputs = {
        "dissolved_oxygen_forecast_mg_l": "mg/L",
        "water_quality_risk": "risk_level",
        "attention_weights": "weight",
        "confidence": "probability",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="deep_learning",
        name="Pearson-LSTM-AM water quality forecast",
        source_reference="Yu et al., 2025; Informe017 Pearson-LSTM-AM",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "Preprocesamiento reportado: interpolacion lineal, 3 sigma, min-max, Pearson.",
            "Arquitectura reportada: capa de entrada, LSTM, atencion y salida.",
            "La inferencia productiva requiere artefacto entrenado versionado.",
            "Las entradas representan series temporales alineadas por tiempo.",
        ],
    )

    def __init__(
        self,
        predictor: Callable[
            [dict[str, list[float]], dict[str, object]],
            dict[str, object],
        ]
        | None = None,
    ) -> None:
        self.predictor = predictor

    def validate_inputs(self, model_input: ModelInput) -> None:
        missing = set(self.required_inputs) - set(model_input.inputs)
        if missing:
            raise ValueError(f"Missing required inputs: {', '.join(sorted(missing))}")

        series_lengths: set[int] = set()
        for input_name, expected_unit in self.required_inputs.items():
            input_value = model_input.inputs[input_name]
            if input_value.unit != expected_unit:
                raise ValueError(
                    f"{input_name} must use unit {expected_unit}; "
                    f"received {input_value.unit}"
                )
            series = require_numeric_series(input_name, input_value.value)
            series_lengths.add(len(series))

        if len(series_lengths) != 1:
            raise ValueError("all input time series must have the same length")

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
                    "Cannot execute model: trained Pearson-LSTM-AM artifact pending."
                )
            return self._artifact_pending_output(context)

        features = {
            input_name: require_numeric_series(
                input_name,
                model_input.inputs[input_name].value,
            )
            for input_name in self.required_inputs
        }
        prediction = self.predictor(features, model_input.parameters)
        forecast = float(prediction["dissolved_oxygen_forecast_mg_l"])
        confidence = prediction.get("confidence")
        if confidence is not None:
            confidence = float(confidence)
            if confidence < 0 or confidence > 1:
                raise ValueError("predictor confidence must be between 0 and 1")

        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "dissolved_oxygen_forecast_mg_l": ModelOutputValue(
                    value=forecast,
                    unit="mg/L",
                ),
                "water_quality_risk": ModelOutputValue(
                    value=str(prediction.get("water_quality_risk", "unknown")),
                    unit="risk_level",
                ),
                "attention_weights": ModelOutputValue(
                    value=prediction.get("attention_weights", {}),
                    unit="weight",
                ),
                "confidence": ModelOutputValue(
                    value=confidence,
                    unit="probability",
                ),
            },
            unit_map=self.required_outputs,
            confidence=confidence,
            explanation=(
                "Pearson-LSTM-AM inference delegated to injected trained artifact."
            ),
            explainability={
                "preprocessing": [
                    "linear_interpolation_for_missing_values",
                    "outlier_filter_3sigma",
                    "minmax_normalization",
                    "pearson_feature_selection",
                ],
                "input_window_size": len(next(iter(features.values()))),
            },
        )

    def _artifact_pending_output(self, context: ModelRunContext) -> ModelOutput:
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "dissolved_oxygen_forecast_mg_l": ModelOutputValue(
                    value=None,
                    unit="mg/L",
                ),
                "water_quality_risk": ModelOutputValue(
                    value="not_computed_artifact_pending",
                    unit="risk_level",
                ),
                "attention_weights": ModelOutputValue(value={}, unit="weight"),
                "confidence": ModelOutputValue(value=None, unit="probability"),
            },
            unit_map=self.required_outputs,
            confidence=None,
            warnings=[
                "MODEL_ARTIFACT_PENDING: trained Pearson-LSTM-AM artifact is not available.",
                "Execution allowed only for dry_run or metadata_only.",
            ],
            explanation="Trained model artifact pending; no water quality forecast computed.",
            explainability={
                "preprocessing": [
                    "linear_interpolation_for_missing_values",
                    "outlier_filter_3sigma",
                    "minmax_normalization",
                    "pearson_feature_selection",
                    "train_test_split_80_20",
                ],
                "artifact_status": "MODEL_ARTIFACT_PENDING",
            },
        )
