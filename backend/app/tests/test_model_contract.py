from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.models_engine.base import (
    BaseModelRunner,
    ModelInput,
    ModelInputValue,
    ModelMetadata,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)


class EchoModelRunner(BaseModelRunner):
    model_code = "TEST_ECHO_MODEL"
    model_version = "1.0.0"
    source_report = "TEST_REPORT"
    metadata = ModelMetadata(
        model_code=model_code,
        model_version=model_version,
        source_report=source_report,
        model_type="test",
        name="Echo model for contract tests",
        inputs={"temperature": "degC"},
        outputs={"temperature_echo": "degC"},
        units={"temperature": "degC", "temperature_echo": "degC"},
        assumptions=["Only used in tests."],
    )

    def validate_inputs(self, model_input: ModelInput) -> None:
        if "temperature" not in model_input.inputs:
            raise ValueError("temperature is required")

    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        input_value = model_input.inputs["temperature"]
        return ModelOutput(
            model_code=context.model_code,
            model_version=context.model_version,
            source_report=context.source_report,
            outputs={
                "temperature_echo": ModelOutputValue(
                    value=input_value.value,
                    unit=input_value.unit,
                    variable="temperature_echo",
                )
            },
            confidence=0.9,
            explanation="Echoed input temperature.",
            explainability={"input_count": len(model_input.inputs)},
        )


class FakeRunRepository:
    def __init__(self) -> None:
        self.calls = []

    def create_successful_run(
        self,
        model_input: ModelInput,
        model_output: ModelOutput,
        context: ModelRunContext,
    ) -> str:
        self.calls.append((model_input, model_output, context))
        return "RUN-TEST-001"


def test_runner_contract_executes_and_saves_run() -> None:
    runner = EchoModelRunner()
    repository = FakeRunRepository()
    model_input = ModelInput(
        model_code="TEST_ECHO_MODEL",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        pond_id="POND-001",
        inputs={"temperature": ModelInputValue(value=18.5, unit="degC")},
    )
    context = ModelRunContext(
        model_code="TEST_ECHO_MODEL",
        model_version="1.0.0",
        source_report="TEST_REPORT",
        timestamp=model_input.timestamp,
        pond_id="POND-001",
        model_version_id=uuid4(),
    )

    result = runner.run(model_input, context, run_repository=repository)

    assert result.run_id == "RUN-TEST-001"
    assert result.outputs["temperature_echo"].value == 18.5
    assert result.unit_map == {"temperature_echo": "degC"}
    assert result.traceability["model_run_id"] == "RUN-TEST-001"
    assert len(repository.calls) == 1


def test_runner_rejects_mismatched_context() -> None:
    runner = EchoModelRunner()
    model_input = ModelInput(
        model_code="TEST_ECHO_MODEL",
        inputs={"temperature": ModelInputValue(value=18.5, unit="degC")},
    )
    context = ModelRunContext(
        model_code="OTHER_MODEL",
        model_version="1.0.0",
        source_report="TEST_REPORT",
    )

    with pytest.raises(ValueError, match="model_code"):
        runner.run(model_input, context)


def test_model_output_requires_unit_map_for_every_output() -> None:
    with pytest.raises(ValueError, match="unit_map missing"):
        ModelOutput(
            model_code="TEST_ECHO_MODEL",
            model_version="1.0.0",
            source_report="TEST_REPORT",
            outputs={
                "temperature_echo": ModelOutputValue(value=18.5, unit="degC")
            },
            unit_map={"other_output": "degC"},
        )
