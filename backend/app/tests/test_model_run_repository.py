from datetime import datetime, timezone
from uuid import uuid4

import pytest

from backend.app.infrastructure.db.models.registry import (
    ModelRun,
    ModelRunInput,
    ModelRunOutput,
)
from backend.app.infrastructure.repositories.model_run import ModelRunRepository
from backend.app.models_engine.base import (
    ModelInput,
    ModelInputValue,
    ModelOutput,
    ModelOutputValue,
    ModelRunContext,
)


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.flush_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1


def test_model_run_repository_persists_run_inputs_and_outputs() -> None:
    session = FakeSession()
    repository = ModelRunRepository(session=session)
    model_version_id = uuid4()
    parameter_set_id = uuid4()
    measurement_id = uuid4()
    model_input = ModelInput(
        model_code="TEST_ECHO_MODEL",
        timestamp=datetime(2026, 5, 4, tzinfo=timezone.utc),
        inputs={
            "temperature": ModelInputValue(
                value=18.5,
                unit="degC",
                source_measurement_id=measurement_id,
            )
        },
        parameters={"alpha": 1.0},
    )
    model_output = ModelOutput(
        model_code="TEST_ECHO_MODEL",
        model_version="1.0.0",
        source_report="TEST_REPORT",
        outputs={
            "temperature_echo": ModelOutputValue(value=18.5, unit="degC")
        },
        confidence=0.8,
        warnings=["test warning"],
    )
    context = ModelRunContext(
        model_code="TEST_ECHO_MODEL",
        model_version="1.0.0",
        source_report="TEST_REPORT",
        timestamp=model_input.timestamp,
        model_version_id=model_version_id,
        parameter_set_id=parameter_set_id,
    )

    run_code = repository.create_successful_run(
        model_input=model_input,
        model_output=model_output,
        context=context,
    )

    assert run_code.startswith("RUN-")
    assert session.flush_count == 1
    assert any(isinstance(item, ModelRun) for item in session.added)
    assert any(isinstance(item, ModelRunInput) for item in session.added)
    assert any(isinstance(item, ModelRunOutput) for item in session.added)

    run = next(item for item in session.added if isinstance(item, ModelRun))
    assert run.model_version_id == model_version_id
    assert run.parameter_set_id == parameter_set_id
    assert run.model_code == "TEST_ECHO_MODEL"
    assert run.execution_status == "success"
    assert run.warnings == ["test warning"]


def test_model_run_repository_requires_model_version_id() -> None:
    repository = ModelRunRepository(session=FakeSession())
    model_input = ModelInput(
        model_code="TEST_ECHO_MODEL",
        inputs={"temperature": ModelInputValue(value=18.5, unit="degC")},
    )
    model_output = ModelOutput(
        model_code="TEST_ECHO_MODEL",
        model_version="1.0.0",
        source_report="TEST_REPORT",
        outputs={
            "temperature_echo": ModelOutputValue(value=18.5, unit="degC")
        },
    )
    context = ModelRunContext(
        model_code="TEST_ECHO_MODEL",
        model_version="1.0.0",
        source_report="TEST_REPORT",
    )

    with pytest.raises(ValueError, match="model_version_id"):
        repository.create_successful_run(model_input, model_output, context)
