from abc import ABC, abstractmethod
from typing import Protocol

from backend.app.models_engine.base.model_context import ModelRunContext
from backend.app.models_engine.base.model_input import ModelInput
from backend.app.models_engine.base.model_metadata import ModelMetadata
from backend.app.models_engine.base.model_result import ModelOutput


class ModelRunRepositoryProtocol(Protocol):
    def create_successful_run(
        self,
        model_input: ModelInput,
        model_output: ModelOutput,
        context: ModelRunContext,
    ) -> str:
        ...


class BaseModelRunner(ABC):
    model_code: str
    model_version: str
    source_report: str
    metadata: ModelMetadata

    @abstractmethod
    def validate_inputs(self, model_input: ModelInput) -> None:
        pass

    def preprocess(self, model_input: ModelInput) -> ModelInput:
        return model_input

    @abstractmethod
    def predict(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> ModelOutput:
        pass

    def postprocess(self, model_output: ModelOutput) -> ModelOutput:
        return model_output

    def explain(self, model_output: ModelOutput) -> dict[str, object]:
        return model_output.explainability

    def save_run(
        self,
        model_input: ModelInput,
        model_output: ModelOutput,
        context: ModelRunContext,
        run_repository: ModelRunRepositoryProtocol | None = None,
    ) -> ModelOutput:
        if run_repository is None:
            return model_output

        run_id = run_repository.create_successful_run(
            model_input=model_input,
            model_output=model_output,
            context=context,
        )
        traceability = {
            **model_output.traceability,
            "model_run_id": run_id,
            "parameter_set_id": str(context.parameter_set_id)
            if context.parameter_set_id
            else None,
            "input_window_start": context.input_window_start,
            "input_window_end": context.input_window_end,
        }
        return model_output.model_copy(
            update={
                "run_id": run_id,
                "traceability": traceability,
            }
        )

    def run(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
        run_repository: ModelRunRepositoryProtocol | None = None,
    ) -> ModelOutput:
        self._validate_contract_context(model_input, context)
        self.validate_inputs(model_input)
        clean_input = self.preprocess(model_input)
        prediction = self.predict(clean_input, context)
        result = self.postprocess(prediction)
        self._validate_contract_result(result, context)
        return self.save_run(clean_input, result, context, run_repository)

    def _validate_contract_context(
        self,
        model_input: ModelInput,
        context: ModelRunContext,
    ) -> None:
        if model_input.model_code != self.model_code:
            raise ValueError("ModelInput.model_code does not match runner model_code")
        if context.model_code != self.model_code:
            raise ValueError("ModelRunContext.model_code does not match runner model_code")
        if context.model_version != self.model_version:
            raise ValueError(
                "ModelRunContext.model_version does not match runner model_version"
            )
        if context.source_report != self.source_report:
            raise ValueError(
                "ModelRunContext.source_report does not match runner source_report"
            )

    def _validate_contract_result(
        self,
        model_output: ModelOutput,
        context: ModelRunContext,
    ) -> None:
        if model_output.model_code != context.model_code:
            raise ValueError("ModelOutput.model_code does not match run context")
        if model_output.model_version != context.model_version:
            raise ValueError("ModelOutput.model_version does not match run context")
        if model_output.source_report != context.source_report:
            raise ValueError("ModelOutput.source_report does not match run context")
