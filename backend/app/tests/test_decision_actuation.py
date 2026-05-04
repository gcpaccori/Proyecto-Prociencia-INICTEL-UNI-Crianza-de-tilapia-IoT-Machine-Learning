from backend.app.domains.actuation import (
    ActuationPolicyEngine,
    ActuatorStatus,
    SafetyPolicy,
    UserApproval,
)
from backend.app.domains.decision import AlertEngine
from backend.app.models_engine.orchestrators.schemas import Recommendation, RiskAssessment


def build_high_risk() -> RiskAssessment:
    return RiskAssessment(
        risk_code="HYPOXIA_RISK",
        risk_level="high",
        risk_score=0.75,
        source="TEST_MODEL",
        explanation="High hypoxia risk.",
    )


def build_recommendation() -> Recommendation:
    return Recommendation(
        recommendation_code="REVIEW_HYPOXIA_RISK",
        priority="high",
        recommended_action="Review oxygenation before physical actuation.",
        explanation="High hypoxia risk.",
        approval_required=True,
        source_risk_code="HYPOXIA_RISK",
    )


def test_alert_engine_creates_alerts_for_actionable_risks() -> None:
    alerts = AlertEngine().build_alerts(
        risk_assessments=[build_high_risk()],
        recommendations=[build_recommendation()],
    )

    assert len(alerts) == 1
    assert alerts[0].alert_code == "ALERT_HYPOXIA_RISK"
    assert alerts[0].severity == "high"
    assert alerts[0].source_recommendation_code == "REVIEW_HYPOXIA_RISK"


def test_alert_engine_ignores_low_risk() -> None:
    alerts = AlertEngine().build_alerts(
        risk_assessments=[
            RiskAssessment(
                risk_code="BASELINE",
                risk_level="low",
                risk_score=0.25,
                source="state",
                explanation="No actionable risk.",
            )
        ],
        recommendations=[],
    )

    assert alerts == []


def test_actuation_policy_requires_manual_approval() -> None:
    decision = ActuationPolicyEngine().evaluate(
        recommendation=build_recommendation(),
        actuator_statuses=[
            ActuatorStatus(
                actuator_id="ACT-001",
                actuator_type="oxygenator",
                status="online",
            )
        ],
        safety_policy=SafetyPolicy(
            allow_automatic_commands=True,
            allowed_actuator_types=["oxygenator"],
            manual_approval_required=True,
        ),
    )

    assert decision.command_status == "approval_required"
    assert decision.command is None


def test_actuation_policy_blocks_when_automatic_commands_disabled() -> None:
    decision = ActuationPolicyEngine().evaluate(
        recommendation=build_recommendation(),
        actuator_statuses=[
            ActuatorStatus(
                actuator_id="ACT-001",
                actuator_type="oxygenator",
                status="online",
            )
        ],
        safety_policy=SafetyPolicy(
            allow_automatic_commands=False,
            allowed_actuator_types=["oxygenator"],
            manual_approval_required=True,
        ),
        user_approval=UserApproval(approved=True, approved_by="operator-1"),
    )

    assert decision.command_status == "blocked_by_safety_policy"
    assert decision.command is None


def test_actuation_policy_creates_pending_command_after_approval() -> None:
    decision = ActuationPolicyEngine().evaluate(
        recommendation=build_recommendation(),
        actuator_statuses=[
            ActuatorStatus(
                actuator_id="ACT-001",
                actuator_type="oxygenator",
                status="online",
            )
        ],
        safety_policy=SafetyPolicy(
            allow_automatic_commands=True,
            allowed_actuator_types=["oxygenator"],
            manual_approval_required=True,
        ),
        user_approval=UserApproval(approved=True, approved_by="operator-1"),
    )

    assert decision.command_status == "pending_dispatch"
    assert decision.command is not None
    assert decision.command.actuator_id == "ACT-001"
    assert decision.command.command_type == "oxygenation_control"
    assert decision.command.execution_status == "pending_dispatch"


def test_actuation_policy_blocks_without_available_actuator() -> None:
    decision = ActuationPolicyEngine().evaluate(
        recommendation=build_recommendation(),
        actuator_statuses=[
            ActuatorStatus(
                actuator_id="ACT-001",
                actuator_type="feeder",
                status="offline",
            )
        ],
        safety_policy=SafetyPolicy(
            allow_automatic_commands=True,
            allowed_actuator_types=["oxygenator"],
            manual_approval_required=True,
        ),
        user_approval=UserApproval(approved=True, approved_by="operator-1"),
    )

    assert decision.command_status == "blocked_no_available_actuator"
    assert decision.command is None
