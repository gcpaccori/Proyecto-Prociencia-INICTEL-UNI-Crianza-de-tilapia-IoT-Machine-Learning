"""Supervised interval growth, grouped selection and portable inference.

No synthetic biomass labels. Environmental forecasts are exogenous inputs.
JSON inference does not depend on sklearn or unpickle server-side payloads.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

CODE = "TILAPIA_SUPERVISED_INTERVAL_ML"
VERSION = "0.2.0-experimental"
ENV = ("temperature_c", "oxygen_mg_l", "ph")


def number(value: Any, name: str, *, positive: bool = False) -> float:
    x = float(value)
    if not math.isfinite(x) or (positive and x <= 0):
        raise ValueError(f"Invalid {name}")
    return x


def vector(weight: float, days: float, env: dict, environmental: bool) -> list[float]:
    x = [math.log(number(weight, "initial_weight_g", positive=True)),
         math.log(number(days, "duration_days", positive=True))]
    if environmental:
        values = [float("nan") if env.get(k) is None else number(env[k], k) for k in ENV]
        x += values + [float(math.isnan(v)) for v in values]
    return x


def target(row: dict, kind: str) -> float:
    a = number(row["initial_weight_g"], "initial_weight_g", positive=True)
    b = number(row["final_weight_g"], "final_weight_g", positive=True)
    days = number(row["duration_days"], "duration_days", positive=True)
    return (b-a)/days if kind == "absolute_rate" else math.log(b/a)/days


def endpoint(rate: float, weight: float, days: float, kind: str) -> float:
    value = weight + rate*days if kind == "absolute_rate" else weight*math.exp(min(100, max(-100, rate*days)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Nonpositive or unstable predicted weight")
    return value


def estimator(algorithm: str):
    from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    models = {
        "ridge": lambda: Ridge(alpha=10),
        "random_forest": lambda: RandomForestRegressor(n_estimators=120, max_depth=3,
            min_samples_leaf=3, random_state=20261021, n_jobs=1),
        "extra_trees": lambda: ExtraTreesRegressor(n_estimators=120, max_depth=3,
            min_samples_leaf=3, random_state=20261021, n_jobs=1),
    }
    return Pipeline([("impute", SimpleImputer(keep_empty_features=True)),
                     ("scale", StandardScaler()), ("reg", models[algorithm]())])


def train(rows: list[dict], specification: dict):
    import numpy as np
    if len(rows) < 6:
        raise ValueError("Six observed intervals required")
    x = [vector(r["initial_weight_g"], r["duration_days"], r, specification["environmental"]) for r in rows]
    y = [target(r, specification["target"]) for r in rows]
    studies = {r["study_id"] for r in rows}
    counts = {s: sum(r["study_id"] == s for r in rows) for s in studies}
    weights = np.array([len(rows)/(len(studies)*counts[r["study_id"]]) for r in rows])
    model = estimator(specification["algorithm"])
    model.fit(x, y, reg__sample_weight=weights)
    return model


def select_external(rows: list[dict]) -> dict:
    """Select only on donor data. Complete studies stay in the same fold.

    Both sources currently remain provisional; selection does not approve them.
    Macro MAPE gives each study equal influence. No local test labels accepted.
    """
    import numpy as np
    studies = sorted({r["study_id"] for r in rows})
    if len(studies) < 2 or any(r["study_id"] == "local" for r in rows):
        raise ValueError("External-only grouped selection requires two donor studies")
    results = []
    for environmental in [False, True]:
        for kind in ["absolute_rate", "log_rate"]:
            for algorithm in ["ridge", "random_forest", "extra_trees"]:
                spec = {"algorithm": algorithm, "target": kind, "environmental": environmental}
                predictions, scores = [], []
                for study in studies:
                    fit = [r for r in rows if r["study_id"] != study]
                    test = [r for r in rows if r["study_id"] == study]
                    model = train(fit, spec)
                    errors = []
                    for r in test:
                        x = vector(r["initial_weight_g"], r["duration_days"], r, environmental)
                        rate = float(model.predict([x])[0])
                        try:
                            p = endpoint(rate, r["initial_weight_g"], r["duration_days"], kind)
                            e = abs(p-r["final_weight_g"])/r["final_weight_g"]
                        except ValueError:
                            p, e = None, 1e6
                        errors.append(e)
                        predictions.append({"study_id":study,"interval_id":r["interval_id"],
                                            "observed_g":r["final_weight_g"],"predicted_g":p})
                    scores.append({"study_id":study,"mape_percent":100*float(np.mean(errors))})
                results.append({**spec,"macro_mape_percent":float(np.mean([s["mape_percent"] for s in scores])),
                                "per_study":scores,"predictions":predictions})
    results.sort(key=lambda r: (r["macro_mape_percent"], r["algorithm"], r["target"]))
    env_best = next(r for r in results if r["environmental"])
    return {"selected":results[0],"selected_environmental":env_best,"candidates":results,
            "selection_protocol":"leave_one_complete_study_out_macro_mape",
            "independent_external_studies":len(studies),"external_intervals":len(rows),
            "source_quality":"provisional_source_conflicts_unresolved"}


def export_pipeline(model, spec: dict, rows: list[dict]) -> dict:
    im = model.named_steps["impute"];sc = model.named_steps["scale"];reg=model.named_steps["reg"]
    asset = {"model_code":CODE,"model_version":VERSION,"specification":spec,
             "impute_values":im.statistics_.tolist(),"means":sc.mean_.tolist(),"scales":sc.scale_.tolist(),
             "training_intervals":len(rows),"training_studies":sorted({r["study_id"] for r in rows}),
             "weight_range_g":[min(r["initial_weight_g"] for r in rows),max(r["initial_weight_g"] for r in rows)],
             "duration_range_days":[min(r["duration_days"] for r in rows),max(r["duration_days"] for r in rows)],
             "environment_ranges":{k:[min(v),max(v)] for k in ENV
                                   if (v:=[float(r[k]) for r in rows if r.get(k) is not None])},
             "production_ready":False,"uncertainty_calibrated":False,
             "source_quality":"provisional_source_conflicts_unresolved"}
    if hasattr(reg, "coef_"):
        asset["regressor"]={"kind":"linear","coefficients":reg.coef_.tolist(),"intercept":float(reg.intercept_)}
    else:
        asset["regressor"]={"kind":"forest","trees":[{
            "left":t.tree_.children_left.tolist(),"right":t.tree_.children_right.tolist(),
            "feature":t.tree_.feature.tolist(),"threshold":t.tree_.threshold.tolist(),
            "value":t.tree_.value[:,0,0].tolist()} for t in reg.estimators_]}
    return asset


def portable_regression(reg: dict, x: list[float]) -> float:
    if reg["kind"] == "linear":
        return reg["intercept"] + sum(a*b for a,b in zip(reg["coefficients"],x))
    predictions=[]
    for tree in reg["trees"]:
        node=0
        while tree["left"][node] != -1:
            node=tree["left"][node] if x[tree["feature"][node]] <= tree["threshold"][node] else tree["right"][node]
        predictions.append(tree["value"][node])
    return sum(predictions)/len(predictions)


def predict(asset: dict, initial_weight_g: float, duration_days: float, environment: dict) -> dict:
    spec=asset["specification"]
    x=vector(initial_weight_g,duration_days,environment,spec["environmental"])
    scaled=[((asset["impute_values"][i] if math.isnan(v) else v)-asset["means"][i])/asset["scales"][i] for i,v in enumerate(x)]
    rate=portable_regression(asset["regressor"],scaled)
    p=endpoint(rate,initial_weight_g,duration_days,spec["target"])
    outside=[]
    for key,value,bounds in [("initial_weight_g",initial_weight_g,asset["weight_range_g"]),
                             ("duration_days",duration_days,asset["duration_range_days"])]:
        if value<bounds[0] or value>bounds[1]:outside.append(key)
    if spec["environmental"]:
        for k,bounds in asset["environment_ranges"].items():
            if environment.get(k) is None:outside.append(k+":missing")
            elif not bounds[0]<=environment[k]<=bounds[1]:outside.append(k)
    return {"model_code":CODE,"model_version":VERSION,"predicted_mean_weight_g":p,
            "learned_rate":rate,"rate_target":spec["target"],"environment_used":spec["environmental"],
            "outside_training_domain":outside,"production_ready":False,
            "prediction_interval":None,"uncertainty_calibrated":False}


def timestamp(value: str) -> datetime:
    t=datetime.fromisoformat(value.replace("Z","+00:00"))
    if t.tzinfo is None or t.utcoffset() is None:raise ValueError("Timezone required")
    return t


def predict_with_forecasts(asset: dict, request: dict) -> dict:
    """Consume actual sensor-model outputs with a strict availability contract.

    A held 24h forecast beyond that horizon is a conditional scenario only.
    No data/model payload can claim a later issue/training time than the request.
    """
    issued=timestamp(request["issued_at"]);target_at=timestamp(request["target_at"])
    if target_at<=issued:raise ValueError("target_at must follow issued_at")
    initial_at=timestamp(request["initial_weight_at"])
    if initial_at!=issued:
        raise ValueError("Weight must be anchored at issue time; older biometrics require an observed-history state estimate")
    forecasts=request["sensor_forecasts"]
    env={}; provenance=[];valid_until=[]
    for k in ENV:
        f=forecasts.get(k)
        if f is None:raise ValueError(f"Missing sensor forecast: {k}")
        available=timestamp(f["issued_at"]);trained=timestamp(f["trained_until"])
        end=timestamp(f["valid_until"])
        if trained>available or available>issued:raise ValueError("Future forecast or training information")
        if (issued-available).total_seconds()>24*3600:raise ValueError("Stale sensor forecast")
        if end<=issued:raise ValueError("Sensor forecast expired")
        if f.get("target_kind")!="next_24h_mean":raise ValueError("Expected next_24h_mean forecast")
        if not f.get("model_version"):raise ValueError("Sensor model version required")
        env[k]=number(f["value"],k);valid_until.append(end)
        provenance.append({"variable":k,"model_version":f["model_version"],"trained_until":f["trained_until"]})
    conditional=target_at>min(valid_until)
    if conditional and not request.get("allow_conditional_scenario",False):
        raise ValueError("Growth horizon exceeds sensor forecast support; explicit conditional scenario required")
    out=predict(asset,request["initial_weight_g"],(target_at-issued).total_seconds()/86400,env)
    out.update({"issued_at":issued.isoformat(),"target_at":target_at.isoformat(),
                "sensor_models":provenance,"conditional_scenario":conditional,
                "environment_assumption":"hold_next_24h_forecast_mean" if conditional else "next_24h_forecast_mean",
                "environment":env})
    return out
