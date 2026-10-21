"""Growth-rate ML using observed biometric history and eligible sensor forecasts.

Training is optional offline sklearn code; serving is portable JSON inference.
Environmental forecasts are used only when paired historical forecast support
exists across studies. Repeated endpoints are not independent observations.
"""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Any

from backend.app.models_engine.ml.supervised_tilapia_growth import number, portable_regression, timestamp

CODE = "TILAPIA_ADAPTIVE_GROWTH_ML"
VERSION = "0.3.0-experimental"
BASE_FEATURES = ("log_weight_g", "log_duration_days", "log_previous_days",
                 "previous_rate_g_day", "previous_relative_rate_day")
HISTORY_FEATURES = ("older_rate_g_day", "rate_change_g_day")
SENSORS = ("temperature_c", "oxygen_mg_l", "ph", "light_lux")


def validated_forecasts(forecasts: dict, issued_at: str) -> dict:
    issue = timestamp(issued_at)
    values = {}
    for key, f in forecasts.items():
        if key not in SENSORS:
            raise ValueError("Unknown sensor forecast: " + key)
        made, trained, until = [timestamp(f[k]) for k in ("issued_at", "trained_until", "valid_until")]
        if trained > made or made > issue:
            raise ValueError("Sensor forecast or training comes from the future")
        if until <= issue or (issue-made).total_seconds() > 86400:
            raise ValueError("Expired or stale sensor forecast")
        if f.get("target_kind") != "next_24h_mean" or not str(f.get("model_version", "")).strip():
            raise ValueError("Versioned next_24h_mean sensor forecast required")
        value = number(f["value"], key)
        lo, hi = {"temperature_c": (0, 50), "oxygen_mg_l": (0, 30),
                  "ph": (0, 14), "light_lux": (0, 200000)}[key]
        if not lo <= value <= hi:
            raise ValueError("Sensor value outside supported units/range: " + key)
        values[key] = value
    return values


def sensor_support(rows: list[dict]) -> dict:
    """Require paired, dated forecasts, not study-level environmental constants."""
    result = {}
    values = {k: {} for k in SENSORS}
    for row in rows:
        forecasts = row.get("sensor_forecasts", {})
        if not forecasts:
            continue
        if not row.get("issued_at"):
            raise ValueError("Training sensor forecasts require their issue date")
        if not row.get("target_at") or timestamp(row["target_at"]) <= timestamp(row["issued_at"]):
            raise ValueError("Training sensor forecasts require a later observed target date")
        for k, v in validated_forecasts(forecasts, row["issued_at"]).items():
            identity = (row["study"], row.get("cohort", ""), row["issued_at"], forecasts[k]["model_version"])
            if identity in values[k] and values[k][identity] != v:
                raise ValueError("Conflicting values for the same forecast origin")
            values[k][identity] = v
    for key, origins in values.items():
        vv = [(identity[0], v) for identity, v in origins.items()]
        varying = sum(len({v for s, v in vv if s == study}) >= 3 for study in {s for s, _ in vv})
        eligible = len(vv) >= 10 and varying >= 2
        result[key] = {"eligible": eligible, "paired_training_examples": len(vv),
                       "count_basis": "distinct_study_cohort_issue_version_origins",
                       "studies_with_within_study_variation": varying,
                       "reason": "eligible" if eligible else "insufficient_paired_forecasts_and_within_study_variation"}
    return result


def vector(row: dict, history: bool, sensor_keys: tuple | list = ()) -> list[float]:
    w = number(row["w"], "weight_g", positive=True)
    days = number(row["days"], "duration_days", positive=True)
    prev = number(row["prev_days"], "previous_days", positive=True)
    rate = number(row["rate"], "previous_rate")
    xx = [math.log(w), math.log(days), math.log(prev), rate, rate/w]
    if history:
        older = row.get("rate2")
        older = float("nan") if older is None else float(older)
        xx += [older, rate-older]
    if sensor_keys:
        forecasts = row.get("sensor_forecasts", {})
        values = validated_forecasts(forecasts, row["issued_at"]) if forecasts else {}
        xx += [values.get(k, float("nan")) for k in sensor_keys]
    if any(math.isinf(v) for v in xx):
        raise ValueError("Infinite history feature")
    return xx


