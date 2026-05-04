from pydantic import BaseModel, Field, model_validator


class ModelOutputValue(BaseModel):
    value: object
    unit: str = Field(min_length=1)
    variable: str | None = None


class ModelOutput(BaseModel):
    model_code: str
    model_version: str
    source_report: str
    outputs: dict[str, ModelOutputValue]
    unit_map: dict[str, str] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)
    explanation: str | None = None
    explainability: dict[str, object] = Field(default_factory=dict)
    run_id: str | None = None
    traceability: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_units_for_outputs(self) -> "ModelOutput":
        output_units = {name: output.unit for name, output in self.outputs.items()}
        if not self.unit_map:
            self.unit_map = output_units
        missing_units = set(self.outputs) - set(self.unit_map)
        if missing_units:
            missing = ", ".join(sorted(missing_units))
            raise ValueError(f"unit_map missing output units: {missing}")
        return self
