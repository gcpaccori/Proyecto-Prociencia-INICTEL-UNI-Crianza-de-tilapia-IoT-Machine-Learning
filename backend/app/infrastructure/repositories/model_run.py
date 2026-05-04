from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.registry import (
    ModelRun,
    ModelRunInput,
    ModelRunOutput,
)
from backend.app.infrastructure.db.models.mixins import utc_now
from backend.app.models_engine.base.model_context import ModelRunContext
from backend.app.models_engine.base.model_input import ModelInput
from backend.app.models_engine.base.model_result import ModelOutput


class ModelRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_successful_run(
        self,
        model_input: ModelInput,
        model_output: ModelOutput,
        context: ModelRunContext,
    ) -> str:
        if context.model_version_id is None:
            raise ValueError("model_version_id is required to persist model_run")

        now = utc_now()
        run_id = uuid4()
        run_code = f"RUN-{run_id}"
        model_run = ModelRun(
            id=run_id,
            run_code=run_code,
            model_version_id=context.model_version_id,
            parameter_set_id=context.parameter_set_id,
            model_code=model_output.model_code,
            model_version=model_output.model_version,
            source_report=model_output.source_report,
            source_reference=context.source_reference,
            input_data=_jsonable(model_input),
            parameters=_jsonable(model_input.parameters),
            output_data=_jsonable(model_output.outputs),
            warnings=list(model_output.warnings),
            confidence=Decimal(str(model_output.confidence))
            if model_output.confidence is not None
            else None,
            execution_status="success",
            error_message=None,
            started_at=context.timestamp,
            finished_at=now,
            created_at=now,
        )
        self.session.add(model_run)

        for input_name, input_value in model_input.inputs.items():
            self.session.add(
                ModelRunInput(
                    id=uuid4(),
                    model_run_id=run_id,
                    input_name=input_name,
                    input_value=_jsonable(input_value),
                    unit=input_value.unit,
                    source_measurement_id=input_value.source_measurement_id,
                    created_at=now,
                )
            )

        for output_name, output_value in model_output.outputs.items():
            self.session.add(
                ModelRunOutput(
                    id=uuid4(),
                    model_run_id=run_id,
                    output_name=output_name,
                    output_value=_jsonable(output_value),
                    unit=output_value.unit,
                    created_at=now,
                )
            )

        self.session.flush()
        return run_code


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