def fit(rows: list[dict], spec: dict):
    import numpy as np
    from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    if len(rows) < 6:
        raise ValueError("At least six observed-endpoint training examples required")
    algorithms = {
        "ridge": lambda: Ridge(alpha=10),
        "rf": lambda: RandomForestRegressor(n_estimators=120, max_depth=3, min_samples_leaf=5,
                                            random_state=20261021, n_jobs=1),
        "extra": lambda: ExtraTreesRegressor(n_estimators=120, max_depth=3, min_samples_leaf=5,
                                             random_state=20261021, n_jobs=1),
        "boost": lambda: GradientBoostingRegressor(n_estimators=60, max_depth=1, min_samples_leaf=5,
            learning_rate=.05, loss="huber", random_state=20261021),
    }
    support = sensor_support(rows)
    sensor_keys = tuple(k for k in SENSORS if support[k]["eligible"])
    features = [vector(r, spec["history"], sensor_keys) for r in rows]
    rates = [number(r["y"], "observed_rate") - (r["rate"] if spec["target"] == "residual" else 0) for r in rows]
    counts = Counter(r["study"] for r in rows)
    weights = np.array([len(rows)/(len(counts)*counts[r["study"]]) for r in rows])
    model = Pipeline([("impute", SimpleImputer(keep_empty_features=True)),
                      ("scale", StandardScaler()), ("reg", algorithms[spec["algorithm"]]())])
    model.fit(features, rates, reg__sample_weight=weights)
    return model, sensor_keys, support


def export(model, rows: list[dict], spec: dict, sensor_keys: tuple, support: dict) -> dict:
    reg = model.named_steps["reg"]
    if not hasattr(reg, "estimators_") or spec["algorithm"] == "boost":
        raise ValueError("Portable serving currently exports only RF/ExtraTrees; other candidates remain offline")
    names = list(BASE_FEATURES) + (list(HISTORY_FEATURES) if spec["history"] else []) + list(sensor_keys)
    features = [vector(r, spec["history"], sensor_keys) for r in rows]
    bounds = []
    for column in zip(*features):
        vv = [v for v in column if math.isfinite(v)]
        bounds.append([min(vv), max(vv)] if vv else None)
    return {"model_code": CODE, "model_version": VERSION, "specification": spec,
        "feature_names": names, "sensor_keys": list(sensor_keys), "sensor_support": support,
        "feature_bounds": bounds, "training_examples": len(rows),
        "training_studies": dict(Counter(r["study"] for r in rows)),
        "impute_values": model.named_steps["impute"].statistics_.tolist(),
        "means": model.named_steps["scale"].mean_.tolist(), "scales": model.named_steps["scale"].scale_.tolist(),
        "regressor": {"kind": "forest", "trees": [{"left": t.tree_.children_left.tolist(),
            "right": t.tree_.children_right.tolist(), "feature": t.tree_.feature.tolist(),
            "threshold": t.tree_.threshold.tolist(), "value": t.tree_.value[:, 0, 0].tolist()} for t in reg.estimators_]},
        "prediction_interval_g": None, "uncertainty_calibrated": False, "production_ready": False,
        "validation_status": "reused_external_development_and_retrospective_local_replay"}


