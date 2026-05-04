from backend.app.domains.actuation.schemas import (
    ActuationCommandDraft,
    ActuationDecision,
    ActuatorStatus,
    SafetyPolicy,
    UserApproval,
)
from backend.app.models_engine.orchestrators.schemas import Recommendation


AVAILABLE_STATUSES = {"active", "online", "ready", "healthy", "ok"}


class ActuationPolicyEngine:
    def evaluate(
        self,
        recommendation: Recommendation,
        actuator_statuses: list[ActuatorStatus],
        safety_policy: SafetyPolicy,
        user_approval: UserApproval | None = None,
    ) -> ActuationDecision:
        audit_record = {
            "recommendation_code": recommendation.recommendation_code,
            "priority": recommendation.priority,
            "approval_required": recommendation.approval_required,
            "safety_policy": safety_policy.model_dump(mode="json"),
            "user_approval": user_approval.model_dump(mode="json")
            if user_approval is not None
            else None,
        }

        if recommendation.approval_required or safety_policy.manual_approval_required:
            if user_approval is None or not user_approval.approved:
                return ActuationDecision(
                    command_status="approval_required",
                    audit_record=audit_record,
                    warnings=["Manual approval is required before command dispatch."],
                )

        if not safety_policy.allow_automatic_commands:
            return ActuationDecision(
                command_status="blocked_by_safety_policy",
                audit_record=audit_record,
                warnings=["Automatic command dispatch is disabled by safety policy."],
            )

        actuator = self._select_actuator(actuator_statuses, safety_policy)
        if actuator is None:
            return ActuationDecision(
                command_status="blocked_no_available_actuator",
                audit_record=audit_record,
                warnings=["No available actuator matched the safety policy."],
            )

        command = ActuationCommandDraft(
            actuator_id=actuator.actuator_id,
            command_type=self._command_type_for_recommendation(recommendation),
            command_payload={
                "recommendation_code": recommendation.recommendation_code,
                "recommended_action": recommendation.recommended_action,
                "priority": recommendation.priority,
                "source_risk_code": recommendation.source_risk_code,
            },
            requested_by=user_approval.approved_by if user_approval is not None else None,
            audit_record={
                **audit_record,
                "actuator": actuator.model_dump(mode="json"),
            },
        )
        return ActuationDecision(
            command_status="pending_dispatch",
            command=command,
            audit_record=command.audit_record,
        )

    def _select_actuator(
        self,
        actuator_statuses: list[ActuatorStatus],
        safety_policy: SafetyPolicy,
    ) -> ActuatorStatus | None:
        allowed_types = set(safety_policy.allowed_actuator_types)
        for actuator in actuator_statuses:
            if allowed_types and actuator.actuator_type not in allowed_types:
                continue
            if actuator.status.lower() not in AVAILABLE_STATUSES:
                continue
            return actuator
        return None

    def _command_type_for_recommendation(self, recommendation: Recommendation) -> str:
        text = (
            f"{recommendation.recommendation_code} "
            f"{recommendation.recommended_action}"
        ).lower()
        if "feed" in text or "feeding" in text or "alimento" in text:
            return "feeding_control"
        if "oxygen" in text or "hypoxia" in text or "aireador" in text:
            return "oxygenation_control"
        if "pump" in text or "bomba" in text:
            return "pump_control"
        return "manual_review"
