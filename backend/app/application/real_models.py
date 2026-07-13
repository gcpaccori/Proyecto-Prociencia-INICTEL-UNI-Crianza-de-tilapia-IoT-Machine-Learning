from __future__ import annotations

import base64
import math
import pickle
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.app.domains.measurements import CleanMeasurementRead
from backend.app.domains.ml_lifecycle import (
    CleaningRunRead,
    CleaningRunStepRead,
    FeatureSetColumnRead,
    FeatureSetRead,
    ModelAssetRead,
    TrainingJobEventRead,
    TrainingJobRead,
)
from backend.app.models_engine.deterministic.dissolved_oxygen import (
    do_saturation,
    oxygen_status,
    update_do_0d,
)
from backend.app.models_engine.deterministic.growth import tilapia_growth_temperature
from backend.app.models_engine.deterministic.water_quality import (
    biofloc_water_quality_readiness,
    water_quality_index,
)
from backend.app.models_engine.ml.preprocessing import (
    align_sensor_series,
    build_latest_svm_od_features,
    build_svm_od_feature_rows,
    hampel_flags,
    interpolate_short_internal_gaps,
    regression_metrics,
)
from backend.app.models_engine.ml.ica_classifier import (
    ICA_CLASS_ORDER,
    ICA_FEATURE_NAMES,
    build_ica_training_rows,
)


SVM_MODEL_CODE = "SVM_OD_FORECAST_1H"
OXYGEN_MODEL_CODE = "OXYGEN_STATUS_MODEL"
GROWTH_MODEL_CODE = "TILAPIA_GROWTH_TEMPERATURE"
WATER_QUALITY_ICA_MODEL_CODE = "WATER_QUALITY_INDEX_ICA"
WATER_QUALITY_ICA_SVM_MODEL_CODE = "WATER_QUALITY_INDEX_ICA_SVM"
BIOFLOC_WATER_QUALITY_MODEL_CODE = "BIOFLOC_WATER_QUALITY"
REQUIRED_VARIABLES = [
    "water_temperature_c",
    "ph",
    "dissolved_oxygen_mg_l",
    "nitrate_ion",
]
MIN_VALID_WINDOWS = 500
DYNAMIC_OXYGEN_INPUTS = [
    "flow_rate_l_h",
    "raceway_volume_l",
    "do_influent_mg_l",
    "oxygen_supply_rate_mg_l_h",
    "fish_biomass_kg",
    "fish_respiration_rate_mg_h_kg",
    "reaeration_rate_h_1",
]


