from __future__ import annotations

from typing import TYPE_CHECKING

from backend.app.domains.decision.schemas import AlertDraft

if TYPE_CHECKING:
    from backend.app.models_engine.orchestrators.schemas import (
        Recommendation,
        RiskAssessment,
    )


SEVERITY_BY_RISK = {
    "critical": "critical",
    "high": "high",
    "medium": "warning",
    "unknown": "warning",
    "low": "info",
}


class AlertEngine:
    def build_alerts(
        self,
        risk_assessments: list[RiskAssessment],
        recommendations: list[Recommendation],
    ) -> list[AlertDraft]:
        recommendations_by_risk = {
            recommendation.source_risk_code: recommendation
            for recommendation in recommendations
            if recommendation.source_risk_code is not None
        }
        alerts: list[AlertDraft] = []
        for risk in risk_assessments:
            if risk.risk_level == "low":
                continue
            recommendation = recommendations_by_risk.get(risk.risk_code)
            alerts.append(
                AlertDraft(
                    alert_code=f"ALERT_{risk.risk_code}",
                    severity=SEVERITY_BY_RISK.get(risk.risk_level, "warning"),
                    message=risk.explanation,
                    source_risk_code=risk.risk_code,
                    source_recommendation_code=(
                        recommendation.recommendation_code
                        if recommendation is not None
                        else None
                    ),
                    evidence={
                        "risk": risk.model_dump(mode="json"),
                        "recommendation": recommendation.model_dump(mode="json")
                        if recommendation is not None
                        else None,
                    },
                )
            )
        return alerts
