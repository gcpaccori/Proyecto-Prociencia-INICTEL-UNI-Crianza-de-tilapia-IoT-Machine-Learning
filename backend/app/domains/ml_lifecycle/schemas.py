from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DatasetSource(BaseModel):
    source_code: str
    source_type: str
    database_name: str | None = None
    table_name: str | None = None
    access_mode: str
    status: str
    notes: list[str] = Field(default_factory=list)


class DatasetVariableCoverage(BaseModel):
    pond_id: str | None
    variable_code: str
    unit: str | None = None
    records: int
    first_time: datetime | None = None
    last_time: datetime | None = None
    missing_count: int = 0
    outlier_count: int = 0
    completeness_ratio: float
    trainable: bool


class DatasetCoverage(BaseModel):
    pond_id: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    total_records: int
    variables: list[DatasetVariableCoverage]
    trainable_variables: list[str]
    warnings: list[str] = Field(default_factory=list)


class DatasetReadiness(BaseModel):
    pond_id: str | None
    model_code: str
    status: str
    required_variables: list[str]
    available_variables: list[str]
    missing_variables: list[str]
    minimum_records_required: int
    records_by_variable: dict[str, int]
    can_train: bool
    notes: list[str] = Field(default_factory=list)


class CleaningRunRequest(BaseModel):
    pond_id: str | None = None
    variable_codes: list[str] = Field(default_factory=list)
    apply_interpolation: bool = True
    apply_sigma3: bool = True
    apply_minmax: bool = False
    overwrite_clean_measurements: bool = False


class CleaningRunStepRead(BaseModel):
    step_name: str
    status: str
    details: dict[str, object] = Field(default_factory=dict)


class CleaningRunRead(BaseModel):
    run_id: str
    pond_id: str | None = None
    variable_codes: list[str]
    status: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    records_in: int = 0
    records_out: int = 0
    interpolated_points: int = 0
    outliers_detected: int = 0
    normalized_points: int = 0
    steps: list[CleaningRunStepRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FeatureBuildRequest(BaseModel):
    pond_id: str
    target_variable: str
    feature_variables: list[str]
    cleaning_run_id: str | None = None
    window_size: int = 1
    horizon: int = 1
    pearson_threshold: float | None = None
    train_fraction: float = 0.7
    validation_fraction: float = 0.15


class FeatureSetColumnRead(BaseModel):
    name: str
    role: str
    source_variable: str
    unit: str | None = None
    pearson_score: float | None = None


class FeatureSetRead(BaseModel):
    feature_set_id: str
    pond_id: str
    target_variable: str
    feature_variables: list[str]
    cleaning_run_id: str | None = None
    window_size: int
    horizon: int
    rows_count: int
    train_rows: int
    validation_rows: int
    test_rows: int
    columns: list[FeatureSetColumnRead]
    rows: list[dict[str, object]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    status: str = "ready"
    warnings: list[str] = Field(default_factory=list)


class FeatureSetPreview(BaseModel):
    feature_set_id: str
    rows_count: int
    preview_rows: list[dict[str, object]]
    columns: list[FeatureSetColumnRead]


class TrainingJobRequest(BaseModel):
    model_code: str
    feature_set_id: str
    hyperparameters: dict[str, object] = Field(default_factory=dict)
    auto_activate: bool = False


class TrainingJobEventRead(BaseModel):
    event_id: str
    job_id: str
    event_type: str
    message: str
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class TrainingJobRead(BaseModel):
    job_id: str
    model_code: str
    feature_set_id: str
    status: str
    requested_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    hyperparameters: dict[str, object] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    asset_id: str | None = None
    error_message: str | None = None


class ModelAssetRead(BaseModel):
    asset_id: str
    model_code: str
    version: str
    artifact_path: str
    artifact_format: str
    artifact_payload: dict[str, object] = Field(default_factory=dict)
    feature_set_id: str
    training_job_id: str
    metrics_json: dict[str, float] = Field(default_factory=dict)
    status: str
    created_at: datetime = Field(default_factory=utc_now)
    activated_at: datetime | None = None
    deprecated_at: datetime | None = None


class ModelAssetPredictionRequest(BaseModel):
    features: dict[str, float]


class ModelAssetPredictionRead(BaseModel):
    model_code: str
    asset_id: str
    version: str
    prediction: float | int | str
    feature_names: list[str]
    traceability: dict[str, object] = Field(default_factory=dict)


class ModelAssetPredictionHistoryRead(BaseModel):
    prediction_id: str
    asset_id: str
    model_code: str
    version: str
    feature_set_id: str
    training_job_id: str
    features: dict[str, float]
    prediction: float | int | str
    status: str = "completed"
    created_at: datetime = Field(default_factory=utc_now)


class ModelLifecycleDetailRead(BaseModel):
    model_code: str
    pond_id: str | None = None
    readiness: DatasetReadiness
    active_asset: ModelAssetRead | None = None
    latest_training_job: TrainingJobRead | None = None
    feature_set: FeatureSetRead | None = None
    recent_predictions: list[ModelAssetPredictionHistoryRead] = Field(default_factory=list)
    steps: list[dict[str, object]] = Field(default_factory=list)
    recommendation: str


class TrainableModelRead(BaseModel):
    model_code: str
    name: str
    family: str
    lifecycle_status: str
    required_variables: list[str]
    active_asset_id: str | None = None
    latest_metrics: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class ModelPortfolioRead(BaseModel):
    model_code: str
    name: str
    family: str
    pond_id: str | None = None
    can_train: bool
    readiness_status: str
    required_variables: list[str] = Field(default_factory=list)
    available_variables: list[str] = Field(default_factory=list)
    missing_variables: list[str] = Field(default_factory=list)
    records_by_variable: dict[str, int] = Field(default_factory=dict)
    training_runs: int = 0
    completed_training_runs: int = 0
    version_count: int = 0
    versions: list[str] = Field(default_factory=list)
    active_asset_id: str | None = None
    active_version: str | None = None
    active_metrics: dict[str, float] = Field(default_factory=dict)
    active_since: datetime | None = None
    active_route: str | None = None
    best_asset_id: str | None = None
    best_version: str | None = None
    best_metrics: dict[str, float] = Field(default_factory=dict)
    latest_job_id: str | None = None
    latest_job_status: str | None = None
    last_trained_at: datetime | None = None


class MLLifecycleStatus(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    datasets_enabled: bool
    cleaning_enabled: bool
    features_enabled: bool
    training_enabled: bool
    model_assets_enabled: bool
    total_feature_sets: int
    total_training_jobs: int
    total_model_assets: int
    active_model_assets: int
    routes: dict[str, str]
