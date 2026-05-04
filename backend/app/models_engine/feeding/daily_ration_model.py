from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)


class DailyRationModel(BaseModelRunner):
    model_code = "DAILY_RATION_MODEL"
    model_version = "1.0.0"
    source_report = "INFORME017"

    required_inputs = {
        "feed_conversion_ratio": "ratio",
        "daily_growth": "cm/day",
        "fish_length": "cm",
        "fish_weight": "g",
    }
    required_outputs = {
        "feed_percentage_body_weight": "%",
        "feed_amount_g_day": "g/day",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="mechanistic",
        name="Modelo de racion diaria",
        source_reference="Informe017 equation 10",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "La longitud del pez y el crecimiento diario usan unidades compatibles.",
            "La formula textual usada es F = ((3 * C * daily_growth) / L) * 100.",
            "fish_weight corresponde al peso individual actual.",
        ],
    )

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
            self._require_non_negative_number(input_name, input_value.value)

        self._require_positive_number(
            "fish_length",
            model_input.inputs["fish_length"].value,
        )
        self._require_positive_number(
            "fish_weight",
            model_input.inputs["fish_weight"].value,
        )

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        feed_conversion_ratio = float(
            model_input.inputs["feed_conversion_ratio"].value
        )
        daily_growth = float(model_input.inputs["daily_growth"].value)
        fish_length = float(model_input.inputs["fish_length"].value)
        fish_weight = float(model_input.inputs["fish_weight"].value)

        feed_percentage = ((3 * feed_conversion_ratio * daily_growth) / fish_length) * 100
        feed_amount_g_day = fish_weight * (feed_percentage / 100)

        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "feed_percentage_body_weight": ModelOutputValue(
                    value=feed_percentage,
                    unit="%",
                ),
                "feed_amount_g_day": ModelOutputValue(
                    value=feed_amount_g_day,
                    unit="g/day",
                ),
            },
            unit_map=self.required_outputs,
            confidence=None,
            explanation="Daily ration calculated from Informe017 equation 10.",
            explainability={
                "formula": "F = ((3 * C * daily_growth) / fish_length) * 100",
                "feed_amount_formula": "fish_weight * F / 100",
            },
        )

    @staticmethod
    def _require_non_negative_number(name: str, value: object) -> None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if numeric_value < 0:
            raise ValueError(f"{name} must be non-negative")

    @staticmethod
    def _require_positive_number(name: str, value: object) -> None:
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if numeric_value <= 0:
            raise ValueError(f"{name} must be positive")
