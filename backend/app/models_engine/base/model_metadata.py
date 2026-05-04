from pydantic import BaseModel, Field


class ModelMetadata(BaseModel):
    model_code: str
    model_version: str
    source_report: str
    model_type: str
    name: str
    source_reference: str | None = None
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
