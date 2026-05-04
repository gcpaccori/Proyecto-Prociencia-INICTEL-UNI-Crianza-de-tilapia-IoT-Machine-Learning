"""SQLAlchemy models for the Phase 2 database schema."""

from backend.app.infrastructure.db.models.actuation import Actuator, Command
from backend.app.infrastructure.db.models.aquaculture import (
    BiomassSampling,
    Channel,
    Farm,
    FeedComposition,
    FeedingEvent,
    FeedProduct,
    FishBatch,
    MortalityEvent,
    Pond,
    Species,
)
from backend.app.infrastructure.db.models.audit import AuditLog
from backend.app.infrastructure.db.models.decision import AlertEvent, Recommendation
from backend.app.infrastructure.db.models.iot import (
    Sensor,
    SensorCalibration,
    SensorMeasurementClean,
    SensorMeasurementRaw,
)
from backend.app.infrastructure.db.models.registry import (
    ModelDefinition,
    ModelInputSchema,
    ModelOutputSchema,
    ModelParameter,
    ModelParameterSet,
    ModelRun,
    ModelRunInput,
    ModelRunOutput,
    ModelSourceReference,
    ModelVersion,
)
from backend.app.infrastructure.db.models.timeseries import ModelPrediction

__all__ = [
    "Actuator",
    "AlertEvent",
    "AuditLog",
    "BiomassSampling",
    "Channel",
    "Command",
    "Farm",
    "FeedComposition",
    "FeedingEvent",
    "FeedProduct",
    "FishBatch",
    "ModelDefinition",
    "ModelInputSchema",
    "ModelOutputSchema",
    "ModelParameter",
    "ModelParameterSet",
    "ModelPrediction",
    "ModelRun",
    "ModelRunInput",
    "ModelRunOutput",
    "ModelSourceReference",
    "ModelVersion",
    "MortalityEvent",
    "Pond",
    "Recommendation",
    "Sensor",
    "SensorCalibration",
    "SensorMeasurementClean",
    "SensorMeasurementRaw",
    "Species",
]
