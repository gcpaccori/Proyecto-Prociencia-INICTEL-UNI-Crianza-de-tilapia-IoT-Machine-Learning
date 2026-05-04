from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)


class FeedingSatietyRules(BaseModelRunner):
    model_code = "FEEDING_SATIETY_RULES"
    model_version = "1.0.0"
    source_report = "INFORME017"

    behavior_categories = {
        "ACTIVE_CONTINUOUS_FEEDING",
        "MOVE_AND_RETURN",
        "ONLY_FRONT_FEEDING",
        "NO_REACTION",
    }
    required_inputs = {
        "feeding_behavior_category": "category",
        "feed_remaining": "boolean",
        "fish_reaction": "text",
    }
    required_outputs = {
        "stop_feeding": "boolean",
        "feed_waste_risk": "risk_level",
        "recommendation": "text",
    }

    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="rule_based",
        name="Reglas de saciedad alimentaria",
        source_reference="Informe017 feeding reaction categories",
        inputs=required_inputs,
        outputs=required_outputs,
        units={**required_inputs, **required_outputs},
        assumptions=[
            "La cuarta condicion, NO_REACTION, detiene la alimentacion.",
            "La presencia de alimento remanente aumenta el riesgo de desperdicio.",
            "Las reglas no ejecutan actuacion fisica directa.",
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

        category = str(model_input.inputs["feeding_behavior_category"].value)
        if category not in self.behavior_categories:
            raise ValueError("feeding_behavior_category is not supported")
        if not isinstance(model_input.inputs["feed_remaining"].value, bool):
            raise ValueError("feed_remaining must be boolean")

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        category = str(model_input.inputs["feeding_behavior_category"].value)
        feed_remaining = bool(model_input.inputs["feed_remaining"].value)

        stop_feeding = category == "NO_REACTION"
        feed_waste_risk = self._risk_level(category, feed_remaining)
        recommendation = self._recommendation(category, feed_remaining)

        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "stop_feeding": ModelOutputValue(
                    value=stop_feeding,
                    unit="boolean",
                ),
                "feed_waste_risk": ModelOutputValue(
                    value=feed_waste_risk,
                    unit="risk_level",
                ),
                "recommendation": ModelOutputValue(
                    value=recommendation,
                    unit="text",
                ),
            },
            unit_map=self.required_outputs,
            confidence=1.0,
            explanation="Rule-based feeding satiety decision from Informe017.",
            explainability={
                "behavior_category": category,
                "feed_remaining": feed_remaining,
                "source_rule": (
                    "Stop feeding when fish do not react to bait fall; residues "
                    "increase feed waste risk."
                ),
            },
        )

    def _risk_level(self, category: str, feed_remaining: bool) -> str:
        if category == "NO_REACTION":
            return "high"
        if feed_remaining:
            return "medium"
        if category == "ONLY_FRONT_FEEDING":
            return "medium"
        return "low"

    def _recommendation(self, category: str, feed_remaining: bool) -> str:
        if category == "NO_REACTION":
            return "Stop feeding and verify water quality before the next ration."
        if feed_remaining:
            return "Reduce or pause the next feeding round and inspect residual feed."
        if category == "ONLY_FRONT_FEEDING":
            return "Continue cautiously and monitor for feed waste."
        return "Continue feeding under routine monitoring."
