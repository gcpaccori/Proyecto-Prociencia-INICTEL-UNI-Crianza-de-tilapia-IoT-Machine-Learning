from __future__ import annotations

import base64
import pickle
from datetime import datetime, timezone
from uuid import uuid4

from backend.app.application.store import InMemoryBackendStore
from backend.app.domains.measurements import CleanMeasurementRead
from backend.app.domains.ml_lifecycle import (
    CleaningRunRead,
    CleaningRunRequest,
    CleaningRunStepRead,
    DatasetCoverage,
    DatasetReadiness,
    DatasetSource,
    DatasetVariableCoverage,
    FeatureBuildRequest,
    FeatureSetColumnRead,
    FeatureSetPreview,
    FeatureSetRead,
    MLLifecycleStatus,
    ModelLifecycleDetailRead,
    ModelAssetPredictionRead,
    ModelAssetPredictionHistoryRead,
    ModelAssetRead,
    TrainableModelRead,
    TrainingJobEventRead,
    TrainingJobRead,
    TrainingJobRequest,
)
from backend.app.models_engine.ml.preprocessing import (
    linear_interpolate_missing,
    pearson_correlation,
    regression_metrics,
    sigma3_flags,
    temporal_train_validation_test_split,
)
from backend.app.models_engine.ml.tabular_algorithms import (
    kmeans_fit,
    linear_regression_fit_gradient_descent,
    linear_regression_predict,
)


MIN_TRAINING_RECORDS = 8


TRAINABLE_MODEL_VARIABLES: dict[str, list[str]] = {
    "ML_SUPERVISED_LINEAR_REG": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "ML_SUPERVISED_LOGISTIC_REG": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "ML_NONLINEAR_DECISION_TREE": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "ML_NONLINEAR_RANDOM_FOREST": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "ML_NONLINEAR_SVM": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "ML_NONSUPERVISED_KNN": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "ML_UNSUPERVISED_KMEANS": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
    ],
    "ML_UNSUPERVISED_PCA": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
    ],
    "ML_NONSUPERVISED_SOM": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
    ],
    "PEARSON_LSTM_ATTENTION_WQ": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "LSTM_TRADITIONAL_WQ": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "PEARSON_LSTM_BASE": [
        "water_temperature_c",
        "ph",
        "nitrate_ion",
        "dissolved_oxygen_mg_l",
    ],
    "BPNN_MEA_FEED_INTAKE": [
        "water_temperature_c",
        "dissolved_oxygen_mg_l",
        "average_weight_g",
        "fish_count",
    ],
}


