from backend.app.models_engine.base import ModelOutput
from backend.app.models_engine.orchestrators.schemas import (
    Recommendation,
    RiskAssessment,
)


class RecommendationEngine:
    def generate(
        self,
        risk_assessments: list[RiskAssessment],
        model_outputs: list[ModelOutput],
        operational_constraints: dict[str, object] | None = None,
    ) -> list[Recommendation]:
        constraints = operational_constraints or {}
        recommendations: list[Recommendation] = []

        for risk in risk_assessments:
            if risk.risk_level in {"critical", "high"}:
                recommendations.append(
                    Recommendation(
                        recommendation_code=f"REVIEW_{risk.risk_code}",
                        priority="urgent" if risk.risk_level == "critical" else "high",
                        recommended_action=(
                            "Review the pond condition, validate source data, and "
                            "confirm operational response before physical actuation."
                        ),
                        explanation=risk.explanation,
                        approval_required=True,
                        source_risk_code=risk.risk_code,
                        evidence={
                            "risk": risk.model_dump(mode="json"),
                            "constraints": constraints,
                        },
                    )
                )
            elif risk.risk_level == "medium":
                recommendations.append(
                    Recommendation(
                        recommendation_code=f"MONITOR_{risk.risk_code}",
                        priority="medium",
                        recommended_action=(
                            "Complete missing data or monitor the condition before "
                            "running prescriptive actions."
                        ),
                        explanation=risk.explanation,
                        approval_required=True,
                        source_risk_code=risk.risk_code,
                        evidence={
                            "risk": risk.model_dump(mode="json"),
                            "constraints": constraints,
                        },
                    )
                )
            elif risk.risk_level == "unknown":
                recommendations.append(
                    Recommendation(
                        recommendation_code=f"VALIDATE_{risk.risk_code}",
                        priority="medium",
                        recommended_action=(
                            "Validate model readiness and source data before using "
                            "this result for operational decisions."
                        ),
                        explanation=risk.explanation,
                        approval_required=True,
                        source_risk_code=risk.risk_code,
                        evidence={
                            "risk": risk.model_dump(mode="json"),
                            "model_outputs": [
                                output.model_code for output in model_outputs
                            ],
                        },
                    )
                )

        if recommendations:
            return recommendations

        return [
            Recommendation(
                recommendation_code="CONTINUE_MONITORING",
                priority="low",
                recommended_action="Continue routine monitoring.",
                explanation="No actionable Digital Twin risk was detected.",
                approval_required=False,
                evidence={"model_outputs": [output.model_code for output in model_outputs]},
            )
        ]