class RealModelsService:
    def __init__(self, store: object) -> None:
        self.store = store

    def train_svm_od(self, pond_id: str) -> dict[str, object]:
        self._require_persistent_store()
        prepared = self._prepare_dataset(pond_id, persist_cleaning=True, limit=100000)
        feature_rows = prepared["feature_rows"]
        feature_names = prepared["feature_names"]
        horizon_steps = prepared["horizon_steps"]
        if len(feature_rows) < MIN_VALID_WINDOWS:
            raise ValueError(
                f"se requieren al menos {MIN_VALID_WINDOWS} ventanas validas; "
                f"solo hay {len(feature_rows)}"
            )

        nitrate_metadata = self.store.get_variable_metadata("nitrate_ion")
        nitrate_verified = bool(
            nitrate_metadata
            and nitrate_metadata.get("standard_unit") == "mg/L"
            and nitrate_metadata.get("verified_at")
        )
        if not nitrate_verified:
            raise ValueError("la unidad de nitrate_ion no esta verificada")

        feature_set = self._save_feature_set(
            pond_id=pond_id,
            cleaning_run_id=prepared["cleaning_run"].run_id,
            feature_rows=feature_rows,
            feature_names=feature_names,
            horizon_steps=horizon_steps,
        )
        job = TrainingJobRead(
            job_id=self._new_id("TRAINJOB"),
            model_code=SVM_MODEL_CODE,
            feature_set_id=feature_set.feature_set_id,
            status="queued",
            hyperparameters={
                "search": "GridSearchCV",
                "cross_validation": "TimeSeriesSplit(n_splits=5, gap=horizon_steps)",
            },
        )
        self.store.save_training_job(job)
        self._event(job.job_id, "queued", "Entrenamiento SVM registrado.")

        try:
            from sklearn.base import clone
            from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.svm import SVR

            running = job.model_copy(update={"status": "running", "started_at": self._now()})
            self.store.save_training_job(running)
            self._event(
                job.job_id,
                "running",
                "Buscando hiperparametros con validacion temporal.",
                {"valid_windows": len(feature_rows), "horizon_steps": horizon_steps},
            )

            x = [[float(row[name]) for name in feature_names] for row in feature_rows]
            y = [float(row["target"]) for row in feature_rows]
            train_end = int(len(x) * 0.70)
            validation_end = train_end + int(len(x) * 0.15)
            train_x, train_y = x[:train_end], y[:train_end]
            validation_x, validation_y = x[train_end:validation_end], y[train_end:validation_end]
            test_x, test_y = x[validation_end:], y[validation_end:]

            pipeline = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("svr", SVR(kernel="rbf", cache_size=512)),
                ]
            )
            parameter_grid = {
                "svr__C": [1, 10, 50, 100],
                "svr__gamma": ["scale", 0.001, 0.01, 0.1],
                "svr__epsilon": [0.01, 0.05, 0.1, 0.2],
            }
            cross_validation = TimeSeriesSplit(n_splits=5, gap=horizon_steps)
            search = GridSearchCV(
                pipeline,
                parameter_grid,
                scoring="neg_mean_absolute_error",
                cv=cross_validation,
                n_jobs=-1,
                refit=True,
                error_score="raise",
            )
            search.fit(train_x, train_y)
            validation_predictions = [float(value) for value in search.predict(validation_x)]
            validation_metrics = regression_metrics(validation_y, validation_predictions)

            estimator = clone(search.best_estimator_)
            estimator.fit(train_x + validation_x, train_y + validation_y)
            test_predictions = [float(value) for value in estimator.predict(test_x)]
            test_metrics = regression_metrics(test_y, test_predictions)
            persistence_predictions = [
                float(row[feature_names.index("dissolved_oxygen_mg_l")]) for row in test_x
            ]
            baseline_metrics = regression_metrics(test_y, persistence_predictions)
            metrics = {
                "mae": test_metrics["mae"],
                "rmse": test_metrics["rmse"],
                "r2": test_metrics["r2"],
                "validation_mae": validation_metrics["mae"],
                "validation_rmse": validation_metrics["rmse"],
                "validation_r2": validation_metrics["r2"],
                "persistence_mae": baseline_metrics["mae"],
                "persistence_rmse": baseline_metrics["rmse"],
                "persistence_r2": baseline_metrics["r2"],
                "cv_best_mae": -float(search.best_score_),
            }
            activation_criteria = {
                "minimum_500_windows": len(feature_rows) >= MIN_VALID_WINDOWS,
                "nitrate_unit_verified": nitrate_verified,
                "beats_persistence_mae": metrics["mae"] < metrics["persistence_mae"],
                "positive_test_r2": metrics["r2"] > 0,
                "artifact_and_metrics_stored": True,
            }
            can_activate = all(activation_criteria.values())
            version = self._next_version()
            asset = ModelAssetRead(
                asset_id=self._new_id("ASSET"),
                model_code=SVM_MODEL_CODE,
                version=version,
                artifact_path=f"model_assets/{SVM_MODEL_CODE}/{version}.pkl",
                artifact_format="pickle_base64",
                artifact_payload={
                    "algorithm": "Pipeline(StandardScaler, SVR-rbf)",
                    "model_code": SVM_MODEL_CODE,
                    "feature_names": feature_names,
                    "target_variable": "dissolved_oxygen_mg_l",
                    "estimator_b64": base64.b64encode(pickle.dumps(estimator)).decode("ascii"),
                    "best_params": search.best_params_,
                    "sampling_minutes": prepared["sampling_minutes"],
                    "horizon_steps": horizon_steps,
                    "valid_windows": len(feature_rows),
                    "input_window_start": feature_rows[0]["issued_at"].isoformat(),
                    "input_window_end": feature_rows[-1]["issued_at"].isoformat(),
                    "activation_criteria": activation_criteria,
                    "nitrate_unit": nitrate_metadata.get("standard_unit"),
                },
                feature_set_id=feature_set.feature_set_id,
                training_job_id=job.job_id,
                metrics_json=metrics,
                status="candidate",
            )
            self.store.save_model_asset(asset)
            if can_activate:
                asset = self.store.activate_model_asset(asset.asset_id)

            completed = running.model_copy(
                update={
                    "status": "completed",
                    "finished_at": self._now(),
                    "metrics": metrics,
                    "asset_id": asset.asset_id,
                    "hyperparameters": search.best_params_,
                }
            )
            self.store.save_training_job(completed)
            self._event(
                job.job_id,
                "completed",
                "SVM entrenado y evaluado contra persistencia.",
                {
                    "asset_id": asset.asset_id,
                    "asset_status": asset.status,
                    "activation_criteria": activation_criteria,
                },
            )
            return {
                "status": "completed",
                "model_code": SVM_MODEL_CODE,
                "pond_id": pond_id,
                "job": completed.model_dump(mode="json"),
                "asset": self._public_asset(asset),
                "activation_criteria": activation_criteria,
                "data_quality": prepared["quality"],
            }
        except Exception as exc:
            failed = job.model_copy(
                update={
                    "status": "failed",
                    "finished_at": self._now(),
                    "error_message": str(exc),
                }
            )
            self.store.save_training_job(failed)
            self._event(job.job_id, "failed", str(exc))
            raise

    def forecast_svm_od(
        self,
        pond_id: str,
        prepared: dict[str, object] | None = None,
        allow_candidate: bool = False,
    ) -> dict[str, object]:
        self._require_persistent_store()
        asset = self.store.active_model_asset(SVM_MODEL_CODE)
        productive = asset is not None
        if asset is None:
            candidates = self.store.list_model_assets(model_code=SVM_MODEL_CODE)
            if allow_candidate and candidates:
                asset = candidates[0]
            else:
                return {
                    "status": "not_ready",
                    "model_code": SVM_MODEL_CODE,
                    "pond_id": pond_id,
                    "reason": "no_active_asset",
                    "latest_candidate": self._public_asset(candidates[0]) if candidates else None,
                }
        prepared = prepared or self._prepare_dataset(
            pond_id,
            persist_cleaning=False,
            limit=4000,
        )
        latest = build_latest_svm_od_features(prepared["aligned"], REQUIRED_VARIABLES)
        feature_names = list(asset.artifact_payload["feature_names"])
        estimator = pickle.loads(base64.b64decode(asset.artifact_payload["estimator_b64"]))
        prediction = float(estimator.predict([[float(latest[name]) for name in feature_names]])[0])
        issued_at = latest["issued_at"]
        target_time = issued_at + timedelta(hours=1)
        forecast_id = self._new_id("FORECAST")
        response = {
            "status": "ready" if productive else "candidate_test",
            "model_code": SVM_MODEL_CODE,
            "pond_id": pond_id,
            "issued_at": issued_at.isoformat(),
            "target_time": target_time.isoformat(),
            "current_do_mg_l": float(latest["dissolved_oxygen_mg_l"]),
            "forecast_do_mg_l": prediction,
            "change_mg_l": prediction - float(latest["dissolved_oxygen_mg_l"]),
            "asset_id": asset.asset_id,
            "asset_version": asset.version,
            "metrics": asset.metrics_json,
            "data_quality": {
                "observed_points": prepared["quality"]["aligned_points"],
                "interpolated_ratio": latest["interpolated_ratio"],
            },
            "traceability": {
                "forecast_id": forecast_id,
                "feature_set_id": asset.feature_set_id,
                "training_job_id": asset.training_job_id,
                "input_window_start": latest["input_window_start"].isoformat(),
                "input_window_end": latest["input_window_end"].isoformat(),
                "timestamp_field": "parametro_aguas.created_at",
                "generated_data_used": False,
                "productive_use": productive,
            },
        }
        if productive:
            self.store.save_model_forecast(
                {
                    "forecast_id": forecast_id,
                    "pond_id": pond_id,
                    "model_code": SVM_MODEL_CODE,
                    "asset_id": asset.asset_id,
                    "issued_at": issued_at,
                    "target_time": target_time,
                    "input_window_start": latest["input_window_start"],
                    "input_window_end": latest["input_window_end"],
                    "predicted_variable": "dissolved_oxygen_mg_l",
                    "predicted_value": prediction,
                    "unit": "mg/L",
                    "observed_value": None,
                    "absolute_error": None,
                    "quality_json": response["data_quality"],
                    "payload_json": response,
                    "created_at": self._now(),
                }
            )
        return response

    def train_ica_svm(self, pond_id: str) -> dict[str, object]:
        """Train an SVC that estimates the documented ICA classification.

        The training target is the deterministic ICA class, not an independent
        field inspection. This keeps the artifact useful for comparison while
        preserving the documented formula as the source of truth.
        """
        self._require_persistent_store()
        prepared = self._prepare_dataset(pond_id, persist_cleaning=True, limit=100000)
        feature_rows = build_ica_training_rows(prepared["aligned"])
        if len(feature_rows) < MIN_VALID_WINDOWS:
            raise ValueError(
                f"se requieren al menos {MIN_VALID_WINDOWS} lecturas ICA validas; "
                f"solo hay {len(feature_rows)}"
            )
        feature_set = self._save_feature_set(
            pond_id=pond_id,
            cleaning_run_id=prepared["cleaning_run"].run_id,
            feature_rows=feature_rows,
            feature_names=ICA_FEATURE_NAMES,
            horizon_steps=0,
            target_variable="ica_formula_class",
            target_unit=None,
            feature_variables=ICA_FEATURE_NAMES,
            window_size=1,
        )
        job = TrainingJobRead(
            job_id=self._new_id("TRAINJOB"),
            model_code=WATER_QUALITY_ICA_SVM_MODEL_CODE,
            feature_set_id=feature_set.feature_set_id,
            status="queued",
            hyperparameters={
                "search": "GridSearchCV",
                "cross_validation": "TimeSeriesSplit(n_splits=5)",
                "target": "ica_formula_class",
            },
        )
        self.store.save_training_job(job)
        self._event(job.job_id, "queued", "Entrenamiento SVM ICA registrado.")
        try:
            from sklearn.base import clone
            from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
            from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.svm import SVC

            running = job.model_copy(update={"status": "running", "started_at": self._now()})
            self.store.save_training_job(running)
            x = [[float(row[name]) for name in ICA_FEATURE_NAMES] for row in feature_rows]
            y = [int(row["target"]) for row in feature_rows]
            train_end = int(len(x) * 0.70)
            validation_end = train_end + int(len(x) * 0.15)
            train_x, train_y = x[:train_end], y[:train_end]
            validation_x, validation_y = x[train_end:validation_end], y[train_end:validation_end]
            test_x, test_y = x[validation_end:], y[validation_end:]
            if len(set(train_y)) < 2:
                raise ValueError("las etiquetas ICA historicas no contienen al menos dos clases")

            pipeline = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("svc", SVC(kernel="rbf", class_weight="balanced")),
                ]
            )
            search = GridSearchCV(
                pipeline,
                {"svc__C": [1, 10, 50], "svc__gamma": ["scale", 0.01]},
                scoring="f1_weighted",
                cv=TimeSeriesSplit(n_splits=5),
                n_jobs=-1,
                refit=True,
                error_score="raise",
            )
            search.fit(train_x, train_y)
            validation_predictions = [int(value) for value in search.predict(validation_x)]
            estimator = clone(search.best_estimator_)
            estimator.fit(train_x + validation_x, train_y + validation_y)
            test_predictions = [int(value) for value in estimator.predict(test_x)]
            metrics = {
                "accuracy": float(accuracy_score(test_y, test_predictions)),
                "f1_weighted": float(f1_score(test_y, test_predictions, average="weighted", zero_division=0)),
                "validation_accuracy": float(accuracy_score(validation_y, validation_predictions)),
                "validation_f1_weighted": float(f1_score(validation_y, validation_predictions, average="weighted", zero_division=0)),
                "cv_best_f1_weighted": float(search.best_score_),
            }
            activation_criteria = {
                "minimum_500_rows": len(feature_rows) >= MIN_VALID_WINDOWS,
                "two_or_more_classes": len(set(y)) >= 2,
                "test_f1_at_least_0_80": metrics["f1_weighted"] >= 0.80,
                "artifact_and_metrics_stored": True,
            }
            version = self._next_version(WATER_QUALITY_ICA_SVM_MODEL_CODE)
            asset = ModelAssetRead(
                asset_id=self._new_id("ASSET"),
                model_code=WATER_QUALITY_ICA_SVM_MODEL_CODE,
                version=version,
                artifact_path=f"model_assets/{WATER_QUALITY_ICA_SVM_MODEL_CODE}/{version}.pkl",
                artifact_format="pickle_base64",
                artifact_payload={
                    "algorithm": "Pipeline(StandardScaler, SVC-rbf)",
                    "model_code": WATER_QUALITY_ICA_SVM_MODEL_CODE,
                    "feature_names": ICA_FEATURE_NAMES,
                    "target_variable": "ica_formula_class",
                    "target_origin": "WATER_QUALITY_INDEX_ICA formula labels",
                    "class_order": ICA_CLASS_ORDER,
                    "estimator_b64": base64.b64encode(pickle.dumps(estimator)).decode("ascii"),
                    "best_params": search.best_params_,
                    "valid_rows": len(feature_rows),
                    "input_window_start": feature_rows[0]["issued_at"].isoformat(),
                    "input_window_end": feature_rows[-1]["issued_at"].isoformat(),
                    "confusion_matrix": confusion_matrix(test_y, test_predictions, labels=list(range(len(ICA_CLASS_ORDER)))).tolist(),
                    "activation_criteria": activation_criteria,
                },
                feature_set_id=feature_set.feature_set_id,
                training_job_id=job.job_id,
                metrics_json=metrics,
                status="candidate",
            )
            self.store.save_model_asset(asset)
            if all(activation_criteria.values()):
                asset = self.store.activate_model_asset(asset.asset_id)
            completed = running.model_copy(
                update={
                    "status": "completed",
                    "finished_at": self._now(),
                    "metrics": metrics,
                    "asset_id": asset.asset_id,
                    "hyperparameters": search.best_params_,
                }
            )
            self.store.save_training_job(completed)
            self._event(
                job.job_id,
                "completed",
                "SVM ICA entrenado con clases derivadas de la formula documentada.",
                {"asset_id": asset.asset_id, "asset_status": asset.status},
            )
            return {
                "status": "completed",
                "model_code": WATER_QUALITY_ICA_SVM_MODEL_CODE,
                "pond_id": pond_id,
                "job": completed.model_dump(mode="json"),
                "asset": self._public_asset(asset),
                "activation_criteria": activation_criteria,
                "data_quality": prepared["quality"],
            }
        except Exception as exc:
            failed = job.model_copy(
                update={"status": "failed", "finished_at": self._now(), "error_message": str(exc)}
            )
            self.store.save_training_job(failed)
            self._event(job.job_id, "failed", str(exc))
            raise

    def ica_svm_classification(
        self,
        pond_id: str,
        prepared: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self._require_persistent_store()
        asset = self.store.active_model_asset(WATER_QUALITY_ICA_SVM_MODEL_CODE)
        if asset is None:
            candidates = self.store.list_model_assets(model_code=WATER_QUALITY_ICA_SVM_MODEL_CODE)
            asset = candidates[0] if candidates else None
        if asset is None:
            return {
                "status": "not_trained",
                "detail": "Aun no existe un artefacto SVM para clasificar el ICA documentado.",
            }
        prepared = prepared or self._prepare_dataset(pond_id, False, 4000)
        latest = self._latest_observed(prepared["aligned"], ICA_FEATURE_NAMES)
        estimator = pickle.loads(base64.b64decode(asset.artifact_payload["estimator_b64"]))
        values = latest["values"]
        predicted_code = int(
            estimator.predict([[float(values[name]) for name in ICA_FEATURE_NAMES]])[0]
        )
        labels = list(asset.artifact_payload["class_order"])
        return {
            "status": "trained",
            "classification": labels[predicted_code],
            "asset_id": asset.asset_id,
            "version": asset.version,
            "metrics": asset.metrics_json,
            "detail": "SVM entrenada con lecturas reales y etiquetas ICA calculadas por la formula documentada.",
            "target_origin": asset.artifact_payload["target_origin"],
        }

    def svm_metrics(self, pond_id: str) -> dict[str, object]:
        active = self.store.active_model_asset(SVM_MODEL_CODE)
        candidates = self.store.list_model_assets(model_code=SVM_MODEL_CODE)
        return {
            "model_code": SVM_MODEL_CODE,
            "pond_id": pond_id,
            "active_asset": self._public_asset(active) if active else None,
            "latest_asset": self._public_asset(candidates[0]) if candidates else None,
        }

    def oxygen_status_for_pond(
        self,
        pond_id: str,
        prepared: dict[str, object] | None = None,
        forecast: dict[str, object] | None = None,
    ) -> dict[str, object]:
        prepared = prepared or self._prepare_dataset(pond_id, False, 4000)
        latest = self._latest_observed(
            prepared["aligned"],
            ["water_temperature_c", "dissolved_oxygen_mg_l"],
        )
        if forecast is None:
            forecast = self.forecast_svm_od(pond_id, prepared)
        projected = (
            float(forecast["forecast_do_mg_l"])
            if forecast.get("status") == "ready"
            else None
        )
        result = oxygen_status(
            float(latest["values"]["water_temperature_c"]),
            float(latest["values"]["dissolved_oxygen_mg_l"]),
            projected,
        )
        return {
            "status": "calculated",
            "model_code": OXYGEN_MODEL_CODE,
            "pond_id": pond_id,
            **result,
            "issued_at": latest["timestamp"].isoformat(),
            "traceability": {
                "formula": "DO_sat(T)=14.589-0.4T+0.008T^2-0.0000661T^3",
                "measured_inputs_only": True,
                "forecast_asset_id": forecast.get("asset_id"),
            },
        }

    def dynamic_oxygen(self, pond_id: str, inputs: dict[str, float | None]) -> dict[str, object]:
        missing = [name for name in DYNAMIC_OXYGEN_INPUTS if inputs.get(name) is None]
        if inputs.get("dt_h") is None:
            missing.append("dt_h")
        if missing:
            return {"status": "not_ready", "missing_real_inputs": missing}
        prepared = self._prepare_dataset(pond_id, False, 4000)
        latest = self._latest_observed(
            prepared["aligned"],
            ["water_temperature_c", "dissolved_oxygen_mg_l"],
        )
        saturation = do_saturation(float(latest["values"]["water_temperature_c"]))
        projected = update_do_0d(
            x_prev=float(latest["values"]["dissolved_oxygen_mg_l"]),
            x_in=float(inputs["do_influent_mg_l"]),
            q_l_h=float(inputs["flow_rate_l_h"]),
            volume_l=float(inputs["raceway_volume_l"]),
            s=float(inputs["oxygen_supply_rate_mg_l_h"]),
            k_rear=float(inputs["reaeration_rate_h_1"]),
            do_sat=saturation,
            biomass_kg=float(inputs["fish_biomass_kg"]),
            respiration_rate=float(inputs["fish_respiration_rate_mg_h_kg"]),
            dt_h=float(inputs["dt_h"]),
        )
        return {
            "status": "calculated",
            "model_code": "DO_DYNAMIC_0D_ROYER_2021",
            "pond_id": pond_id,
            "projected_do_mg_l": projected,
            "inputs": inputs,
        }

    def tilapia_growth(
        self,
        pond_id: str,
        prepared: dict[str, object] | None = None,
        projection_days: int | None = None,
    ) -> dict[str, object]:
        prepared = prepared or self._prepare_dataset(pond_id, False, 4000)
        latest = self._latest_observed(prepared["aligned"], ["water_temperature_c"])
        sample = self.store.latest_biometric_sample(pond_id)
        result = tilapia_growth_temperature(
            float(latest["values"]["water_temperature_c"]),
            float(sample["average_length_mm"])
            if sample and sample.get("average_length_mm") is not None
            else None,
            projection_days,
        )
        return {
            "model_code": GROWTH_MODEL_CODE,
            "pond_id": pond_id,
            **result,
            "sampled_at": sample["sampled_at"].isoformat() if sample else None,
            "traceability": {
                "formula": "delta_L=-1.6707+0.09682T",
                "temperature_source": "parametro_aguas.temperatura",
                "biometric_source": sample.get("source") if sample else None,
            },
        }

    def dashboard(
        self,
        pond_id: str,
        window_hours: int = 168,
        growth_projection_days: int = 7,
    ) -> dict[str, object]:
        prepared = self._prepare_dataset(pond_id, persist_cleaning=False, limit=100000)
        productive_forecast = self.forecast_svm_od(pond_id, prepared)
        display_forecast = (
            productive_forecast
            if productive_forecast.get("status") == "ready"
            else self.forecast_svm_od(pond_id, prepared, allow_candidate=True)
        )
        status = self.oxygen_status_for_pond(pond_id, prepared, productive_forecast)
        growth = self.tilapia_growth(
            pond_id,
            prepared,
            projection_days=growth_projection_days,
        )
        water_quality = self.water_quality_index_for_pond(pond_id, prepared)
        ica_svm = self.ica_svm_classification(pond_id, prepared)
        biometric_assessment = self.store.latest_biometric_assessment(pond_id)
        biometric_context = self._biometric_context(biometric_assessment)
        growth["requested_projection_days"] = growth_projection_days
        latest_od = self._latest_observed(
            prepared["aligned"],
            ["water_temperature_c", "dissolved_oxygen_mg_l"],
        )
        latest_by_variable = {
            code: self._latest_observed(prepared["aligned"], [code])
            for code in REQUIRED_VARIABLES
        }
        dynamic = {"status": "not_ready", "missing_real_inputs": DYNAMIC_OXYGEN_INPUTS}

        history_rows = self._history_window(prepared["aligned"], window_hours)
        observed_do = [
            [row["timestamp"].isoformat(), float(row["values"]["dissolved_oxygen_mg_l"])]
            for row in history_rows
            if row["values"].get("dissolved_oxygen_mg_l") is not None
            and "dissolved_oxygen_mg_l" not in row.get("invalid_variables", set())
        ]
        saturation_history = [
            [
                row["timestamp"].isoformat(),
                float(row["values"]["dissolved_oxygen_mg_l"])
                / do_saturation(float(row["values"]["water_temperature_c"]))
                * 100.0,
            ]
            for row in history_rows
            if row["values"].get("water_temperature_c") is not None
            and row["values"].get("dissolved_oxygen_mg_l") is not None
            and "water_temperature_c" not in row.get("invalid_variables", set())
            and "dissolved_oxygen_mg_l" not in row.get("invalid_variables", set())
        ]
        growth_history = []
        ica_history = []
        temperatures = []
        for row in history_rows:
            temperature = row["values"].get("water_temperature_c")
            observed = row["values"].get("dissolved_oxygen_mg_l")
            if temperature is None:
                continue
            temperatures.append(float(temperature))
            calculated = tilapia_growth_temperature(float(temperature))
            if calculated["daily_length_gain_mm_day"] is not None:
                growth_history.append(
                    [row["timestamp"].isoformat(), calculated["daily_length_gain_mm_day"]]
                )
            values = row["values"]
            if all(
                values.get(code) is not None and code not in row.get("invalid_variables", set())
                for code in REQUIRED_VARIABLES
            ):
                ica_history.append(
                    [
                        row["timestamp"].isoformat(),
                        water_quality_index(
                            float(values["water_temperature_c"]),
                            float(values["ph"]),
                            float(values["dissolved_oxygen_mg_l"]),
                            float(values["nitrate_ion"]),
                        )["ica"],
                    ]
                )

        forecast_points = []
        if display_forecast.get("status") in {"ready", "candidate_test"}:
            forecast_points = [
                [display_forecast["issued_at"], display_forecast["current_do_mg_l"]],
                [display_forecast["target_time"], display_forecast["forecast_do_mg_l"]],
            ]
        short_projection_focus = None
        if forecast_points:
            issued_at = datetime.fromisoformat(str(display_forecast["issued_at"]))
            short_projection_focus = (
                issued_at - timedelta(hours=min(window_hours, 3))
            ).isoformat()
        oxygen_projection_points = self._oxygen_projection_points(
            latest_od,
            display_forecast,
        )
        growth_projection_points = self._growth_rate_projection_points(
            latest_od["timestamp"],
            growth,
            growth_projection_days,
        )
        candidates = self.store.list_model_assets(model_code=SVM_MODEL_CODE)
        latest_candidate = self._public_asset(candidates[0]) if candidates else {}
        warnings = list(prepared["quality"].get("warnings", []))
        if productive_forecast.get("status") != "ready":
            warnings.append(
                "La SVM esta entrenada y se muestra en evaluacion tecnica; "
                "la persistencia aun tiene menor error para uso automatico."
            )

        svm_chart = self._chart(
            "Oxigeno disuelto: medicion y estimacion a una hora",
            [
                self._series("OD observado", observed_do, "#0d6efd"),
                self._series(
                    "Estimacion IA +1h",
                    forecast_points,
                    "#20a854" if display_forecast.get("status") == "ready" else "#f59e0b",
                    dashed=True,
                ),
            ],
            "mg/L",
            focus_from=short_projection_focus,
        )
        latest_candidate_payload = latest_candidate.get("artifact_payload", {})
        activation_criteria = latest_candidate_payload.get("activation_criteria", {})
        svm_ready = productive_forecast.get("status") == "ready"
        svm_usage = {
            "status": "en_uso" if svm_ready else "candidato_bloqueado",
            "label": "Usado en proyeccion productiva" if svm_ready else "Modelo entrenado en evaluacion tecnica",
            "detail": (
                "El artefacto activo genera la estimacion de OD a una hora."
                if svm_ready
                else "Hay un modelo IA entrenado. La persistencia conserva menor MAE, por eso la estimacion no activa alertas ni decisiones automaticas."
            ),
            "activation_criteria": activation_criteria,
        }
        ica_chart = self._chart(
            "Indice de calidad de agua calculado con sensores reales",
            [self._series("ICA", ica_history, "#14b8a6")],
            "ICA",
        )
        ica_chart["series"][0]["markLine"] = {
            "silent": True,
            "lineStyle": {"type": "dashed", "color": "#94a3b8"},
            "data": [
                {"yAxis": 90, "name": "Excelente"},
                {"yAxis": 70, "name": "Buena"},
                {"yAxis": 50, "name": "Regular"},
                {"yAxis": 25, "name": "Mala"},
            ],
        }
        models = [
            {
                "code": SVM_MODEL_CODE,
                "name": "Proyeccion de oxigeno disuelto a 1 hora",
                "message": "SVR temporal entrenado con temperatura, pH, OD e ion nitrato reales.",
                "status": "asset_activo" if svm_ready else "candidato_bloqueado",
                "current_value": latest_od["values"]["dissolved_oxygen_mg_l"],
                "unit": "mg/L",
                "engine": "FastAPI / scikit-learn",
                "source": "MySQL sismapiscis.parametro_aguas",
                "asset_id": display_forecast.get("asset_id") or latest_candidate.get("asset_id"),
                "version": display_forecast.get("asset_version") or latest_candidate.get("version"),
                "metrics": display_forecast.get("metrics") or latest_candidate.get("metrics_json", {}),
                "forecast": [
                    {
                        "timestamp": display_forecast.get("target_time"),
                        "label": "Proyeccion productiva +1 hora" if svm_ready else "Estimacion IA +1 hora",
                        "value": display_forecast.get("forecast_do_mg_l"),
                    }
                ] if display_forecast.get("status") in {"ready", "candidate_test"} else [],
                "chart": svm_chart,
                "chart_description": "Azul: oxigeno medido. La linea punteada muestra la estimacion a una hora del modelo IA entrenado.",
                "relationship": {
                    "description": "Las barras muestran que variables cambian mas el error de la SVM al alterarlas. Una barra mayor indica mayor peso para la estimacion.",
                    "chart": self._svm_influence_chart(candidates[0] if candidates else None, prepared["feature_rows"]),
                },
                "formula": {
                    "expression": "OD(t+1h) = SVR_RBF(StandardScaler(X_t))",
                    "latex": r"\widehat{OD}_{t+1h}=\sum_{i=1}^{n}(\alpha_i-\alpha_i^*)e^{-\gamma\lVert x_i-x_t\rVert^2}+b",
                    "detail": "X_t contiene temperatura, pH, OD e ion nitrato actuales; sus retardos 1, 2, 3 y 6; medias, desviacion estandar y hora ciclica.",
                    "kernel": "K(x, x') = exp(-gamma ||x - x'||^2)",
                    "conditions": [
                        "Horizonte fijo validado: 1 hora.",
                        "Entrenamiento temporal 70/15/15 con TimeSeriesSplit de 5 particiones.",
                        "Solo se activa si MAE mejora la persistencia y R2 de evaluacion es positivo.",
                    ],
                },
                "origin": {
                    "document": "Biometria1.docx, secciones 4.4 y 4.7; DIRECTIVA_CODEX_3_MODELOS_DATOS_REALES.md, seccion 2.",
                    "data": "parametro_aguas: temperatura, pH, OD e ion nitrato; 14,997 ventanas validas.",
                },
                "usage": svm_usage,
                "traceability": display_forecast.get("traceability", {}),
            },
            {
                "code": OXYGEN_MODEL_CODE,
                "name": "Estado fisico del oxigeno disuelto",
                "message": "Saturacion y deficit calculados con temperatura y OD medidos.",
                "status": "calculado",
                "current_value": status["saturation_percent"],
                "unit": "%",
                "engine": "FastAPI / formula deterministica",
                "source": "Informe 016",
                "asset_id": None,
                "version": "formula-v1",
                "metrics": {},
                "forecast": [
                    {"label": "Saturacion actual", "value": status["saturation_percent"]},
                    {"label": "Deficit actual", "value": status["oxygen_deficit_mg_l"]},
                    {
                        "label": "Saturacion estimada +1 hora",
                        "value": self._oxygen_projection_value(display_forecast, latest_od),
                        "unit": "%",
                    },
                ],
                "chart": self._chart(
                    "Saturacion de oxigeno: medida y estimacion a una hora",
                    [
                        self._series("Saturacion medida", saturation_history, "#0d6efd"),
                        self._series(
                            "Estimacion IA a +1h",
                            oxygen_projection_points,
                            "#20a854" if svm_ready else "#f59e0b",
                            dashed=True,
                        ),
                    ],
                    "%",
                    focus_from=short_projection_focus,
                ),
                "chart_description": "Azul: porcentaje real de saturacion. La linea punteada convierte la estimacion de OD a una hora en porcentaje de saturacion.",
                "relationship": {
                    "description": "La temperatura define cuanto oxigeno puede contener el agua. El punto marca la lectura actual de la piscina.",
                    "chart": self._oxygen_temperature_chart(temperatures, latest_od),
                },
                "formula": {
                    "expression": "OD_sat(T) = 14.589 - 0.4T + 0.008T^2 - 0.0000661T^3",
                    "latex": r"OD_{sat}(T)=14.589-0.4T+0.008T^2-0.0000661T^3",
                    "detail": "Saturacion (%) = 100 x OD medido / OD_sat(T); deficit = OD_sat(T) - OD medido.",
                    "conditions": [
                        "Usa exclusivamente temperatura y OD medidos en MySQL local.",
                        "No extrapola una proyeccion temporal ni requiere entrenamiento.",
                    ],
                },
                "origin": {
                    "document": "Informe016_Oxigeno_Disuelto y DIRECTIVA_CODEX_3_MODELOS_DATOS_REALES.md, seccion 3.",
                    "data": "Ultima temperatura y OD limpios de parametro_aguas.",
                },
                "usage": {
                    "status": "en_uso",
                    "label": "Calculado con la ultima medicion real",
                    "detail": "El resultado se actualiza con cada consulta usando temperatura y OD observados.",
                },
                "traceability": status["traceability"],
            },
            {
                "code": GROWTH_MODEL_CODE,
                "name": "Crecimiento de tilapia por temperatura",
                "message": "Ganancia diaria de longitud dentro del dominio publicado de 21 a 30 C.",
                "status": "calculado" if growth["status"] == "calculated" else "sin_datos",
                "current_value": growth["daily_length_gain_mm_day"],
                "unit": "mm/dia",
                "engine": "FastAPI / formula deterministica",
                "source": "Informe 017",
                "asset_id": None,
                "version": "formula-v1",
                "metrics": {"r2": growth["source_r2"]},
                "forecast": self._growth_forecast_rows(growth),
                "chart": self._chart(
                    "Ganancia diaria de crecimiento: medida y proyeccion",
                    [
                        self._series("Ganancia calculada", growth_history, "#7c3aed"),
                        self._series(
                            "Proyeccion con temperatura actual",
                            growth_projection_points,
                            "#7c3aed",
                            dashed=True,
                        ),
                    ],
                    "mm/dia",
                    focus_from=(
                        latest_od["timestamp"]
                        - timedelta(hours=min(window_hours, 24))
                    ).isoformat(),
                ),
                "chart_description": "La linea continua usa la temperatura real de cada momento. La punteada mantiene la temperatura actual durante el periodo elegido.",
                "relationship": {
                    "description": "Esta curva muestra la ganancia diaria que corresponde a cada temperatura dentro del rango validado para tilapia.",
                    "chart": self._growth_temperature_chart(latest_od),
                },
                "formula": {
                    "expression": "Delta L = -1.6707 + 0.09682T (mm/dia)",
                    "latex": r"\Delta L=-1.6707+0.09682T",
                    "detail": "Si existe una biometria real: L(t+d) = L(t) + d x Delta L.",
                    "conditions": [
                        "Dominio validado para tilapia: 21 a 30 C.",
                        "La longitud y peso futuros solo se calculan con una longitud inicial biometrica real.",
                    ],
                },
                "origin": {
                    "document": "Informe017_Crecimiento_Alimentacion_ML y DIRECTIVA_CODEX_3_MODELOS_DATOS_REALES.md, seccion 4.",
                    "data": "Temperatura de parametro_aguas y biometria real cuando existe.",
                },
                "usage": self._growth_usage(growth),
                "biometric_context": biometric_context,
                "traceability": growth["traceability"],
            },
            {
                "code": WATER_QUALITY_ICA_MODEL_CODE,
                "name": "Indice de calidad de agua",
                "message": "Puntaje ponderado con temperatura, pH, oxigeno disuelto e ion nitrato reales.",
                "status": "calculado",
                "current_value": water_quality["ica"],
                "unit": "/100",
                "engine": "FastAPI / formula documentada",
                "source": "Biometria1.docx, seccion 4.1",
                "asset_id": None,
                "version": "ica-formula-v1",
                "metrics": {},
                "forecast": [
                    {
                        "label": f"Clasificacion actual: {water_quality['classification']}",
                        "value": water_quality["ica"],
                        "unit": "/100",
                    }
                ],
                "chart": ica_chart,
                "chart_description": "La linea muestra el ICA calculado en cada lectura valida; las lineas horizontales separan sus niveles de interpretacion.",
                "relationship": {
                    "description": "Cada barra es el aporte ponderado de una variable al ICA actual. Oxigeno disuelto tiene el mayor peso documentado.",
                    "chart": self._ica_components_chart(water_quality["components"]),
                },
                "formula": {
                    "expression": "ICA = 0.25Q_T + 0.25Q_pH + 0.35Q_OD + 0.15Q_NO3",
                    "latex": r"\mathrm{ICA}=0.25Q_T+0.25Q_{pH}+0.35Q_{OD}+0.15Q_{NO_3}",
                    "detail": "Cada Q se normaliza de 0 a 100 con los rangos del documento; el resultado actual se clasifica como " + str(water_quality["classification"]) + ".",
                    "conditions": [
                        "Temperatura optima: 26 a 30 C; pH optimo: 6.5 a 8.5.",
                        "OD obtiene 100 desde 5 mg/L; nitrato obtiene 100 por debajo de 50 mg/L.",
                        "Es un calculo deterministico: no necesita entrenar un artefacto.",
                    ],
                },
                "origin": {
                    "document": "Biometria1.docx, seccion 4.1.",
                    "data": "Las cuatro lecturas limpias de parametro_aguas; no usa datos simulados.",
                },
                "usage": {
                    "status": "en_uso",
                    "label": f"Calidad actual: {water_quality['classification']}",
                    "detail": "Se recalcula con la ultima lectura limpia de los cuatro sensores locales.",
                },
                "interpretation": water_quality["interpretation"],
                "components": water_quality["components"],
                "machine_learning": ica_svm,
                "traceability": water_quality["traceability"],
            },
        ]
        active_asset = self.store.active_model_asset(SVM_MODEL_CODE)
        display_asset = active_asset or (candidates[0] if candidates else None)
        return {
            "status": "ok",
            "backend_engine": "FastAPI local / scikit-learn",
            "backend_url": "http://aquaculture_backend:8000/api/v1",
            "pond_id": pond_id,
            "latest_measurement": {
                "timestamp": latest_od["timestamp"].isoformat(),
                **{
                    code: latest_by_variable[code]["values"][code]
                    for code in REQUIRED_VARIABLES
                },
            },
            "svm_od_forecast": display_forecast,
            "ai_model": {
                "trained": display_asset is not None,
                "asset_id": display_asset.asset_id if display_asset else None,
                "version": display_asset.version if display_asset else None,
                "productive": active_asset is not None,
                "estimated_as": "productiva" if active_asset else "evaluacion_tecnica",
                "detail": (
                    "El modelo SVM entrenado se usa para la proyeccion productiva de OD a una hora."
                    if active_asset
                    else "El modelo SVM esta entrenado y muestra su estimacion de OD a una hora; la persistencia aun tiene menor MAE para automatizar decisiones."
                ) if display_asset else "No hay un artefacto SVM entrenado disponible.",
            },
            "oxygen_status": status,
            "tilapia_growth": growth,
            "ica_svm": ica_svm,
            "biometrics": biometric_context,
            "biofloc_water_quality": self.biofloc_water_quality(),
            "dynamic_oxygen": dynamic,
            "data_quality": prepared["quality"],
            "warnings": warnings,
            "traceability": {
                "source": "FastAPI local -> MySQL local",
                "source_table": "sismapiscis.parametro_aguas",
                "timestamp_field": "created_at",
                "projection_method": "SVM 1h + formulas publicadas",
                "uses_all_points": True,
                "generated_data_used": False,
                "chart_window_hours": window_hours,
                "cleaning_run_id": prepared["cleaning_run"].run_id if prepared.get("cleaning_run") else None,
            },
            "filters": {
                "window_hours": window_hours,
                "window_label": self._window_label(window_hours),
                "svm_horizon_label": "1 hora (horizonte validado)",
                "growth_projection_days": growth_projection_days,
                "growth_projection_label": f"{growth_projection_days} dias",
            },
            "latest": {
                "timestamp": latest_od["timestamp"].isoformat(),
                "ion_nitrato": latest_by_variable["nitrate_ion"]["values"]["nitrate_ion"],
                "ion_nitrato_unit": "mg/L",
                "oxigeno_disuelto": latest_od["values"]["dissolved_oxygen_mg_l"],
                "oxigeno_disuelto_unit": "mg/L",
                "piscina": pond_id,
            },
            "summary": {
                "samples": prepared["quality"]["aligned_points"],
                "from": prepared["quality"]["first_timestamp"],
                "to": prepared["quality"]["last_timestamp"],
                "historical_points": len(observed_do),
                "all_historical_points": prepared["quality"]["aligned_points"],
                "forecast_points": len(forecast_points),
                "training_rows": {
                    SVM_MODEL_CODE: display_asset.artifact_payload.get("valid_windows", 0)
                    if display_asset else 0
                },
            },
            "lifecycle": {
                "status": "production" if active_asset else "evaluation",
                "summary": [
                    {
                        "step": "Datos reales",
                        "detail": "Temperatura, pH, OD e ion nitrato se leen de MySQL local.",
                    },
                    {
                        "step": "Limpieza temporal",
                        "detail": "Se eliminan duplicados, se aplican limites y Hampel/MAD; solo se interpolan huecos internos cortos.",
                    },
                    {
                        "step": "Entrenamiento",
                        "detail": "La SVR aprende OD a una hora con division cronologica y validacion temporal.",
                    },
                    {
                        "step": "Uso",
                        "detail": "La formula ICA y los modelos fisicos se calculan en cada consulta; la SVR se compara con persistencia antes de automatizar decisiones.",
                    },
                ],
                "models": [
                    {
                        "model_code": SVM_MODEL_CODE,
                        "algorithm": "StandardScaler + SVR RBF",
                        "artifact_path": display_asset.artifact_path if display_asset else None,
                        "training_rows": display_asset.artifact_payload.get("valid_windows")
                        if display_asset else 0,
                    },
                    {"model_code": OXYGEN_MODEL_CODE, "algorithm": "formula", "training_rows": 0},
                    {"model_code": GROWTH_MODEL_CODE, "algorithm": "formula", "training_rows": 0},
                    {"model_code": WATER_QUALITY_ICA_MODEL_CODE, "algorithm": "formula", "training_rows": 0},
                    {
                        "model_code": WATER_QUALITY_ICA_SVM_MODEL_CODE,
                        "algorithm": "StandardScaler + SVC RBF",
                        "training_rows": ica_svm.get("metrics", {}).get("valid_rows", 0),
                    },
                ],
            },
            "models": models,
        }

    def _prepare_dataset(
        self,
        pond_id: str,
        persist_cleaning: bool,
        limit: int,
    ) -> dict[str, object]:
        self._require_persistent_store()
        self.store.sync_legacy_data(force=False)
        raw_rows = self.store.list_raw_measurements(pond_id=pond_id, limit=limit)
        grouped = {
            code: sorted(
                [row for row in raw_rows if row.variable_code == code],
                key=lambda row: row.time,
            )
            for code in REQUIRED_VARIABLES
        }
        missing = [code for code, rows in grouped.items() if not rows]
        if missing:
            raise ValueError(f"faltan sensores reales para {pond_id}: {', '.join(missing)}")

        run_id = self._new_id("CLEANRUN")
        processed_series: dict[str, list[tuple[datetime, float | None]]] = {}
        invalid_times: dict[str, set[datetime]] = {}
        interpolated_times: dict[str, set[datetime]] = {}
        clean_rows: list[CleanMeasurementRead] = []
        quality_by_variable: dict[str, dict[str, object]] = {}

        for code, rows in grouped.items():
            deduplicated = []
            seen: set[tuple[datetime, float | None]] = set()
            for row in rows:
                key = (row.time, row.raw_value)
                if key in seen:
                    continue
                seen.add(key)
                deduplicated.append(row)
            metadata = self.store.get_variable_metadata(code) or {}
            minimum = metadata.get("minimum_valid")
            maximum = metadata.get("maximum_valid")
            values = [float(row.raw_value) if row.raw_value is not None else None for row in deduplicated]
            physical_flags = [
                value is not None
                and ((minimum is not None and value < float(minimum))
                     or (maximum is not None and value > float(maximum)))
                for value in values
            ]
            bounded = [None if invalid else value for value, invalid in zip(values, physical_flags)]
            robust_flags = hampel_flags(bounded, window_radius=6, threshold=3.5)
            invalid = [physical or robust for physical, robust in zip(physical_flags, robust_flags)]
            without_outliers = [None if flag else value for value, flag in zip(bounded, robust_flags)]
            interpolated, interpolated_indexes = interpolate_short_internal_gaps(
                without_outliers,
                max_gap=2,
            )
            invalid_times[code] = {
                row.time for row, flag in zip(deduplicated, invalid) if flag
            }
            interpolated_times[code] = {
                deduplicated[index].time for index in interpolated_indexes
            }
            processed_series[code] = [
                (row.time, value) for row, value in zip(deduplicated, interpolated)
            ]
            for index, (raw, clean_value) in enumerate(zip(deduplicated, interpolated)):
                if clean_value is None:
                    continue
                flag = "interpolated_short_gap" if index in interpolated_indexes else "cleaned_valid"
                clean_rows.append(
                    CleanMeasurementRead(
                        id=f"{run_id}-{raw.id}",
                        raw_measurement_id=raw.id,
                        time=raw.time,
                        farm_id=raw.farm_id,
                        pond_id=raw.pond_id,
                        sensor_id=raw.sensor_id,
                        variable_code=raw.variable_code,
                        clean_value=float(clean_value),
                        standard_unit=str(metadata.get("standard_unit") or raw.raw_unit or "unknown"),
                        quality_flag=flag,
                        validation_status="accepted",
                        cleaning_method="physical_bounds+hampel_mad+internal_gap_max_2",
                    )
                )
            quality_by_variable[code] = {
                "raw_points": len(rows),
                "deduplicated_points": len(deduplicated),
                "invalid_points": sum(invalid),
                "interpolated_points": len(interpolated_indexes),
                "unit": metadata.get("standard_unit"),
                "unit_verified": bool(metadata.get("verified_at")),
            }

        aligned, sampling_minutes = align_sensor_series(processed_series, REQUIRED_VARIABLES)
        for row in aligned:
            for code, source_time in row["source_times"].items():
                if source_time in invalid_times[code]:
                    row["invalid_variables"].add(code)
                if source_time in interpolated_times[code]:
                    row["interpolated_variables"].add(code)
        feature_rows, horizon_steps, feature_names = build_svm_od_feature_rows(
            aligned,
            sampling_minutes,
            REQUIRED_VARIABLES,
        )

        warnings = []
        nitrate_invalid = quality_by_variable["nitrate_ion"]["invalid_points"]
        if nitrate_invalid:
            warnings.append(
                f"Se excluyeron {nitrate_invalid} lecturas de ion nitrato por Hampel/MAD."
            )
        if not self.store.get_variable_metadata("water_temperature_c").get("maximum_valid"):
            warnings.append(
                "El rango maximo del sensor de temperatura no esta documentado; se aplico Hampel/MAD."
            )
        quality = {
            "raw_points": len(raw_rows),
            "aligned_points": len(aligned),
            "valid_training_windows": len(feature_rows),
            "sampling_minutes": sampling_minutes,
            "horizon_steps": horizon_steps,
            "first_timestamp": aligned[0]["timestamp"].isoformat(),
            "last_timestamp": aligned[-1]["timestamp"].isoformat(),
            "variables": quality_by_variable,
            "warnings": warnings,
        }
        cleaning_run = CleaningRunRead(
            run_id=run_id,
            pond_id=pond_id,
            variable_codes=REQUIRED_VARIABLES,
            status="completed",
            started_at=self._now(),
            finished_at=self._now(),
            records_in=len(raw_rows),
            records_out=len(clean_rows),
            interpolated_points=sum(
                int(item["interpolated_points"]) for item in quality_by_variable.values()
            ),
            outliers_detected=sum(
                int(item["invalid_points"]) for item in quality_by_variable.values()
            ),
            normalized_points=0,
            steps=[
                CleaningRunStepRead(step_name="deduplicate", status="completed"),
                CleaningRunStepRead(step_name="physical_validation", status="completed"),
                CleaningRunStepRead(step_name="hampel_mad", status="completed"),
                CleaningRunStepRead(
                    step_name="interpolate_internal_gaps_max_2",
                    status="completed",
                ),
                CleaningRunStepRead(step_name="align_by_timestamp", status="completed"),
            ],
            warnings=warnings,
        )
        if persist_cleaning:
            self.store.save_cleaning_run_measurements(run_id, clean_rows)
            self.store.save_cleaning_run(cleaning_run)
        return {
            "aligned": aligned,
            "sampling_minutes": sampling_minutes,
            "feature_rows": feature_rows,
            "horizon_steps": horizon_steps,
            "feature_names": feature_names,
            "quality": quality,
            "cleaning_run": cleaning_run,
        }

    def _save_feature_set(
        self,
        pond_id: str,
        cleaning_run_id: str,
        feature_rows: list[dict[str, object]],
        feature_names: list[str],
        horizon_steps: int,
        target_variable: str = "dissolved_oxygen_mg_l",
        target_unit: str | None = "mg/L",
        feature_variables: list[str] | None = None,
        window_size: int = 7,
    ) -> FeatureSetRead:
        rows = []
        for source in feature_rows:
            row = {
                "row_index": source["row_index"],
                **{name: source[name] for name in feature_names},
                "target": source["target"],
                "issued_at": source["issued_at"].isoformat(),
                "target_time": source["target_time"].isoformat(),
                "interpolated_ratio": source["interpolated_ratio"],
            }
            rows.append(row)
        train_rows = int(len(rows) * 0.70)
        validation_rows = int(len(rows) * 0.15)
        feature_set = FeatureSetRead(
            feature_set_id=self._new_id("FEATURESET"),
            pond_id=pond_id,
            target_variable=target_variable,
            feature_variables=feature_variables or REQUIRED_VARIABLES,
            cleaning_run_id=cleaning_run_id,
            window_size=window_size,
            horizon=horizon_steps,
            rows_count=len(rows),
            train_rows=train_rows,
            validation_rows=validation_rows,
            test_rows=len(rows) - train_rows - validation_rows,
            columns=[
                *[
                    FeatureSetColumnRead(
                        name=name,
                        role="feature",
                        source_variable=name.split("_lag_")[0],
                    )
                    for name in feature_names
                ],
                FeatureSetColumnRead(
                    name="target",
                    role="target",
                    source_variable=target_variable,
                    unit=target_unit,
                ),
            ],
            rows=rows,
        )
        return self.store.save_feature_set(feature_set)

    def _event(
        self,
        job_id: str,
        event_type: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        self.store.append_training_job_event(
            TrainingJobEventRead(
                event_id=self._new_id("TRAINEVENT"),
                job_id=job_id,
                event_type=event_type,
                message=message,
                payload=payload or {},
            )
        )

    def _next_version(self, model_code: str = SVM_MODEL_CODE) -> str:
        return f"v{len(self.store.list_model_assets(model_code=model_code)) + 1}"

    @staticmethod
    def _latest_observed(
        aligned_rows: list[dict[str, object]],
        variables: list[str],
    ) -> dict[str, object]:
        for row in reversed(aligned_rows):
            invalid = row.get("invalid_variables", set())
            values = row["values"]
            if all(values.get(code) is not None and code not in invalid for code in variables):
                return row
        raise ValueError(
            f"no hay una medicion real valida para {', '.join(variables)}"
        )

    @staticmethod
    def _public_asset(asset: ModelAssetRead | None) -> dict[str, object] | None:
        if asset is None:
            return None
        payload = asset.model_dump(mode="json")
        payload["artifact_payload"].pop("estimator_b64", None)
        return payload

    @staticmethod
    def _history_window(
        aligned_rows: list[dict[str, object]],
        window_hours: int,
    ) -> list[dict[str, object]]:
        if not aligned_rows:
            return []
        latest_time = aligned_rows[-1]["timestamp"]
        cutoff = latest_time - timedelta(hours=window_hours)
        selected = [row for row in aligned_rows if row["timestamp"] >= cutoff]
        return selected or aligned_rows[-min(len(aligned_rows), 250):]

    @staticmethod
    def _window_label(window_hours: int) -> str:
        labels = {
            6: "Ultimas 6 horas",
            24: "Ultimas 24 horas",
            168: "Ultimos 7 dias",
            720: "Ultimos 30 dias",
            2160: "Ultimos 90 dias",
        }
        return labels.get(window_hours, f"Ultimas {window_hours} horas")

    @staticmethod
    def _growth_forecast_rows(growth: dict[str, object]) -> list[dict[str, object]]:
        projection = growth.get("length_projection")
        days = int(growth.get("requested_projection_days", 1))
        daily_gain = growth.get("daily_length_gain_mm_day")
        rows = []
        if daily_gain is not None:
            rows.append(
                {
                    "label": f"Ganancia diaria durante {days} dias",
                    "value": daily_gain,
                    "unit": "mm/dia",
                }
            )
        if not isinstance(projection, dict):
            return rows
        return [
            *rows,
            {
                "label": f"Longitud en {projection['projection_days']} dias",
                "value": projection["projected_length_mm"],
                "unit": "mm",
            },
            {
                "label": f"Peso estimado en {projection['projection_days']} dias",
                "value": projection["projected_weight_g"],
                "unit": "g",
            },
        ]

    @staticmethod
    def _growth_usage(growth: dict[str, object]) -> dict[str, str]:
        if growth.get("status") != "calculated":
            return {
                "status": "fuera_de_dominio",
                "label": "No calculado fuera del dominio validado",
                "detail": "La temperatura actual esta fuera del intervalo de 21 a 30 C.",
            }
        if growth.get("length_projection") is None:
            return {
                "status": "calculo_parcial",
                "label": "Ganancia diaria calculada; proyeccion bloqueada",
                "detail": "Falta una longitud inicial de una muestra biometrica real para proyectar longitud y peso.",
            }
        return {
            "status": "en_uso",
            "label": "Proyeccion calculada desde biometria real",
            "detail": "La longitud y el peso se proyectan para el horizonte seleccionado.",
        }

    @staticmethod
    def _oxygen_projection_value(
        forecast: dict[str, object],
        latest_od: dict[str, object],
    ) -> float | None:
        if forecast.get("status") not in {"ready", "candidate_test"}:
            return None
        temperature = latest_od["values"].get("water_temperature_c")
        projected_od = forecast.get("forecast_do_mg_l")
        if temperature is None or projected_od is None:
            return None
        saturation = do_saturation(float(temperature))
        return float(projected_od) / saturation * 100.0

    @classmethod
    def _oxygen_projection_points(
        cls,
        latest_od: dict[str, object],
        forecast: dict[str, object],
    ) -> list[list[object]]:
        projected = cls._oxygen_projection_value(forecast, latest_od)
        if projected is None:
            return []
        temperature = float(latest_od["values"]["water_temperature_c"])
        current_od = float(latest_od["values"]["dissolved_oxygen_mg_l"])
        current = current_od / do_saturation(temperature) * 100.0
        return [
            [forecast["issued_at"], current],
            [forecast["target_time"], projected],
        ]

    @staticmethod
    def _growth_rate_projection_points(
        issued_at: datetime,
        growth: dict[str, object],
        days: int,
    ) -> list[list[object]]:
        daily_gain = growth.get("daily_length_gain_mm_day")
        if growth.get("status") != "calculated" or daily_gain is None:
            return []
        return [
            [issued_at.isoformat(), float(daily_gain)],
            [(issued_at + timedelta(days=days)).isoformat(), float(daily_gain)],
        ]

    @staticmethod
    def _relationship_chart(
        title: str,
        description: str,
        x_name: str,
        y_name: str,
        curve: list[list[float]],
        current: list[float] | None,
        color: str,
    ) -> dict[str, object]:
        return {
            "title": {
                "text": title,
                "subtext": description,
                "left": 12,
                "textStyle": {"fontSize": 14},
                "subtextStyle": {"fontSize": 11},
            },
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 48},
            "grid": {"top": 88, "left": 68, "right": 36, "bottom": 52},
            "xAxis": {"type": "value", "name": x_name, "scale": True},
            "yAxis": {"type": "value", "name": y_name, "scale": True},
            "series": [
                {
                    "name": "Relacion del modelo",
                    "type": "line",
                    "showSymbol": False,
                    "data": curve,
                    "lineStyle": {"width": 2, "color": color},
                    "itemStyle": {"color": color},
                },
                {
                    "name": "Lectura actual",
                    "type": "scatter",
                    "symbolSize": 10,
                    "data": [current] if current else [],
                    "itemStyle": {"color": "#ef4444"},
                },
            ],
        }

    @classmethod
    def _oxygen_temperature_chart(
        cls,
        temperatures: list[float],
        latest_od: dict[str, object],
    ) -> dict[str, object]:
        latest_temperature = float(latest_od["values"]["water_temperature_c"])
        lower = min(temperatures, default=latest_temperature) - 1.0
        upper = max(temperatures, default=latest_temperature) + 1.0
        if upper - lower < 4.0:
            lower -= 2.0
            upper += 2.0
        curve = [
            [temperature, do_saturation(temperature)]
            for temperature in [lower + (upper - lower) * index / 40 for index in range(41)]
        ]
        return cls._relationship_chart(
            "Temperatura y oxigeno que puede contener el agua",
            "La curva sale de la formula de saturacion; el punto rojo es la temperatura actual.",
            "Temperatura (C)",
            "OD de saturacion (mg/L)",
            curve,
            [latest_temperature, do_saturation(latest_temperature)],
            "#0d6efd",
        )

    @classmethod
    def _growth_temperature_chart(cls, latest_od: dict[str, object]) -> dict[str, object]:
        curve = []
        for index in range(37):
            temperature = 21.0 + index * 0.25
            calculated = tilapia_growth_temperature(temperature)
            curve.append([temperature, float(calculated["daily_length_gain_mm_day"])])
        latest_temperature = float(latest_od["values"]["water_temperature_c"])
        current_growth = tilapia_growth_temperature(latest_temperature)
        current = None
        if current_growth.get("daily_length_gain_mm_day") is not None:
            current = [latest_temperature, float(current_growth["daily_length_gain_mm_day"])]
        return cls._relationship_chart(
            "Temperatura y ganancia diaria de tilapia",
            "La curva solo cubre el intervalo validado de 21 a 30 C; el punto rojo es la lectura actual.",
            "Temperatura (C)",
            "Ganancia (mm/dia)",
            curve,
            current,
            "#7c3aed",
        )

    @staticmethod
    def _ica_components_chart(components: list[dict[str, object]]) -> dict[str, object]:
        labels = [str(component["variable"]) for component in components]
        contributions = [
            round(
                float(component["normalized_score"]) * float(component["weight"]),
                2,
            )
            for component in components
        ]
        return {
            "title": {
                "text": "Aporte de cada sensor al ICA actual",
                "left": 12,
                "textStyle": {"fontSize": 14},
            },
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"top": 56, "left": 52, "right": 24, "bottom": 48},
            "xAxis": {"type": "category", "data": labels, "axisLabel": {"interval": 0}},
            "yAxis": {"type": "value", "name": "Puntos ICA", "max": 35},
            "series": [
                {
                    "name": "Aporte ponderado",
                    "type": "bar",
                    "data": contributions,
                    "itemStyle": {"color": "#14b8a6"},
                    "label": {"show": True, "position": "top"},
                }
            ],
        }

    @staticmethod
    def _svm_influence_chart(
        asset: ModelAssetRead | None,
        feature_rows: list[dict[str, object]],
    ) -> dict[str, object]:
        labels = {
            "water_temperature_c": "Temperatura",
            "ph": "pH",
            "dissolved_oxygen_mg_l": "OD actual",
            "nitrate_ion": "Ion nitrato",
            "hour_": "Hora del dia",
        }
        influence = {label: 0.0 for label in labels.values()}
        if asset and feature_rows:
            try:
                feature_names = list(asset.artifact_payload["feature_names"])
                estimator = pickle.loads(base64.b64decode(asset.artifact_payload["estimator_b64"]))
                selected = feature_rows[-min(300, len(feature_rows)):]
                matrix = [
                    [float(row[name]) for name in feature_names]
                    for row in selected
                ]
                target = [float(row["target"]) for row in selected]
                baseline_predictions = estimator.predict(matrix)
                baseline_mae = sum(
                    abs(float(prediction) - actual)
                    for prediction, actual in zip(baseline_predictions, target)
                ) / len(target)
                rng = random.Random(42)
                for prefix, label in labels.items():
                    indexes = [
                        index for index, name in enumerate(feature_names)
                        if name.startswith(prefix)
                    ]
                    if not indexes:
                        continue
                    order = list(range(len(matrix)))
                    rng.shuffle(order)
                    shuffled = [list(values) for values in matrix]
                    for row_index, source_index in enumerate(order):
                        for feature_index in indexes:
                            shuffled[row_index][feature_index] = matrix[source_index][feature_index]
                    predictions = estimator.predict(shuffled)
                    mae = sum(
                        abs(float(prediction) - actual)
                        for prediction, actual in zip(predictions, target)
                    ) / len(target)
                    influence[label] = round(max(0.0, mae - baseline_mae), 4)
            except (KeyError, TypeError, ValueError, pickle.UnpicklingError):
                pass
        ordered = sorted(influence.items(), key=lambda item: item[1])
        return {
            "title": {"text": "Peso de las variables en la IA", "left": 12, "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"top": 48, "left": 118, "right": 38, "bottom": 28},
            "xAxis": {"type": "value", "name": "Aumento del error (mg/L)"},
            "yAxis": {"type": "category", "data": [item[0] for item in ordered]},
            "series": [
                {
                    "name": "Peso en la estimacion",
                    "type": "bar",
                    "data": [item[1] for item in ordered],
                    "itemStyle": {"color": "#0d6efd"},
                }
            ],
        }

    @staticmethod
    def _chart(
        title: str,
        series: list[dict[str, object]],
        unit: str,
        focus_from: str | None = None,
    ) -> dict[str, object]:
        data_zoom = [
            {"type": "inside", "xAxisIndex": [0], "filterMode": "none"},
            {"type": "slider", "bottom": 16, "height": 22, "filterMode": "none"},
        ]
        if focus_from:
            for zoom in data_zoom:
                zoom["startValue"] = focus_from
        return {
            "title": {"text": title, "left": 12, "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "cross"}},
            "legend": {"top": 34, "type": "scroll"},
            "toolbox": {
                "right": 16,
                "feature": {
                    "dataZoom": {"yAxisIndex": "none"},
                    "restore": {},
                    "saveAsImage": {},
                },
            },
            "grid": {"top": 78, "left": 64, "right": 36, "bottom": 66},
            "xAxis": {"type": "time"},
            "yAxis": {"type": "value", "name": unit, "scale": True},
            "dataZoom": data_zoom,
            "series": series,
        }

    @staticmethod
    def _series(
        name: str,
        data: list[list[object]],
        color: str,
        dashed: bool = False,
    ) -> dict[str, object]:
        series = {
            "name": name,
            "type": "line",
            "showSymbol": dashed,
            "symbol": "diamond" if dashed else "circle",
            "symbolSize": 12 if dashed else 6,
            "sampling": "lttb",
            "data": data,
            "lineStyle": {"width": 2, "type": "dashed" if dashed else "solid"},
            "itemStyle": {"color": color},
            "z": 5 if dashed else 2,
        }

        if dashed and data:
            series["markPoint"] = {
                "symbol": "diamond",
                "symbolSize": 16,
                "itemStyle": {"color": color},
                "label": {
                    "show": True,
                    "formatter": "Proyeccion",
                    "position": "top",
                    "color": color,
                },
                "data": [{"coord": data[-1]}],
            }
        return series

    @staticmethod
    def _biometric_context(assessment: dict[str, object] | None) -> dict[str, object]:
        interpretation = [
            {"range": "Menor a 1.2", "label": "Excelente"},
            {"range": "1.2 a 1.5", "label": "Muy buena"},
            {"range": "1.5 a 1.8", "label": "Buena"},
            {"range": "1.8 a 2.0", "label": "Regular"},
            {"range": "Mayor a 2.0", "label": "Deficiente"},
        ]
        if not assessment:
            return {
                "available": False,
                "detail": "No hay una biometria real vinculada a esta piscina.",
                "interpretation": interpretation,
            }
        conversion = float(assessment["conversion_alimenticia"])
        if conversion < 1.2:
            label = "Excelente"
        elif conversion < 1.5:
            label = "Muy buena"
        elif conversion < 1.8:
            label = "Buena"
        elif conversion <= 2.0:
            label = "Regular"
        else:
            label = "Deficiente"
        sampled_at = assessment["fecha_muestreo"]
        return {
            "available": True,
            "sampled_at": sampled_at.isoformat() if hasattr(sampled_at, "isoformat") else str(sampled_at),
            "conversion_alimenticia": conversion,
            "conversion_label": label,
            "total_alimento_consumido_kg": float(assessment["total_alimento_consumido_kg"]),
            "biomasa_inicial_kg": float(assessment["bi_kg"]),
            "biomasa_final_kg": float(assessment["bf_kg"]),
            "peso_promedio_g": float(assessment["prom_peso_g"]),
            "longitud_promedio_cm": float(assessment["prom_longitud_cm"]),
            "tasa_crecimiento_g_dia": float(assessment["tasa_crecimiento_g_dia"]),
            "interpretation": interpretation,
            "formula": r"\mathrm{FCA}=\frac{\mathrm{TAC}}{B_f-B_i}",
            "source_document": "Biometria1.docx, seccion 1.1",
        }

    def water_quality_index_for_pond(
        self,
        pond_id: str,
        prepared: dict[str, object] | None = None,
    ) -> dict[str, object]:
        prepared = prepared or self._prepare_dataset(pond_id, False, 4000)
        latest = self._latest_observed(prepared["aligned"], REQUIRED_VARIABLES)
        values = latest["values"]
        result = water_quality_index(
            float(values["water_temperature_c"]),
            float(values["ph"]),
            float(values["dissolved_oxygen_mg_l"]),
            float(values["nitrate_ion"]),
        )
        return {
            **result,
            "model_code": WATER_QUALITY_ICA_MODEL_CODE,
            "pond_id": pond_id,
            "timestamp": latest["timestamp"].isoformat(),
            "traceability": {
                "source_document": "Biometria1.docx, seccion 4.1",
                "source_table": "sismapiscis.parametro_aguas",
                "input_variables": REQUIRED_VARIABLES,
                "generated_data_used": False,
            },
        }

    def biofloc_water_quality(self) -> dict[str, object]:
        return {
            **biofloc_water_quality_readiness(),
            "model_code": BIOFLOC_WATER_QUALITY_MODEL_CODE,
            "traceability": {
                "source_document": "Biometria1.docx, seccion 4.5",
                "generated_data_used": False,
            },
        }

    def _require_persistent_store(self) -> None:
        required = (
            "sync_legacy_data",
            "get_variable_metadata",
            "save_model_forecast",
            "latest_biometric_sample",
        )
        if any(not hasattr(self.store, name) for name in required):
            raise ValueError("real models require the MySQL backend store")

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}-{uuid4()}"

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
