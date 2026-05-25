from datetime import datetime, timezone

from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelInputValue,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)
from backend.app.models_engine.orchestrators import (
    DigitalTwinOrchestrator,
    RecommendationEngine,
    RiskEngine,
    ScenarioSimulator,
    build_default_model_suite,
    default_model_codes,
)
from backend.app.models_engine.orchestrators.schemas import RiskAssessment


class FakeDigitalTwinStateProvider:
    def load_water_quality_current(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        return {
            "dissolved_oxygen_mg_l": ModelInputValue(value=6.2, unit="mg/L"),
            "water_temperature_c": ModelInputValue(value=18.5, unit="degC"),
        }

    def load_recent_sensor_measurements(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> list[dict[str, object]]:
        return [{"variable_code": "dissolved_oxygen", "value": 6.2, "unit": "mg/L"}]

    def load_current_biomass(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        return {"fish_biomass_kg": ModelInputValue(value=120.0, unit="kg")}

    def load_recent_feeding(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        return {"feed_amount_g": 900.0, "unit": "g"}

    def load_sensor_status(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        return {"DO-001": "online"}


class FakeSnapshotRepository:
    def __init__(self) -> None:
        self.saved = []

    def save_snapshot(self, snapshot) -> str:
        self.saved.append(snapshot)
        return "DT-SNAPSHOT-SAVED"


class ExtendedDigitalTwinStateProvider(FakeDigitalTwinStateProvider):
    def load_current_mortality(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> dict[str, object]:
        return {"mortality_count": 0, "unit": "count"}

    def load_recent_operational_events(
        self,
        pond_id: str,
        timestamp: datetime,
    ) -> list[dict[str, object]]:
        return [{"event_type": "manual_inspection", "status": "ok"}]


class FakeRiskModelRunner(BaseModelRunner):
    model_code = "TEST_RISK_MODEL"
    model_version = "1.0.0"
    source_report = "TEST_REPORT"
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="rule_based",
        name="Risk model test double",
        inputs={"observed_risk": "risk_level"},
        outputs={"hypoxia_risk": "risk_level"},
        units={"observed_risk": "risk_level", "hypoxia_risk": "risk_level"},
        assumptions=["Only used in tests."],
    )

    def validate_inputs(self, model_input: ModelInput) -> None:
        if "observed_risk" not in model_input.inputs:
            raise ValueError("observed_risk is required")

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "hypoxia_risk": ModelOutputValue(
                    value=model_input.inputs["observed_risk"].value,
                    unit="risk_level",
                )
            },
        )


def test_orchestrator_creates_snapshot_with_models_risks_and_recommendations() -> None:
    snapshot_repository = FakeSnapshotRepository()
    orchestrator = DigitalTwinOrchestrator(
        model_runners=[FakeRiskModelRunner()],
        state_provider=FakeDigitalTwinStateProvider(),
        snapshot_repository=snapshot_repository,
    )
    model_input = ModelInput(
        model_code="TEST_RISK_MODEL",
        inputs={"observed_risk": ModelInputValue(value="high", unit="risk_level")},
    )

    snapshot = orchestrator.create_snapshot(
        pond_id="POND-001",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        model_inputs={"TEST_RISK_MODEL": model_input},
    )

    assert snapshot.snapshot_id == "DT-SNAPSHOT-SAVED"
    assert snapshot.current_state.pond_id == "POND-001"
    assert snapshot.model_outputs[0].model_code == "TEST_RISK_MODEL"
    assert snapshot.risk_assessments[0].risk_level == "high"
    assert snapshot.recommendations[0].priority == "high"
    assert snapshot.recommendations[0].approval_required is True
    assert snapshot.alerts[0].alert_code.startswith("ALERT_")
    assert snapshot.traceability["model_codes_executed"] == ["TEST_RISK_MODEL"]
    assert len(snapshot_repository.saved) == 1


def test_orchestrator_records_skipped_models_without_input() -> None:
    orchestrator = DigitalTwinOrchestrator(
        model_runners=[FakeRiskModelRunner()],
        state_provider=FakeDigitalTwinStateProvider(),
    )

    snapshot = orchestrator.create_snapshot(pond_id="POND-001")

    assert snapshot.model_outputs == []
    assert snapshot.traceability["model_codes_skipped"] == ["TEST_RISK_MODEL"]
    assert snapshot.recommendations[0].recommendation_code == "CONTINUE_MONITORING"


def test_risk_engine_reports_missing_state_sections() -> None:
    orchestrator = DigitalTwinOrchestrator()

    snapshot = orchestrator.create_snapshot(pond_id="POND-001")

    assert any(
        risk.risk_code == "DATA_COMPLETENESS_RISK"
        for risk in snapshot.risk_assessments
    )
    assert snapshot.recommendations[0].priority == "medium"


def test_recommendation_engine_requires_approval_for_high_risk() -> None:
    recommendation_engine = RecommendationEngine()
    risk = RiskAssessment(
        risk_code="HYPOXIA_RISK",
        risk_level="high",
        risk_score=0.75,
        source="TEST_RISK_MODEL",
        explanation="High hypoxia risk reported.",
    )

    recommendations = recommendation_engine.generate([risk], model_outputs=[])

    assert recommendations[0].priority == "high"
    assert recommendations[0].approval_required is True
    assert recommendations[0].source_risk_code == "HYPOXIA_RISK"


def test_scenario_simulator_applies_state_overrides() -> None:
    orchestrator = DigitalTwinOrchestrator(
        state_provider=FakeDigitalTwinStateProvider(),
        risk_engine=RiskEngine(),
    )
    simulator = ScenarioSimulator(orchestrator)

    snapshot = simulator.simulate(
        pond_id="POND-001",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        scenario_overrides={
            "water_quality_current": {
                "dissolved_oxygen_mg_l": ModelInputValue(value=4.1, unit="mg/L")
            }
        },
    )

    assert snapshot.current_state.water_quality_current[
        "dissolved_oxygen_mg_l"
    ].value == 4.1
    assert "scenario_overrides" in snapshot.traceability


def test_default_model_suite_registers_implemented_model_codes() -> None:
    expected_codes = {
        "DO_DYNAMIC_0D_ROYER_2021",
        "BIOENERGETIC_SPARUS_AURATA_BRIGOLIN_2010",
        "FEEDING_SATIETY_RULES",
        "DAILY_RATION_MODEL",
        "BPNN_MEA_FEED_INTAKE",
        "PEARSON_LSTM_ATTENTION_WQ",
        "FISH_COUNTING_MODEL",
        "FISH_SIZE_WEIGHT_ESTIMATION",
        "DO_TRANSPORT_1D",
        "RAS_OXYGEN_BALANCE",
        "YI_ENVIRONMENTAL_GROWTH",
        "SODERBERG_LINEAR_GROWTH",
        "ZOOTECHNIC_INDEXES",
    }

    assert set(default_model_codes()) == expected_codes
    assert {runner.model_code for runner in build_default_model_suite()} == expected_codes


def test_orchestrator_with_default_suite_tracks_registered_models() -> None:
    orchestrator = DigitalTwinOrchestrator(
        model_runners=build_default_model_suite(),
        state_provider=FakeDigitalTwinStateProvider(),
    )

    snapshot = orchestrator.create_snapshot(pond_id="POND-001")

    assert set(snapshot.traceability["model_codes_registered"]) == set(
        default_model_codes()
    )
    assert set(snapshot.traceability["model_codes_skipped"]) == set(
        default_model_codes()
    )


def test_orchestrator_loads_optional_mortality_and_operational_events() -> None:
    orchestrator = DigitalTwinOrchestrator(
        state_provider=ExtendedDigitalTwinStateProvider(),
    )

    snapshot = orchestrator.create_snapshot(
        pond_id="POND-001",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
    )

    assert snapshot.current_state.mortality_current["mortality_count"] == 0
    assert snapshot.current_state.operational_events[0]["event_type"] == "manual_inspection"
    assert snapshot.state_summary["has_mortality_data"] is True
    assert snapshot.state_summary["operational_events_count"] == 1
