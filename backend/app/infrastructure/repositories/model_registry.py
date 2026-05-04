from uuid import UUID

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from backend.app.infrastructure.db.models.registry import (
    ModelDefinition,
    ModelInputSchema,
    ModelOutputSchema,
    ModelParameterSet,
    ModelVersion,
)


class ModelRegistryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_definition_by_code(self, model_code: str) -> ModelDefinition | None:
        statement = select(ModelDefinition).where(
            ModelDefinition.model_code == model_code
        )
        return self.session.execute(statement).scalar_one_or_none()

    def list_definitions(self) -> list[ModelDefinition]:
        statement: Select[tuple[ModelDefinition]] = select(ModelDefinition).order_by(
            ModelDefinition.model_code
        )
        return list(self.session.execute(statement).scalars().all())

    def get_active_version(self, model_code: str) -> ModelVersion | None:
        statement = (
            select(ModelVersion)
            .join(
                ModelDefinition,
                ModelVersion.model_definition_id == ModelDefinition.id,
            )
            .where(
                ModelDefinition.model_code == model_code,
                ModelVersion.is_active.is_(True),
            )
            .order_by(desc(ModelVersion.created_at))
            .limit(1)
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_parameter_set(
        self,
        parameter_set_id: UUID,
    ) -> ModelParameterSet | None:
        statement = select(ModelParameterSet).where(
            ModelParameterSet.id == parameter_set_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_input_schema(
        self,
        model_version_id: UUID,
    ) -> ModelInputSchema | None:
        statement = select(ModelInputSchema).where(
            ModelInputSchema.model_version_id == model_version_id
        )
        return self.session.execute(statement).scalar_one_or_none()

    def get_output_schema(
        self,
        model_version_id: UUID,
    ) -> ModelOutputSchema | None:
        statement = select(ModelOutputSchema).where(
            ModelOutputSchema.model_version_id == model_version_id
        )
        return self.session.execute(statement).scalar_one_or_none()
