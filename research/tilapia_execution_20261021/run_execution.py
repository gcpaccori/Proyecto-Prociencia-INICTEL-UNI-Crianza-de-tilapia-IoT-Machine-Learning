"""Execute donor selection, sensor training, frozen forecasts and fixed evaluation.

Prepare never reads reserved local weights. Evaluate is a single frozen-protocol
historical replay, including rolling-origin refits using only preceding weights.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
import math
import platform
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from backend.app.models_engine.ml.supervised_tilapia_growth import (
    select_external,train,export_pipeline,predict,predict_with_forecasts,ENV)

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
TRAIN_BIO=[{"id":1,"date":"2026-05-09","weight_g":8.1875},
           {"id":2,"date":"2026-06-24","weight_g":63.2805}]
DATES=["2026-07-11","2026-08-07","2026-09-13","2026-09-26","2026-10-16"]
VARS=["temperature_c","oxygen_mg_l","ph","nitrate_native_units"]

def dump(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding="utf-8")
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def clean_json(obj):
    if isinstance(obj,dict):return {k:clean_json(v) for k,v in obj.items()}
    if isinstance(obj,list):return [clean_json(v) for v in obj]
    if isinstance(obj,(float,np.floating)):return float(obj) if math.isfinite(obj) else None
    if isinstance(obj,np.integer):return int(obj)
    return obj

def sensors(path):
    rows=json.loads(gzip.decompress(path.read_bytes()))
    d=pd.DataFrame(rows,columns=["time",*VARS,"source_count","last_ingested"])
    # SQL means cover the entire hour; availability by measurement is hour END.
    d["time"]=pd.to_datetime(d.time)+pd.Timedelta(hours=1)
    d["last_ingested"]=pd.to_datetime(d.last_ingested)
    d=d.set_index("time").sort_index()
    d=d.reindex(pd.date_range(d.index.min(),d.index.max(),freq="h"))
    # Causal stuck detection: only current and previous 7 values, never future.
    flat=(d.oxygen_mg_l.sub(7.22).abs()<1e-8).rolling(8,min_periods=8).sum()==8
    d.loc[flat,"oxygen_mg_l"]=np.nan
    return d

def exposure(d,a,b):
    q=d.loc[(d.index>pd.Timestamp(a))&(d.index<=pd.Timestamp(b))]
    return {k:float(q[k].mean()) if q[k].notna().any() else None for k in ENV}

def donors():
    data=REPO/"research/tilapia_growth_20261021/data"
    rows=[]
    for r in pd.read_csv(data/"kamble_2024_tank_intervals.csv").to_dict("records"):
        rows.append({"study_id":"kamble","interval_id":r["tank_id"],
                     "initial_weight_g":r["initial_weight_g"],"final_weight_g":r["final_weight_g"],
                     "duration_days":r["duration_days"],
                     "temperature_c":r["weekly_summary_mean_temperature_c"],
                     "oxygen_mg_l":r["weekly_summary_mean_do_mg_l"],"ph":r["weekly_summary_mean_ph"],
                     "qc":"provisional_SGR_duration_conflict"})
    piura=pd.read_csv(data/"garcia_2012_observed_weekly_means.csv").to_dict("records")
    for a,b in zip(piura,piura[1:]):
        rows.append({"study_id":"garcia","interval_id":b["date"],
                     "initial_weight_g":a["mean_weight_g"],"final_weight_g":b["mean_weight_g"],
                     "duration_days":(pd.Timestamp(b["date"])-pd.Timestamp(a["date"])).days,
                     **dict.fromkeys(ENV,None),"qc":"sample_count_conflict_temporal_mean_series"})
    return rows

def local_rows(d,bios):
    return [{"study_id":"local","interval_id":str(b["id"]),
             "initial_weight_g":a["weight_g"],"final_weight_g":b["weight_g"],
             "duration_days":(pd.Timestamp(b["date"])-pd.Timestamp(a["date"])).days,
             **exposure(d,a["date"],b["date"]),"qc":"historical_replay"}
            for a,b in zip(bios,bios[1:])]

def feature_frame(d):
    x=pd.DataFrame(index=d.index)
    for k in VARS:
        s=d[k]
        for lag in [0,1,2,6,12,24]:x[k+f"_lag{lag}"]=s.shift(lag)
        x[k+"_mean6"]=s.rolling(6,min_periods=4).mean()
        x[k+"_mean24"]=s.rolling(24,min_periods=12).mean()
        x[k+"_diff6"]=s-s.shift(6)
    x["sin_hour"]=np.sin(2*np.pi*x.index.hour/24)
    x["cos_hour"]=np.cos(2*np.pi*x.index.hour/24)
    return x

def sensor_model(name):
    reg=Ridge(alpha=10) if name=="ridge" else RandomForestRegressor(
        n_estimators=60,max_depth=7,min_samples_leaf=8,random_state=20261021,n_jobs=1)
    return make_pipeline(SimpleImputer(keep_empty_features=True),StandardScaler(),reg)

def sensor_examples(d,x,variable,horizon,cutoff):
    y=d[variable].shift(-1) if horizon==1 else d[variable].rolling(24,min_periods=18).mean().shift(-24)
    end=x.index+pd.Timedelta(hours=horizon)
    mask=(end<=pd.Timestamp(cutoff))&y.notna()&d[variable].notna()
    mask &= d[variable].rolling(24,min_periods=1).count()>=12
    return x.loc[mask],y.loc[mask]

def score(y,p):
    y=np.asarray(y);p=np.asarray(p)
    return {"n":len(y),"mae":float(mean_absolute_error(y,p)),
            "rmse":float(np.sqrt(mean_squared_error(y,p))),
            "r2":float(r2_score(y,p)) if len(y)>2 and np.var(y)>0 else None}

def select_sensors(d,x):
    report={}
    for variable in VARS:
        for horizon in [1,24]:
            xx,yy=sensor_examples(d,x,variable,horizon,"2026-06-24")
            n=len(xx);v0=int(n*.6);t0=int(n*.8)
            if n<100:raise ValueError(f"Insufficient sensor windows {variable}/{horizon}: {n}")
            # Embargo training labels before each validation/test issue time.
            train_mask=xx.index+pd.Timedelta(hours=horizon)<xx.index[v0]
            validation_mask=(xx.index>=xx.index[v0])&(xx.index+pd.Timedelta(hours=horizon)<xx.index[t0])
            test_mask=xx.index>=xx.index[t0]
            candidates={}
            fallback=d[variable] if horizon==1 else d[variable].rolling(24,min_periods=12).mean()
            for name in ["persistence","ridge","random_forest"]:
                if name=="persistence":vp=fallback.reindex(xx.index[validation_mask]).to_numpy()
                else:
                    model=sensor_model(name);model.fit(xx.loc[train_mask],yy.loc[train_mask]);vp=model.predict(xx.loc[validation_mask])
                candidates[name]=score(yy.loc[validation_mask],vp)
            chosen=min(candidates,key=lambda k:candidates[k]["mae"])
            final_train=xx.index+pd.Timedelta(hours=horizon)<xx.index[t0]
            if chosen=="persistence":tp=fallback.reindex(xx.index[test_mask]).to_numpy()
            else:
                model=sensor_model(chosen);model.fit(xx.loc[final_train],yy.loc[final_train]);tp=model.predict(xx.loc[test_mask])
            pp=fallback.reindex(xx.index[test_mask]).to_numpy()
            report[f"{variable}/{horizon}"]={"algorithm":chosen,"validation":candidates,
                "test":score(yy.loc[test_mask],tp),"persistence_test":score(yy.loc[test_mask],pp),
                "test_issue_start":xx.index[t0].isoformat(),"cutoff":"2026-06-24",
                "availability_mode":"measurement_time_historical_replay_ingestion_delayed"}
    return report

def forecast_sensors(d,x,selection,issue):
    issue=pd.Timestamp(issue)
    available=d.loc[(d.index<=issue)&d[VARS].notna().any(axis=1)]
    last=available.index.max()
    if pd.isna(last) or (issue-last).total_seconds()>86400:
        return {"status":"stale_inputs","latest_measurement":str(last),"forecast":None}
    row=x.loc[[last]];out={}
    for variable in VARS:
        for horizon in [1,24]:
            alg=selection[f"{variable}/{horizon}"]["algorithm"]
            xx,yy=sensor_examples(d,x,variable,horizon,issue)
            if alg=="persistence":
                values=d.loc[(d.index>last-pd.Timedelta(hours=24))&(d.index<=last),variable]
                value=d.loc[last,variable] if horizon==1 else values.mean()
            else:
                model=sensor_model(alg);model.fit(xx,yy);value=float(model.predict(row)[0])
            if not pd.notna(value):
                return {"status":"missing_sensor_input","variable":variable,"forecast":None}
            out[f"{variable}/{horizon}"]={"value":float(value),"model_version":f"{alg}-hourly-20261021",
                "issued_at":issue.tz_localize("UTC").isoformat(),
                "trained_until":issue.tz_localize("UTC").isoformat(),
                "valid_until":(issue+pd.Timedelta(hours=horizon)).tz_localize("UTC").isoformat(),
                "target_kind":"next_24h_mean" if horizon==24 else "next_1h_point",
                "availability_mode":"historical_measurement_time_replay"}
    return {"status":"historical_replay","latest_measurement":str(last),"forecast":out,
            "warning":"Ingestion dates do not establish real-time availability; not an archived operational forecast"}

def model_predictions(asset,d,forecast,bio,target_date):
    days=(pd.Timestamp(target_date)-pd.Timestamp(bio["date"])).days
    if forecast["forecast"]:
        env={k:forecast["forecast"][k+"/24"]["value"] for k in ENV}
        request={"initial_weight_g":bio["weight_g"],"initial_weight_at":bio["date"]+"T00:00:00+00:00",
                 "issued_at":bio["date"]+"T00:00:00+00:00","target_at":target_date+"T00:00:00+00:00",
                 "allow_conditional_scenario":True,
                 "sensor_forecasts":{k:forecast["forecast"][k+"/24"] for k in ENV}}
        conditioned=predict_with_forecasts(asset,request)
    else:
        env=dict.fromkeys(ENV,None)
        conditioned=None
    oracle=predict(asset,bio["weight_g"],days,exposure(d,bio["date"],target_date))
    return {"conditional_forecast":conditioned,"observed_environment_reconstruction":oracle}

def prepare(args):
    out=args.out;out.mkdir(parents=True,exist_ok=True)
    d=sensors(args.sensors);x=feature_frame(d);external=donors()
    selection=select_external(external);dump(out/"growth_selection.json",selection)
    sensor_selection=select_sensors(d,x);dump(out/"sensor_selection.json",sensor_selection)
    dataset=external+local_rows(d,TRAIN_BIO)
    artifacts={}
    for label,selected in [("selected",selection["selected"]),("environmental",selection["selected_environmental"])]:
        spec={k:selected[k] for k in ["algorithm","target","environmental"]}
        fitted=train(dataset,spec);asset=export_pipeline(fitted,spec,dataset)
        # Independently verify portable JSON agrees with sklearn on actual rows.
        from backend.app.models_engine.ml.supervised_tilapia_growth import vector,endpoint
        for r in dataset:
            expected=endpoint(float(fitted.predict([vector(r["initial_weight_g"],r["duration_days"],r,spec["environmental"])])[0]),r["initial_weight_g"],r["duration_days"],spec["target"])
            actual=predict(asset,r["initial_weight_g"],r["duration_days"],r)["predicted_mean_weight_g"]
            if abs(expected-actual)>max(1e-6,abs(expected)*1e-7):raise AssertionError("Portable inference mismatch")
        artifacts[label]=asset
    dump(out/"growth_models.json",artifacts)
    forecast=forecast_sensors(d,x,sensor_selection,TRAIN_BIO[-1]["date"])
    dump(out/"anchor_sensor_forecasts.json",forecast)
    predictions=[]
    rate=(TRAIN_BIO[1]["weight_g"]-TRAIN_BIO[0]["weight_g"])/46
    for date in DATES:
        days=(pd.Timestamp(date)-pd.Timestamp(TRAIN_BIO[-1]["date"])).days
        predictions.append({"target_date":date,"anchor_date":TRAIN_BIO[-1]["date"],
            "linear_baseline_g":TRAIN_BIO[-1]["weight_g"]+rate*days,
            "persistence_baseline_g":TRAIN_BIO[-1]["weight_g"],
            "models":{name:model_predictions(a,d,forecast,TRAIN_BIO[-1],date) for name,a in artifacts.items()}})
    dump(out/"frozen_predictions.json",predictions)
    source_code=[Path(__file__),REPO/"backend/app/models_engine/ml/supervised_tilapia_growth.py"]
    protocol={"frozen_at":datetime.now(timezone.utc).isoformat(),"training_local_ids":[1,2],
        "reserved_local_ids":[3,4,5,6,7],"previously_seen_endpoint_id":3,
        "never_previously_read_weights_ids":[4,5,6,7],"fixed_origin":"2026-06-24",
        "evaluation":"fixed_origin_and_prequential_rolling_origin_no_retuning",
        "source_quality":"external_donors_provisional_not_certified",
        "time_convention":"date_at_midnight_UTC_for_ordering_only_actual_sampling_hour_unavailable",
        "availability":"retrospective_measurement_time_replay_not_prospective_archived_forecasts",
        "criteria":{"beats_linear_and_persistence_mae":True,"sensor_age_max_hours":24,
                    "production_requires_approved_donors_and_fresh_inputs":True},
        "code_sha256":{str(p.relative_to(REPO)):digest(p) for p in source_code},
        "input_sensor_sha256":digest(args.sensors),
        "frozen_files_sha256":{p.name:digest(p) for p in out.glob("*.json")},
        "python_version":platform.python_version()}
    dump(out/"frozen_protocol.json",protocol)
    print(json.dumps({"stage":"prepared_before_unblinding","selected":artifacts["selected"]["specification"],
                      "environmental":artifacts["environmental"]["specification"],
                      "external_intervals":len(external),"local_training_intervals":1,
                      "protocol_sha256":digest(out/"frozen_protocol.json")},indent=2))

def evaluate(args):
    out=args.out;protocol=json.loads((out/"frozen_protocol.json").read_text())
    for p,h in protocol["code_sha256"].items():
        if digest(REPO/p)!=h:raise ValueError("Code changed after freeze: "+p)
    for p,h in protocol["frozen_files_sha256"].items():
        if digest(out/p)!=h:raise ValueError("Frozen evidence changed: "+p)
    labels=json.loads(args.labels.read_text())
    bios=[{"id":int(r["id"]),"date":r["date"],"weight_g":float(r["weight_g"])} for r in labels]
    if bios[:2]!=TRAIN_BIO:raise ValueError("Training biometrics changed after freeze")
    if [b["date"] for b in bios[2:]]!=DATES:raise ValueError("Reserved dates changed after freeze")
    fixed=json.loads((out/"frozen_predictions.json").read_text())
    assets=json.loads((out/"growth_models.json").read_text())
    sensor_selection=json.loads((out/"sensor_selection.json").read_text())
    d=sensors(args.sensors);x=feature_frame(d);external=donors();records=[]
    def add(mode,b,anchor,name,value,extra=None):
        records.append({"mode":mode,"target_id":b["id"],"target_date":b["date"],
            "anchor_date":anchor["date"],"model":name,"observed_g":b["weight_g"],"predicted_g":value,
            "absolute_error_g":None if value is None else abs(value-b["weight_g"]),
            "ape_percent":None if value is None else abs(value/b["weight_g"]-1)*100,
            "previously_seen_label":b["id"]==3,"details":extra})
    for j,b in enumerate(bios[2:]):
        row=fixed[j];anchor=bios[1]
        for name in ["linear","persistence"]:add("fixed_origin",b,anchor,name,row[name+"_baseline_g"])
        for name,res in row["models"].items():
            for mode,key in [("scenario","conditional_forecast"),("reconstruction","observed_environment_reconstruction")]:
                p=res[key];add("fixed_origin",b,anchor,name+"_"+mode,None if p is None else p["predicted_mean_weight_g"],p)
        past=bios[:j+2];anchor=past[-1];duration=(pd.Timestamp(b["date"])-pd.Timestamp(anchor["date"])).days
        prev=past[-2];slope=(anchor["weight_g"]-prev["weight_g"])/(pd.Timestamp(anchor["date"])-pd.Timestamp(prev["date"])).days
        add("rolling_origin",b,anchor,"linear",anchor["weight_g"]+slope*duration)
        add("rolling_origin",b,anchor,"persistence",anchor["weight_g"])
        forecast=forecast_sensors(d,x,sensor_selection,anchor["date"])
        dataset=external+local_rows(d,past)
        for name,old_asset in assets.items():
            model=train(dataset,old_asset["specification"])
            asset=export_pipeline(model,old_asset["specification"],dataset)
            result=model_predictions(asset,d,forecast,anchor,b["date"])
            for mode,key in [("scenario","conditional_forecast"),("reconstruction","observed_environment_reconstruction")]:
                p=result[key];add("rolling_origin",b,anchor,name+"_"+mode,None if p is None else p["predicted_mean_weight_g"],p)
    dump(out/"local_evaluation.json",clean_json(records))
    pd.DataFrame([{k:v for k,v in r.items() if k!="details"} for r in records]).to_csv(out/"local_evaluation.csv",index=False)
    metrics=[]
    for mode in ["fixed_origin","rolling_origin"]:
        for novel in [False,True]:
            for name in sorted({r["model"] for r in records}):
                rr=[r for r in records if r["mode"]==mode and r["model"]==name and (not novel or not r["previously_seen_label"])]
                ok=[r for r in rr if r["predicted_g"] is not None]
                metrics.append({"mode":mode,"subset":"four_previously_unread_weights" if novel else "all_five_endpoints",
                    "model":name,"n":len(ok),"missing":len(rr)-len(ok),
                    "MAE_g":float(np.mean([r["absolute_error_g"] for r in ok])) if ok else None,
                    "MAPE_percent":float(np.mean([r["ape_percent"] for r in ok])) if ok else None})
    dump(out/"local_metrics.json",metrics)
    final_dataset=external+local_rows(d,bios)
    final_models={name:export_pipeline(train(final_dataset,a["specification"]),a["specification"],final_dataset) for name,a in assets.items()}
    dump(out/"refitted_candidate_models.json",final_models)
    now=pd.Timestamp("2026-10-21");last=d.loc[d[VARS].notna().any(axis=1)].index.max()
    readiness={"model_fitted":True,"all_reserved_dates_evaluated":True,
        "fresh_sensor_inputs":(now-last).total_seconds()<=86400,"latest_sensor_hour":last.isoformat(),
        "sensor_age_hours":(now-last).total_seconds()/3600,"external_sources_approved":False,
        "prospective_forecasts_verified":False,"production_ready":False,
        "reason":"Provisional donors, delayed historical ingestion and stale live sensors; no local precision certification",
        "no_retuning_after_reveal":True,"frozen_protocol_sha256":digest(out/"frozen_protocol.json")}
    dump(out/"readiness.json",readiness)
    print(json.dumps({"stage":"evaluated_and_refitted","readiness":readiness,
          "metrics_novel":[m for m in metrics if m["subset"]=="four_previously_unread_weights"]},indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("stage",choices=["prepare","evaluate"])
    parser.add_argument("--sensors",type=Path,required=True);parser.add_argument("--labels",type=Path)
    parser.add_argument("--out",type=Path,required=True);args=parser.parse_args()
    (prepare if args.stage=="prepare" else evaluate)(args)