class MLLifecycleService:
    def __init__(self, store: InMemoryBackendStore) -> None:
        self.store = store

    def list_sources(self) -> list[DatasetSource]:
        return [
            DatasetSource(
                source_code="legacy_mysql_sismapiscis",
                source_type="mysql_legacy",
                database_name=getattr(self.store, "legacy_database_name", "sismapiscis"),
                table_name="parametro_aguas",
                access_mode="read_only",
                status="available",
                notes=["Fuente legacy sincronizada sin modificar tablas originales."],
            ),
            DatasetSource(
                source_code="app_mysql_aquaculture_digital_twin",
                source_type="mysql_app",
                database_name="aquaculture_digital_twin",
                table_name="raw_measurements, clean_measurements, model_assets",
                access_mode="read_write_app_only",
                status="available",
                notes=["Base propia para limpieza, features, jobs, artefactos e inferencia."],
            ),
        ]

    def sync_legacy(self) -> dict[str, object]:
        sync = getattr(self.store, "sync_legacy_data", None)
        if callable(sync):
            sync(force=True)
            return {"status": "completed", "source": "legacy_mysql_sismapiscis"}
        return {
            "status": "skipped",
            "source": "in_memory_store",
            "note": "El store local no tiene base legacy que sincronizar.",
        }

    def coverage(self, pond_id: str | None = None) -> DatasetCoverage:
        rows = self.store.list_clean_measurements(pond_id=pond_id, limit=100000)
        grouped: dict[str, list[CleanMeasurementRead]] = {}
        for row in rows:
            grouped.setdefault(row.variable_code, []).append(row)
        variables: list[DatasetVariableCoverage] = []
        warnings: list[str] = []
        for variable_code, variable_rows in sorted(grouped.items()):
            ordered = sorted(variable_rows, key=lambda item: item.time)
            outliers = sum(1 for row in ordered if "outlier" in row.quality_flag)
            missing = sum(1 for row in ordered if row.clean_value is None)
            records = len(ordered)
            completeness = 1.0 if records else 0.0
            if records < MIN_TRAINING_RECORDS:
                warnings.append(
                    f"{variable_code} tiene {records} registros; minimo recomendado {MIN_TRAINING_RECORDS}."
                )
            variables.append(
                DatasetVariableCoverage(
                    pond_id=pond_id,
                    variable_code=variable_code,
                    unit=ordered[-1].standard_unit if ordered else None,
                    records=records,
                    first_time=ordered[0].time if ordered else None,
                    last_time=ordered[-1].time if ordered else None,
                    missing_count=missing,
                    outlier_count=outliers,
                    completeness_ratio=completeness,
                    trainable=records >= MIN_TRAINING_RECORDS,
                )
            )
        return DatasetCoverage(
            pond_id=pond_id,
            total_records=len(rows),
            variables=variables,
            trainable_variables=[
                variable.variable_code for variable in variables if variable.trainable
            ],
            warnings=warnings,
        )

    def readiness(self, model_code: str, pond_id: str | None = None) -> DatasetReadiness:
        coverage = self.coverage(pond_id=pond_id)
        records_by_variable = {
            variable.variable_code: variable.records for variable in coverage.variables
        }
        required = TRAINABLE_MODEL_VARIABLES.get(model_code, [])
        available = [
            variable
            for variable in required
            if records_by_variable.get(variable, 0) >= MIN_TRAINING_RECORDS
        ]
        missing = [variable for variable in required if variable not in available]
        can_train = bool(required) and not missing
        status = "dataset_ready" if can_train else "dataset_missing"
        if model_code not in TRAINABLE_MODEL_VARIABLES:
            status = "not_trainable"
        return DatasetReadiness(
            pond_id=pond_id,
            model_code=model_code,
            status=status,
            required_variables=required,
            available_variables=available,
            missing_variables=missing,
            minimum_records_required=MIN_TRAINING_RECORDS,
            records_by_variable=records_by_variable,
            can_train=can_train,
            notes=[] if can_train else ["Faltan variables o registros para entrenamiento real."],
        )

    def run_cleaning(self, request: CleaningRunRequest) -> CleaningRunRead:
        started_at = self._now()
        run_id = self._new_id("CLEANRUN")
        raw_rows = self.store.list_raw_measurements(pond_id=request.pond_id, limit=100000)
        if request.variable_codes:
            raw_rows = [
                row for row in raw_rows if row.variable_code in request.variable_codes
            ]
        variable_codes = request.variable_codes or sorted(
            {row.variable_code for row in raw_rows}
        )
        steps: list[CleaningRunStepRead] = [
            CleaningRunStepRead(
                step_name="load_raw_measurements",
                status="completed",
                details={"records": len(raw_rows), "variables": variable_codes},
            )
        ]
        out_rows: list[CleanMeasurementRead] = []
        interpolated_points = 0
        outliers_detected = 0
        normalized_points = 0

        for variable_code in variable_codes:
            rows = sorted(
                [row for row in raw_rows if row.variable_code == variable_code],
                key=lambda item: item.time,
            )
            if not rows:
                continue
            values: list[float | None] = [
                float(row.raw_value) if row.raw_value is not None else None for row in rows
            ]
            if request.apply_interpolation:
                interpolated_values = linear_interpolate_missing(values)
                interpolated_points += sum(1 for value in values if value is None)
            else:
                interpolated_values = [float(value or 0.0) for value in values]
            flags = ["cleaned" for _ in interpolated_values]
            if request.apply_sigma3 and len(interpolated_values) >= 3:
                sigma_flags = sigma3_flags(interpolated_values)
                outliers_detected += sum(1 for flag in sigma_flags if flag)
                if any(sigma_flags):
                    repaired = [
                        None if is_outlier else value
                        for value, is_outlier in zip(interpolated_values, sigma_flags)
                    ]
                    interpolated_values = linear_interpolate_missing(repaired)
                    flags = [
                        "sigma3_corrected" if is_outlier else flag
                        for flag, is_outlier in zip(flags, sigma_flags)
                    ]
            if request.apply_minmax and interpolated_values:
                minimum = min(interpolated_values)
                maximum = max(interpolated_values)
                if maximum != minimum:
                    interpolated_values = [
                        (value - minimum) / (maximum - minimum)
                        for value in interpolated_values
                    ]
                    flags = ["minmax_normalized" for _ in flags]
                    normalized_points += len(interpolated_values)
            for raw, clean_value, flag in zip(rows, interpolated_values, flags):
                out_rows.append(
                    CleanMeasurementRead(
                        id=f"{run_id}-{raw.id}",
                        raw_measurement_id=raw.id,
                        time=raw.time,
                        farm_id=raw.farm_id,
                        pond_id=raw.pond_id,
                        sensor_id=raw.sensor_id,
                        variable_code=raw.variable_code,
                        clean_value=float(clean_value),
                        standard_unit=raw.raw_unit or "unknown",
                        quality_flag=flag,
                        validation_status="accepted",
                        cleaning_method=self._cleaning_method(request),
                    )
                )

        save_run_measurements = getattr(self.store, "save_cleaning_run_measurements", None)
        if callable(save_run_measurements):
            save_run_measurements(run_id, out_rows)
        if request.overwrite_clean_measurements or not callable(save_run_measurements):
            self.store.save_clean_measurements(
                out_rows,
                overwrite_ids=request.overwrite_clean_measurements,
            )
        steps.extend(
            [
                CleaningRunStepRead(
                    step_name="interpolation",
                    status="completed" if request.apply_interpolation else "skipped",
                    details={"interpolated_points": interpolated_points},
                ),
                CleaningRunStepRead(
                    step_name="sigma3",
                    status="completed" if request.apply_sigma3 else "skipped",
                    details={"outliers_detected": outliers_detected},
                ),
                CleaningRunStepRead(
                    step_name="minmax",
                    status="completed" if request.apply_minmax else "skipped",
                    details={"normalized_points": normalized_points},
                ),
                CleaningRunStepRead(
                    step_name="persist_clean_measurements",
                    status="completed",
                    details={"records_out": len(out_rows)},
                ),
            ]
        )
        run = CleaningRunRead(
            run_id=run_id,
            pond_id=request.pond_id,
            variable_codes=variable_codes,
            status="completed",
            started_at=started_at,
            finished_at=self._now(),
            records_in=len(raw_rows),
            records_out=len(out_rows),
            interpolated_points=interpolated_points,
            outliers_detected=outliers_detected,
            normalized_points=normalized_points,
            steps=steps,
        )
        return self.store.save_cleaning_run(run)

    def cleaning_preview(self, run_id: str) -> dict[str, object]:
        run = self.store.get_cleaning_run(run_id)
        if run is None:
            raise ValueError("cleaning run not found")
        list_run_measurements = getattr(self.store, "list_cleaning_run_measurements", None)
        if callable(list_run_measurements):
            rows = list_run_measurements(run_id, pond_id=run.pond_id, limit=100000)
        else:
            rows = self.store.list_clean_measurements(pond_id=run.pond_id, limit=100000)
            rows = [row for row in rows if row.id.startswith(f"{run_id}-")]
        return {
            "run_id": run_id,
            "records": len(rows),
            "preview_rows": [row.model_dump(mode="json") for row in rows[:25]],
        }

    def build_feature_set(self, request: FeatureBuildRequest) -> FeatureSetRead:
        if request.target_variable in request.feature_variables:
            raise ValueError("target_variable must not be repeated in feature_variables")
        series_by_variable = {
            variable: self._series(request.pond_id, variable, request.cleaning_run_id)
            for variable in [*request.feature_variables, request.target_variable]
        }
        missing = [
            variable for variable, values in series_by_variable.items() if not values
        ]
        if missing:
            raise ValueError(f"variables without clean data: {', '.join(missing)}")
        min_len = min(len(values) for values in series_by_variable.values())
        if min_len < request.window_size + request.horizon:
            raise ValueError("not enough aligned rows for requested window and horizon")

        feature_rows: list[dict[str, object]] = []
        for index in range(0, min_len - request.window_size - request.horizon + 1):
            row: dict[str, object] = {"row_index": index}
            for variable in request.feature_variables:
                values = series_by_variable[variable][index : index + request.window_size]
                if request.window_size == 1:
                    row[variable] = values[-1]
                else:
                    for offset, value in enumerate(values):
                        row[f"{variable}_t_minus_{request.window_size - offset - 1}"] = value
            target_index = index + request.window_size + request.horizon - 1
            row["target"] = series_by_variable[request.target_variable][target_index]
            feature_rows.append(row)

        split = temporal_train_validation_test_split(
            feature_rows,
            train_fraction=request.train_fraction,
            validation_fraction=request.validation_fraction,
        )
        columns: list[FeatureSetColumnRead] = []
        target_values = [float(row["target"]) for row in feature_rows]
        for variable in request.feature_variables:
            values = [
                float(row[variable])
                for row in feature_rows
                if request.window_size == 1 and variable in row
            ]
            pearson = (
                pearson_correlation(values, target_values)
                if len(values) == len(target_values) and values
                else None
            )
            if (
                request.pearson_threshold is not None
                and pearson is not None
                and abs(pearson) < request.pearson_threshold
            ):
                continue
            if request.window_size == 1:
                columns.append(
                    FeatureSetColumnRead(
                        name=variable,
                        role="feature",
                        source_variable=variable,
                        pearson_score=pearson,
                    )
                )
            else:
                for offset in range(request.window_size):
                    columns.append(
                        FeatureSetColumnRead(
                            name=f"{variable}_t_minus_{request.window_size - offset - 1}",
                            role="feature",
                            source_variable=variable,
                            pearson_score=pearson,
                        )
                    )
        columns.append(
            FeatureSetColumnRead(
                name="target",
                role="target",
                source_variable=request.target_variable,
            )
        )
        feature_names = {column.name for column in columns if column.role == "feature"}
        filtered_rows = [
            {
                key: value
                for key, value in row.items()
                if key in feature_names or key in {"target", "row_index"}
            }
            for row in feature_rows
        ]
        feature_set = FeatureSetRead(
            feature_set_id=self._new_id("FEATURESET"),
            pond_id=request.pond_id,
            target_variable=request.target_variable,
            feature_variables=request.feature_variables,
            cleaning_run_id=request.cleaning_run_id,
            window_size=request.window_size,
            horizon=request.horizon,
            rows_count=len(filtered_rows),
            train_rows=len(split["train"]),
            validation_rows=len(split["validation"]),
            test_rows=len(split["test"]),
            columns=columns,
            rows=filtered_rows,
            warnings=[] if filtered_rows else ["Feature set vacio."],
        )
        return self.store.save_feature_set(feature_set)

    def feature_preview(self, feature_set_id: str) -> FeatureSetPreview:
        feature_set = self.store.get_feature_set(feature_set_id)
        if feature_set is None:
            raise ValueError("feature_set_id does not exist")
        return FeatureSetPreview(
            feature_set_id=feature_set_id,
            rows_count=feature_set.rows_count,
            preview_rows=feature_set.rows[:25],
            columns=feature_set.columns,
        )

    def train(self, request: TrainingJobRequest) -> TrainingJobRead:
        job_id = self._new_id("TRAINJOB")
        job = TrainingJobRead(
            job_id=job_id,
            model_code=request.model_code,
            feature_set_id=request.feature_set_id,
            status="queued",
            hyperparameters=request.hyperparameters,
        )
        self.store.save_training_job(job)
        self._event(job_id, "queued", "Training job created.")
        started = self._now()
        try:
            job = job.model_copy(update={"status": "running", "started_at": started})
            self.store.save_training_job(job)
            self._event(job_id, "running", "Training pipeline started.")
            feature_set = self.store.get_feature_set(request.feature_set_id)
            if feature_set is None:
                raise ValueError("feature_set_id does not exist")
            artifact_payload, metrics = self._train_artifact(
                request.model_code,
                feature_set,
                request.hyperparameters,
            )
            version = self._next_asset_version(request.model_code)
            asset = ModelAssetRead(
                asset_id=self._new_id("ASSET"),
                model_code=request.model_code,
                version=version,
                artifact_path=f"model_assets/{request.model_code}/{version}.json",
                artifact_format="json",
                artifact_payload=artifact_payload,
                feature_set_id=request.feature_set_id,
                training_job_id=job_id,
                metrics_json=metrics,
                status="candidate",
            )
            self.store.save_model_asset(asset)
            if request.auto_activate:
                asset = self.store.activate_model_asset(asset.asset_id)
            job = job.model_copy(
                update={
                    "status": "completed",
                    "finished_at": self._now(),
                    "metrics": metrics,
                    "asset_id": asset.asset_id,
                }
            )
            self.store.save_training_job(job)
            self._event(
                job_id,
                "completed",
                "Training completed and model asset registered.",
                {"asset_id": asset.asset_id, "metrics": metrics},
            )
            return job
        except Exception as exc:
            failed = job.model_copy(
                update={
                    "status": "failed",
                    "finished_at": self._now(),
                    "error_message": str(exc),
                }
            )
            self.store.save_training_job(failed)
            self._event(job_id, "failed", str(exc))
            return failed

    def list_trainable_models(self) -> list[TrainableModelRead]:
        models: list[TrainableModelRead] = []
        for model_code, required in sorted(TRAINABLE_MODEL_VARIABLES.items()):
            active_asset = self.store.active_model_asset(model_code)
            models.append(
                TrainableModelRead(
                    model_code=model_code,
                    name=model_code.replace("_", " ").title(),
                    family=self._model_family(model_code),
                    lifecycle_status="active" if active_asset else "training_available",
                    required_variables=required,
                    active_asset_id=active_asset.asset_id if active_asset else None,
                    latest_metrics=active_asset.metrics_json if active_asset else {},
                    notes=[] if active_asset else ["Sin artefacto activo."],
                )
            )
        return models

    def model_lifecycle_detail(
        self,
        model_code: str,
        pond_id: str | None = None,
    ) -> ModelLifecycleDetailRead:
        readiness = self.readiness(model_code=model_code, pond_id=pond_id)
        active_asset = self.store.active_model_asset(model_code)
        jobs = [
            job
            for job in self.store.list_training_jobs()
            if job.model_code == model_code
        ]
        latest_job = jobs[0] if jobs else None
        feature_set_id = (
            active_asset.feature_set_id
            if active_asset
            else latest_job.feature_set_id
            if latest_job
            else None
        )
        feature_set = self.store.get_feature_set(feature_set_id) if feature_set_id else None
        summarized_feature_set = (
            self._summarize_feature_set(feature_set) if feature_set else None
        )
        predictions = self._list_prediction_history(
            model_code=model_code,
            asset_id=active_asset.asset_id if active_asset else None,
            limit=10,
        )
        metrics = active_asset.metrics_json if active_asset else latest_job.metrics if latest_job else {}
        return ModelLifecycleDetailRead(
            model_code=model_code,
            pond_id=pond_id,
            readiness=readiness,
            active_asset=active_asset,
            latest_training_job=latest_job,
            feature_set=summarized_feature_set,
            recent_predictions=predictions,
            steps=self._lifecycle_steps(
                readiness=readiness,
                feature_set=summarized_feature_set,
                job=latest_job,
                asset=active_asset,
                metrics=metrics,
                predictions=predictions,
            ),
            recommendation=self._model_recommendation(metrics, active_asset),
        )

    def model_asset_lineage(self, asset_id: str) -> dict[str, object]:
        asset = self.store.get_model_asset(asset_id)
        if asset is None:
            raise ValueError("model asset not found")
        job = self.store.get_training_job(asset.training_job_id)
        feature_set = self.store.get_feature_set(asset.feature_set_id)
        events = self.store.list_training_job_events(asset.training_job_id)
        predictions = self._list_prediction_history(asset_id=asset_id, limit=25)
        cleaning_run = (
            self.store.get_cleaning_run(feature_set.cleaning_run_id)
            if feature_set and feature_set.cleaning_run_id
            else None
        )
        return {
            "asset": asset.model_dump(mode="json"),
            "training_job": job.model_dump(mode="json") if job else None,
            "training_events": [event.model_dump(mode="json") for event in events],
            "feature_set": (
                self._summarize_feature_set(feature_set).model_dump(mode="json")
                if feature_set
                else None
            ),
            "cleaning_run": cleaning_run.model_dump(mode="json") if cleaning_run else None,
            "recent_predictions": [
                prediction.model_dump(mode="json") for prediction in predictions
            ],
        }

    def prediction_history(
        self,
        model_code: str | None = None,
        asset_id: str | None = None,
        limit: int = 25,
    ) -> list[ModelAssetPredictionHistoryRead]:
        return self._list_prediction_history(
            model_code=model_code,
            asset_id=asset_id,
            limit=limit,
        )

    def lifecycle_status(self) -> MLLifecycleStatus:
        assets = self.store.list_model_assets()
        return MLLifecycleStatus(
            datasets_enabled=True,
            cleaning_enabled=True,
            features_enabled=True,
            training_enabled=True,
            model_assets_enabled=True,
            total_feature_sets=len(self.store.list_feature_sets()),
            total_training_jobs=len(self.store.list_training_jobs()),
            total_model_assets=len(assets),
            active_model_assets=len([asset for asset in assets if asset.status == "active"]),
            routes={
                "datasets": "/datasets/coverage",
                "cleaning": "/data/cleaning-runs",
                "features": "/features/build",
                "training": "/ml/training-jobs",
                "assets": "/ml/model-assets",
                "model_lifecycle": "/ml/models/{model_code}/lifecycle",
                "asset_lineage": "/ml/model-assets/{asset_id}/lineage",
                "predictions": "/ml/predictions",
            },
        )

    def predict_with_asset(
        self,
        asset: ModelAssetRead,
        features: dict[str, float],
    ) -> ModelAssetPredictionRead:
        payload = asset.artifact_payload
        algorithm = str(payload.get("algorithm", ""))
        feature_names = [str(name) for name in payload.get("feature_names", [])]
        missing = [name for name in feature_names if name not in features]
        if missing:
            raise ValueError(f"missing features: {', '.join(missing)}")
        row = [float(features[name]) for name in feature_names]
        if algorithm == "sklearn_pickle":
            estimator = pickle.loads(base64.b64decode(str(payload["estimator_b64"])))
            task = str(payload.get("task", "regression"))
            if task == "projection":
                transformed = estimator.transform([row])[0]
                prediction = float(transformed[0])
            else:
                raw_prediction = estimator.predict([row])[0]
            if task == "classification":
                prediction = int(raw_prediction)
            elif task == "cluster":
                prediction = int(raw_prediction)
            elif task != "projection":
                prediction = float(raw_prediction)
        elif algorithm == "linear_regression_baseline":
            prediction: float | int | str = linear_regression_predict(
                row,
                payload.get("coefficients", []),
                float(payload.get("intercept", 0.0)),
            )
        elif algorithm == "kmeans":
            centroids = payload.get("centroids", [])
            if not isinstance(centroids, list) or not centroids:
                raise ValueError("kmeans artifact has no centroids")
            distances = [
                sum(
                    (float(value) - float(center[index])) ** 2
                    for index, value in enumerate(row)
                )
                ** 0.5
                for center in centroids
            ]
            prediction = min(range(len(distances)), key=lambda index: distances[index])
        else:
            raise ValueError(f"unsupported artifact algorithm: {algorithm}")
        prediction_id = None
        save_prediction = getattr(self.store, "save_model_asset_prediction", None)
        if callable(save_prediction):
            prediction_id = save_prediction(
                asset=asset,
                features=features,
                prediction=prediction,
            )
        return ModelAssetPredictionRead(
            model_code=asset.model_code,
            asset_id=asset.asset_id,
            version=asset.version,
            prediction=prediction,
            feature_names=feature_names,
            traceability={
                "artifact_path": asset.artifact_path,
                "feature_set_id": asset.feature_set_id,
                "training_job_id": asset.training_job_id,
                "artifact_status": asset.status,
                "prediction_id": prediction_id,
            },
        )

    def _train_artifact(
        self,
        model_code: str,
        feature_set: FeatureSetRead,
        hyperparameters: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, float]]:
        feature_names = [
            column.name for column in feature_set.columns if column.role == "feature"
        ]
        if not feature_names:
            raise ValueError("feature set has no feature columns")
        rows = feature_set.rows
        if len(rows) < MIN_TRAINING_RECORDS:
            raise ValueError(
                f"feature set requires at least {MIN_TRAINING_RECORDS} rows"
            )
        x = [[float(row[name]) for name in feature_names] for row in rows]
        y = [float(row["target"]) for row in rows]
        train_count = max(1, feature_set.train_rows)
        train_x = x[:train_count]
        train_y = y[:train_count]
        eval_x = x[train_count:] or x
        eval_y = y[train_count:] or y
        sklearn_artifact = self._train_sklearn_artifact(
            model_code,
            feature_names,
            train_x,
            train_y,
            eval_x,
            eval_y,
            feature_set.target_variable,
            hyperparameters,
        )
        if sklearn_artifact is not None:
            return sklearn_artifact
        if "KMEANS" in model_code:
            k = int(hyperparameters.get("k", 3))
            initial_centroids = train_x[:k] if len(train_x) >= k else train_x
            kmeans = kmeans_fit(train_x, initial_centroids, iterations=10)
            return (
                {
                    "algorithm": "kmeans",
                    "feature_names": feature_names,
                    **kmeans,
                },
                {"objective": float(kmeans["objective"])},
            )
        fitted = linear_regression_fit_gradient_descent(
            train_x,
            train_y,
            learning_rate=float(hyperparameters.get("learning_rate", 0.0001)),
            epochs=int(hyperparameters.get("epochs", 400)),
        )
        predictions = [
            linear_regression_predict(
                row,
                fitted["coefficients"],
                float(fitted["intercept"]),
            )
            for row in eval_x
        ]
        metrics = regression_metrics(eval_y, predictions)
        return (
            {
                "algorithm": "linear_regression_baseline",
                "model_code": model_code,
                "feature_names": feature_names,
                "target_variable": feature_set.target_variable,
                "coefficients": fitted["coefficients"],
                "intercept": fitted["intercept"],
            },
            {key: float(value) for key, value in metrics.items()},
        )

    def _list_prediction_history(
        self,
        model_code: str | None = None,
        asset_id: str | None = None,
        limit: int = 25,
    ) -> list[ModelAssetPredictionHistoryRead]:
        list_predictions = getattr(self.store, "list_model_asset_predictions", None)
        if callable(list_predictions):
            return list_predictions(model_code=model_code, asset_id=asset_id, limit=limit)
        return []

    @staticmethod
    def _summarize_feature_set(feature_set: FeatureSetRead) -> FeatureSetRead:
        return feature_set.model_copy(update={"rows": []})

    @staticmethod
    def _lifecycle_steps(
        *,
        readiness: DatasetReadiness,
        feature_set: FeatureSetRead | None,
        job: TrainingJobRead | None,
        asset: ModelAssetRead | None,
        metrics: dict[str, float],
        predictions: list[ModelAssetPredictionHistoryRead],
    ) -> list[dict[str, object]]:
        r2 = metrics.get("r2")
        if not metrics:
            validation_status = "pending"
        elif r2 is not None and r2 < 0:
            validation_status = "warning"
        else:
            validation_status = "ready"
        return [
            {
                "step": "data",
                "status": "ready" if readiness.can_train else "warning",
                "detail": "dataset_ready" if readiness.can_train else "dataset_missing",
                "missing_variables": readiness.missing_variables,
            },
            {
                "step": "cleaning",
                "status": "ready",
                "detail": "cleaning_run_measurements versionadas disponibles",
            },
            {
                "step": "features",
                "status": "ready" if feature_set else "pending",
                "detail": feature_set.feature_set_id if feature_set else "feature_set pendiente",
            },
            {
                "step": "training",
                "status": job.status if job else "pending",
                "detail": job.job_id if job else "training_job pendiente",
            },
            {
                "step": "validation",
                "status": validation_status,
                "detail": metrics,
            },
            {
                "step": "artifact",
                "status": asset.status if asset else "pending",
                "detail": asset.asset_id if asset else "asset pendiente",
            },
            {
                "step": "inference",
                "status": "ready" if predictions else "pending",
                "detail": {"recent_predictions": len(predictions)},
            },
        ]

    @staticmethod
    def _model_recommendation(
        metrics: dict[str, float],
        asset: ModelAssetRead | None,
    ) -> str:
        if asset is None:
            return "Entrenar candidato antes de usar en produccion."
        r2 = metrics.get("r2")
        if r2 is not None and r2 < 0:
            return "Modelo experimental: no promover sin nuevo entrenamiento o revision de datos."
        if not metrics:
            return "Artefacto activo sin metricas suficientes; validar antes de decision operativa."
        return "Modelo disponible para inferencia asistida con trazabilidad."

    def _train_sklearn_artifact(
        self,
        model_code: str,
        feature_names: list[str],
        train_x: list[list[float]],
        train_y: list[float],
        eval_x: list[list[float]],
        eval_y: list[float],
        target_variable: str,
        hyperparameters: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, float]] | None:
        try:
            from sklearn.cluster import KMeans
            from sklearn.decomposition import PCA
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.linear_model import LinearRegression, LogisticRegression
            from sklearn.metrics import accuracy_score
            from sklearn.neighbors import KNeighborsRegressor
            from sklearn.neural_network import MLPRegressor
            from sklearn.svm import SVR
            from sklearn.tree import DecisionTreeRegressor
        except Exception:
            return None

        task = "regression"
        estimator_name = model_code
        if model_code == "ML_SUPERVISED_LINEAR_REG":
            estimator = LinearRegression()
        elif model_code == "ML_SUPERVISED_LOGISTIC_REG":
            threshold = sorted(train_y)[len(train_y) // 2]
            y_class = [int(value >= threshold) for value in train_y]
            estimator = LogisticRegression(max_iter=int(hyperparameters.get("max_iter", 500)))
            estimator.fit(train_x, y_class)
            eval_class = [int(value >= threshold) for value in eval_y]
            predictions = [int(value) for value in estimator.predict(eval_x)]
            return self._sklearn_payload(
                model_code=model_code,
                estimator=estimator,
                estimator_name="LogisticRegression",
                feature_names=feature_names,
                target_variable=target_variable,
                task="classification",
                metrics={"accuracy": float(accuracy_score(eval_class, predictions))},
                extra={"classification_threshold": float(threshold)},
            )
        elif model_code == "ML_NONLINEAR_DECISION_TREE":
            estimator = DecisionTreeRegressor(
                max_depth=int(hyperparameters.get("max_depth", 6)),
                random_state=42,
            )
        elif model_code == "ML_NONLINEAR_RANDOM_FOREST":
            estimator = RandomForestRegressor(
                n_estimators=int(hyperparameters.get("n_estimators", 80)),
                max_depth=int(hyperparameters.get("max_depth", 8)),
                random_state=42,
                n_jobs=1,
            )
        elif model_code == "ML_NONLINEAR_SVM":
            estimator = SVR(
                C=float(hyperparameters.get("c", 1.0)),
                epsilon=float(hyperparameters.get("epsilon", 0.01)),
            )
        elif model_code == "ML_NONSUPERVISED_KNN":
            estimator = KNeighborsRegressor(
                n_neighbors=int(hyperparameters.get("k", 5)),
            )
        elif model_code == "ML_UNSUPERVISED_KMEANS":
            task = "cluster"
            estimator = KMeans(
                n_clusters=int(hyperparameters.get("k", 3)),
                n_init=10,
                random_state=42,
            )
            estimator.fit(train_x)
            return self._sklearn_payload(
                model_code=model_code,
                estimator=estimator,
                estimator_name="KMeans",
                feature_names=feature_names,
                target_variable=target_variable,
                task=task,
                metrics={"inertia": float(estimator.inertia_)},
            )
        elif model_code == "ML_UNSUPERVISED_PCA":
            task = "projection"
            estimator = PCA(n_components=min(2, len(feature_names)))
            estimator.fit(train_x)
            variance = [float(value) for value in estimator.explained_variance_ratio_]
            return self._sklearn_payload(
                model_code=model_code,
                estimator=estimator,
                estimator_name="PCA",
                feature_names=feature_names,
                target_variable=target_variable,
                task=task,
                metrics={
                    "explained_variance_ratio_0": variance[0],
                    "explained_variance_ratio_total": float(sum(variance)),
                },
            )
        elif "LSTM" in model_code or "BPNN" in model_code:
            estimator = MLPRegressor(
                hidden_layer_sizes=tuple(
                    int(value)
                    for value in hyperparameters.get("hidden_layer_sizes", [32, 16])
                ),
                max_iter=int(hyperparameters.get("max_iter", 500)),
                random_state=42,
            )
            estimator_name = "MLPRegressor"
        else:
            return None

        estimator.fit(train_x, train_y)
        predictions = [float(value) for value in estimator.predict(eval_x)]
        metrics = regression_metrics(eval_y, predictions)
        return self._sklearn_payload(
            model_code=model_code,
            estimator=estimator,
            estimator_name=estimator_name,
            feature_names=feature_names,
            target_variable=target_variable,
            task=task,
            metrics={key: float(value) for key, value in metrics.items()},
        )

    @staticmethod
    def _sklearn_payload(
        *,
        model_code: str,
        estimator: object,
        estimator_name: str,
        feature_names: list[str],
        target_variable: str,
        task: str,
        metrics: dict[str, float],
        extra: dict[str, object] | None = None,
    ) -> tuple[dict[str, object], dict[str, float]]:
        payload = {
            "algorithm": "sklearn_pickle",
            "model_code": model_code,
            "estimator_name": estimator_name,
            "feature_names": feature_names,
            "target_variable": target_variable,
            "task": task,
            "estimator_b64": base64.b64encode(pickle.dumps(estimator)).decode("ascii"),
        }
        if extra:
            payload.update(extra)
        return payload, metrics

    def _series(
        self,
        pond_id: str,
        variable_code: str,
        cleaning_run_id: str | None = None,
    ) -> list[float]:
        rows = []
        if cleaning_run_id is not None:
            list_run_measurements = getattr(self.store, "list_cleaning_run_measurements", None)
            if callable(list_run_measurements):
                rows = list_run_measurements(
                    cleaning_run_id,
                    pond_id=pond_id,
                    variable_code=variable_code,
                    limit=100000,
                )
        if not rows:
            rows = self.store.list_clean_measurements(
                pond_id=pond_id,
                variable_code=variable_code,
                limit=100000,
            )
        return [float(row.clean_value) for row in sorted(rows, key=lambda item: item.time)]

    def _event(
        self,
        job_id: str,
        event_type: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> TrainingJobEventRead:
        event = TrainingJobEventRead(
            event_id=self._new_id("TRAINEVENT"),
            job_id=job_id,
            event_type=event_type,
            message=message,
            payload=payload or {},
        )
        return self.store.append_training_job_event(event)

    def _next_asset_version(self, model_code: str) -> str:
        count = len(self.store.list_model_assets(model_code=model_code)) + 1
        return f"v{count}"

    @staticmethod
    def _cleaning_method(request: CleaningRunRequest) -> str:
        methods = []
        if request.apply_interpolation:
            methods.append("linear_interpolation")
        if request.apply_sigma3:
            methods.append("sigma3")
        if request.apply_minmax:
            methods.append("minmax")
        return "+".join(methods) or "none"

    @staticmethod
    def _model_family(model_code: str) -> str:
        if "LSTM" in model_code or "BPNN" in model_code:
            return "ml_sequence"
        if "KMEANS" in model_code or "PCA" in model_code or "SOM" in model_code:
            return "ml_unsupervised"
        return "ml_tabular"

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4()}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
