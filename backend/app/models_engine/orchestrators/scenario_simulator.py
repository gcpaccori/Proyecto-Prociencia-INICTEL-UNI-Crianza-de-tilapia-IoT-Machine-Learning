from datetime import datetime

from backend.app.models_engine.base import ModelInput
from backend.app.models_engine.orchestrators.digital_twin_orchestrator import (
    DigitalTwinOrchestrator,
)
from backend.app.models_engine.orchestrators.schemas import DigitalTwinSnapshot


class ScenarioSimulator:
    def __init__(self, orchestrator: DigitalTwinOrchestrator) -> None:
        self.orchestrator = orchestrator

    def simulate(
        self,
        pond_id: str,
        scenario_overrides: dict[str, object],
        timestamp: datetime | None = None,
        model_inputs: dict[str, ModelInput] | None = None,
        operational_constraints: dict[str, object] | None = None,
    ) -> DigitalTwinSnapshot:
        snapshot = self.orchestrator.create_snapshot(
            pond_id=pond_id,
            timestamp=timestamp,
            model_inputs=model_inputs,
            state_overrides=scenario_overrides,
            operational_constraints=operational_constraints,
        )
        traceability = {
            **snapshot.traceability,
            "scenario_overrides": scenario_overrides,
        }
        return snapshot.model_copy(update={"traceability": traceability})
