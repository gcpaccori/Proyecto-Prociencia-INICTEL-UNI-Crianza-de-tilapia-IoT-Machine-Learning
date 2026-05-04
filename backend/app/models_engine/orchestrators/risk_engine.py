from backend.app.models_engine.base import ModelOutput
from backend.app.models_engine.orchestrators.schemas import (
    DigitalTwinState,
    RiskAssessment,
)


RISK_SCORES = {
    "unknown": None,
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}


class RiskEngine:
    def assess(
        self,
        state: DigitalTwinState,
        model_outputs: list[ModelOutput],
    ) -> list[RiskAssessment]:
        risks: list[RiskAssessment] = []
        risks.extend(self._assess_model_risks(model_outputs))
        risks.extend(self._assess_missing_data(state))
        risks.extend(self._assess_sensor_status(state))

        if not risks:
            return [
                RiskAssessment(
                    risk_code="RISK_BASELINE",
                    risk_level="low",
                    risk_score=RISK_SCORES["low"],
                    source="digital_twin_state",
                    explanation="No explicit model or data quality risks were reported.",
                )
            ]
        return risks

    def _assess_model_risks(
        self,
        model_outputs: list[ModelOutput],
    ) -> list[RiskAssessment]:
        risks: list[RiskAssessment] = []
        for model_output in model_outputs:
            for output_name, output_value in model_output.outputs.items():
                if not output_name.endswith("_risk"):
                    continue
                risk_level = self._normalize_risk_level(output_value.value)
                risks.append(
                    RiskAssessment(
                        risk_code=f"{model_output.model_code}_{output_name}".upper(),
                        risk_level=risk_level,
                        risk_score=RISK_SCORES[risk_level],
                        source=model_output.model_code,
                        explanation=(
                            f"{output_name} reported by {model_output.model_code}."
                        ),
                        evidence={
                            "output_name": output_name,
                            "output_value": output_value.value,
                            "unit": output_value.unit,
                            "model_version": model_output.model_version,
                            "run_id": model_output.run_id,
                        },
                    )
                )
        return risks

    def _assess_missing_data(self, state: DigitalTwinState) -> list[RiskAssessment]:
        missing_sections = list(state.missing_data)
        if not state.water_quality_current:
            missing_sections.append("water_quality_current")
        if not state.biomass_current:
            missing_sections.append("biomass_current")
        if not state.feeding_current:
            missing_sections.append("feeding_current")

        if not missing_sections:
            return []

        return [
            RiskAssessment(
                risk_code="DATA_COMPLETENESS_RISK",
                risk_level="medium",
                risk_score=RISK_SCORES["medium"],
                source="digital_twin_state",
                explanation="Required Digital Twin state sections are missing.",
                evidence={"missing_sections": sorted(set(missing_sections))},
            )
        ]

    def _assess_sensor_status(self, state: DigitalTwinState) -> list[RiskAssessment]:
        inactive = [
            str(sensor_code)
            for sensor_code, status in state.sensor_status.items()
            if str(status).lower() not in {"active", "ok", "online", "healthy"}
        ]
        if not inactive:
            return []

        return [
            RiskAssessment(
                risk_code="SENSOR_STATUS_RISK",
                risk_level="high",
                risk_score=RISK_SCORES["high"],
                source="sensor_status",
                explanation="One or more sensors are not reporting a healthy status.",
                evidence={"sensors": inactive},
            )
        ]

    def _normalize_risk_level(self, value: object) -> str:
        risk_level = str(value).lower()
        if risk_level in RISK_SCORES:
            return risk_level
        if risk_level in {"not_computed_formula_pending", "not_computed", "pending"}:
            return "unknown"
        return "unknown"