def predict_row(asset: dict, row: dict) -> dict:
    xx = vector(row, asset["specification"]["history"], asset["sensor_keys"])
    scaled = [((asset["impute_values"][i] if math.isnan(v) else v)-asset["means"][i])/asset["scales"][i]
              for i, v in enumerate(xx)]
    rate = portable_regression(asset["regressor"], scaled)
    if asset["specification"]["target"] == "residual":
        rate += row["rate"]
    weight = row["w"] + row["days"]*rate
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError("Nonpositive or unstable weight prediction")
    outside = [name for name, value, bounds in zip(asset["feature_names"], xx, asset["feature_bounds"])
               if bounds is not None and math.isfinite(value) and not bounds[0]-1e-10 <= value <= bounds[1]+1e-10]
    return {"predicted_mean_weight_g": weight, "learned_rate_g_day": rate,
        "recent_trend_weight_g": row["w"]+row["days"]*row["rate"],
        "learned_correction_to_trend_g": row["days"]*(rate-row["rate"]),
        "outside_training_domain": outside, "prediction_interval_g": None,
        "uncertainty_calibrated": False, "production_ready": False}


def predict_history(asset: dict, request: dict) -> dict:
    issue, target_time = timestamp(request["issued_at"]), timestamp(request["target_at"])
    if target_time <= issue:
        raise ValueError("target_at must follow issued_at")
    observations = request["biometries"]
    if not 2 <= len(observations) <= 100:
        raise ValueError("At least two, and at most 100, observed biomet­ries required")
    times = [timestamp(b["observed_at"]) for b in observations]
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Biometries must be strictly chronological with no duplicate date")
    if times[-1] > issue:
        raise ValueError("Future biometry cannot initialize a forecast")
    if asset.get("training_local_cutoff") and timestamp(asset["training_local_cutoff"]) > issue:
        raise ValueError("Artifact includes local labels later than requested issue time")
    for b in observations:
        number(b["mean_weight_g"], "mean_weight_g", positive=True)
        if b.get("available_at") and timestamp(b["available_at"]) > issue:
            raise ValueError("Biometry was not available at issue time")
        if b.get("cohort_id") and b["cohort_id"] != request["cohort_id"]:
            raise ValueError("Cannot mix biomet­ries from different cohorts")
    last, previous = observations[-1], observations[-2]
    prevdays = (times[-1]-times[-2]).total_seconds()/86400
    rate = (last["mean_weight_g"]-previous["mean_weight_g"])/prevdays
    older = None
    if len(times) >= 3:
        older = (previous["mean_weight_g"]-observations[-3]["mean_weight_g"])/((times[-2]-times[-3]).total_seconds()/86400)
    forecasts = request.get("sensor_forecasts", {})
    validated_forecasts(forecasts, request["issued_at"])
    if any(k not in forecasts for k in asset["sensor_keys"]):
        raise ValueError("An actively trained sensor feature is missing its forecast")
    row = {"w": last["mean_weight_g"], "days": (target_time-times[-1]).total_seconds()/86400,
           "prev_days": prevdays, "rate": rate, "rate2": older,
           "sensor_forecasts": forecasts, "issued_at": request["issued_at"]}
    result = predict_row(asset, row)
    result.update({"model_code": CODE, "model_version": VERSION, "cohort_id": request["cohort_id"],
        "issued_at": issue.isoformat(), "target_at": target_time.isoformat(),
        "anchor_observed_at": times[-1].isoformat(), "anchor_observed_weight_g": last["mean_weight_g"],
        "anchor_age_days": (issue-times[-1]).total_seconds()/86400,
        "duration_from_observed_anchor_days": row["days"], "biometries_used": min(3, len(times)),
        "sensor_features_used": asset["sensor_keys"],
        "sensor_models_received": [{"variable": k, "model_version": f["model_version"],
            "used_by_growth_model": k in asset["sensor_keys"]} for k, f in forecasts.items()],
        "sensor_support": asset["sensor_support"],
        "validation_status": asset["validation_status"],
        "source_quality": asset.get("source_quality", "provisional"),
        "forecast_status": "extrapolation_unvalidated" if result["outside_training_domain"] else "experimental_in_domain"})
    return result
