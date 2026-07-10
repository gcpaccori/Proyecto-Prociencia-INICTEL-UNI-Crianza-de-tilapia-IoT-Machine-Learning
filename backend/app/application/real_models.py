from __future__ import annotations

import base64
import math
import pickle
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
from backend.app.models_engine.ml.preprocessing import (
    align_sensor_series,
    build_latest_svm_od_features,
    build_svm_od_feature_rows,
    hampel_flags,
    interpolate_short_internal_gaps,
    regression_metrics,
)


SVM_MODEL_CODE = "SVM_OD_FORECAST_1H"
OXYGEN_MODEL_CODE = "OXYGEN_STATUS_MODEL"
GROWTH_MODEL_CODE = "TILAPIA_GROWTH_TEMPERATURE"
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
    ) -> dict[str, object]:
        self._require_persistent_store()
        asset = self.store.active_model_asset(SVM_MODEL_CODE)
        if asset is None:
            candidates = self.store.list_model_assets(model_code=SVM_MODEL_CODE)
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
            "status": "ready",
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
            },
        }
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

    def dashboard(self, pond_id: str) -> dict[str, object]:
        prepared = self._prepare_dataset(pond_id, persist_cleaning=False, limit=100000)
        forecast = self.forecast_svm_od(pond_id, prepared)
        status = self.oxygen_status_for_pond(pond_id, prepared, forecast)
        growth = self.tilapia_growth(pond_id, prepared)
        latest_od = self._latest_observed(
            prepared["aligned"],
            ["water_temperature_c", "dissolved_oxygen_mg_l"],
        )
        latest_by_variable = {
            code: self._latest_observed(prepared["aligned"], [code])
            for code in REQUIRED_VARIABLES
        }
        dynamic = {"status": "not_ready", "missing_real_inputs": DYNAMIC_OXYGEN_INPUTS}

        observed_do = [
            [row["timestamp"].isoformat(), float(row["values"]["dissolved_oxygen_mg_l"])]
            for row in prepared["aligned"]
            if row["values"].get("dissolved_oxygen_mg_l") is not None
            and "dissolved_oxygen_mg_l" not in row.get("invalid_variables", set())
        ]
        saturation_history = [
            [row["timestamp"].isoformat(), do_saturation(float(row["values"]["water_temperature_c"]))]
            for row in prepared["aligned"]
            if row["values"].get("water_temperature_c") is not None
            and "water_temperature_c" not in row.get("invalid_variables", set())
        ]
        growth_history = []
        for row in prepared["aligned"]:
            temperature = row["values"].get("water_temperature_c")
            if temperature is None:
                continue
            calculated = tilapia_growth_temperature(float(temperature))
            if calculated["daily_length_gain_mm_day"] is not None:
                growth_history.append(
                    [row["timestamp"].isoformat(), calculated["daily_length_gain_mm_day"]]
                )

        forecast_points = []
        if forecast.get("status") == "ready":
            forecast_points = [
                [forecast["issued_at"], forecast["current_do_mg_l"]],
                [forecast["target_time"], forecast["forecast_do_mg_l"]],
            ]
        warnings = list(prepared["quality"].get("warnings", []))
        if forecast.get("status") != "ready":
            warnings.append("El SVM no tiene un artefacto activo que supere la persistencia.")

        combined_chart = self._chart(
            "Oxigeno disuelto observado y proyeccion SVM a 1 hora",
            [
                self._series("OD observado", observed_do, "#0d6efd"),
                self._series("SVM OD +1h", forecast_points, "#20a854", dashed=True),
            ],
            "mg/L",
        )
        models = [
            {
                "code": SVM_MODEL_CODE,
                "name": "Proyeccion de oxigeno disuelto a 1 hora",
                "message": "SVR temporal entrenado con temperatura, pH, OD e ion nitrato reales.",
                "status": "asset_activo" if forecast.get("status") == "ready" else "sin_datos",
                "current_value": latest_od["values"]["dissolved_oxygen_mg_l"],
                "unit": "mg/L",
                "engine": "FastAPI / scikit-learn",
                "source": "MySQL sismapiscis.parametro_aguas",
                "asset_id": forecast.get("asset_id"),
                "version": forecast.get("asset_version"),
                "metrics": forecast.get("metrics", {}),
                "forecast": [
                    {
                        "timestamp": forecast.get("target_time"),
                        "label": "+1 hora",
                        "value": forecast.get("forecast_do_mg_l"),
                    }
                ] if forecast.get("status") == "ready" else [],
                "chart": combined_chart,
                "traceability": forecast.get("traceability", {}),
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
                ],
                "chart": self._chart(
                    "OD medido frente a saturacion",
                    [
                        self._series("OD observado", observed_do, "#0d6efd"),
                        self._series("OD de saturacion", saturation_history, "#f59f00"),
                    ],
                    "mg/L",
                ),
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
                "forecast": [],
                "chart": self._chart(
                    "Ganancia diaria estimada desde temperatura real",
                    [self._series("Ganancia diaria", growth_history, "#7c3aed")],
                    "mm/dia",
                ),
                "traceability": growth["traceability"],
            },
        ]
        active_asset = self.store.active_model_asset(SVM_MODEL_CODE)
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
            "svm_od_forecast": forecast,
            "oxygen_status": status,
            "tilapia_growth": growth,
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
                "cleaning_run_id": prepared["cleaning_run"].run_id if prepared.get("cleaning_run") else None,
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
                "forecast_points": len(forecast_points),
                "training_rows": {
                    SVM_MODEL_CODE: active_asset.artifact_payload.get("valid_windows", 0)
                    if active_asset else 0
                },
            },
            "lifecycle": {
                "status": "production" if active_asset else "validation_required",
                "models": [
                    {
                        "model_code": SVM_MODEL_CODE,
                        "algorithm": "StandardScaler + SVR RBF",
                        "artifact_path": active_asset.artifact_path if active_asset else None,
                        "training_rows": active_asset.artifact_payload.get("valid_windows")
                        if active_asset else 0,
                    },
                    {"model_code": OXYGEN_MODEL_CODE, "algorithm": "formula", "training_rows": 0},
                    {"model_code": GROWTH_MODEL_CODE, "algorithm": "formula", "training_rows": 0},
                ],
            },
            "combined_chart": combined_chart,
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
            target_variable="dissolved_oxygen_mg_l",
            feature_variables=REQUIRED_VARIABLES,
            cleaning_run_id=cleaning_run_id,
            window_size=7,
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
                    source_variable="dissolved_oxygen_mg_l",
                    unit="mg/L",
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

    def _next_version(self) -> str:
        return f"v{len(self.store.list_model_assets(model_code=SVM_MODEL_CODE)) + 1}"

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
    def _chart(
        title: str,
        series: list[dict[str, object]],
        unit: str,
    ) -> dict[str, object]:
        return {
            "title": {"text": title, "left": 12, "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "axis"},
            "legend": {"top": 34, "type": "scroll"},
            "grid": {"top": 78, "left": 64, "right": 36, "bottom": 58},
            "xAxis": {"type": "time"},
            "yAxis": {"type": "value", "name": unit, "scale": True},
            "dataZoom": [
                {"type": "inside", "xAxisIndex": [0]},
                {"type": "slider", "bottom": 12, "height": 22},
            ],
            "series": series,
        }

    @staticmethod
    def _series(
        name: str,
        data: list[list[object]],
        color: str,
        dashed: bool = False,
    ) -> dict[str, object]:
        return {
            "name": name,
            "type": "line",
            "showSymbol": False,
            "sampling": "lttb",
            "data": data,
            "lineStyle": {"width": 2, "type": "dashed" if dashed else "solid"},
            "itemStyle": {"color": color},
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
