"""Inference endpoint for the executed supervised-growth candidate.

Artifacts are trusted server configuration, never user-uploaded pickles.
No model activation or actuator writes are performed by this endpoint.
"""
from __future__ import annotations
import json
import os
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter,HTTPException,Request,Query
from pydantic import BaseModel,ConfigDict,Field

from backend.app.models_engine.ml.supervised_tilapia_growth import (
    CODE,VERSION,predict,predict_with_forecasts,timestamp)

router=APIRouter()


class SensorForecast(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    value:float
    issued_at:datetime
    trained_until:datetime
    valid_until:datetime
    model_version:str=Field(min_length=1)
    target_kind:Literal["next_24h_mean"]="next_24h_mean"
    availability_mode:str="provided_by_client"


class GrowthMLRequest(BaseModel):
    model_config=ConfigDict(extra="forbid",allow_inf_nan=False)
    initial_weight_g:float=Field(gt=0)
    initial_weight_at:datetime
    issued_at:datetime
    target_at:datetime
    model:Literal["selected","environmental"]="selected"
    inference_mode:Literal["current","historical_replay"]="current"
    sensor_forecasts:dict[str,SensorForecast]=Field(default_factory=dict)
    allow_conditional_scenario:bool=False


def assets(request:Request,replay:bool=False):
    state_key="tilapia_growth_replay_models" if replay else "tilapia_growth_models"
    bundle=getattr(request.app.state,state_key,None)
    if bundle is not None:return bundle
    path=os.environ.get("TILAPIA_GROWTH_ML_REPLAY_ARTIFACT" if replay else "TILAPIA_GROWTH_ML_ARTIFACT")
    if not path:raise HTTPException(503,"Supervised growth artifact is not configured")
    try:
        bundle=json.loads(Path(path).read_text())
        if not all(k in bundle for k in ["selected","environmental"]):raise ValueError("Invalid bundle")
    except (OSError,ValueError) as exc:raise HTTPException(503,"Supervised growth artifact cannot be loaded") from exc
    setattr(request.app.state,state_key,bundle)
    return bundle


@router.get("/models/tilapia-growth-ml/status")
def growth_ml_status(request:Request):
    bundle=assets(request)
    return {"model_code":CODE,"model_version":VERSION,"artifact_loaded":True,
            "production_ready":False,"uncertainty_calibrated":False,
            "models":{k:{"specification":v["specification"],"training_intervals":v["training_intervals"],
                         "training_studies":v["training_studies"],"source_quality":v["source_quality"]}
                      for k,v in bundle.items()},
            "evaluation":"historical_replay_not_prospective_validation",
            "warning":"External source conflicts remain unresolved; this is a research candidate"}


@router.post("/models/tilapia-growth-ml/predict")
def growth_ml_predict(body:GrowthMLRequest,request:Request):
    replay=body.inference_mode=="historical_replay"
    asset=assets(request,replay=replay)[body.model]
    payload=body.model_dump(mode="json")
    try:
        issued=timestamp(payload["issued_at"])
        if not replay:
            if asset.get("available_at") and issued<timestamp(asset["available_at"]):
                raise ValueError("Growth artifact was not available at requested issue time")
            if issued>datetime.now(timezone.utc).replace(microsecond=0) and (issued-datetime.now(timezone.utc)).total_seconds()>60:
                raise ValueError("Current forecasts cannot be issued in the future")
            if any(f.availability_mode.startswith("historical") for f in body.sensor_forecasts.values()):
                raise ValueError("Historical sensor replay cannot be presented as a current forecast")
        if asset["specification"]["environmental"] or body.sensor_forecasts:
            result=predict_with_forecasts(asset,payload)
        else:
            start=timestamp(payload["issued_at"]);end=timestamp(payload["target_at"])
            anchor=timestamp(payload["initial_weight_at"])
            if anchor>start:raise ValueError("Future biometric weight cannot initialize a forecast")
            if end<=start:raise ValueError("target_at must follow issued_at")
            result=predict(asset,body.initial_weight_g,(end-anchor).total_seconds()/86400,{})
            result.update({"issued_at":start.isoformat(),"target_at":end.isoformat(),"sensor_models":[],
                           "anchor_weight_at":anchor.isoformat(),"anchor_age_days":(start-anchor).total_seconds()/86400,
                           "conditional_scenario":False,"environment_assumption":"environment_not_used_by_selected_model"})
        result["artifact_role"]=body.model
        result["source_quality"]=asset["source_quality"]
        result["inference_mode"]=body.inference_mode
        return result
    except (ValueError,KeyError,OverflowError) as exc:
        raise HTTPException(422,str(exc)) from exc


def latest_pond_context(pond_id:int,now:datetime) -> dict:
    """Read actual latest biometrics and sensor freshness; no writes or secrets."""
    from sqlalchemy import text
    from backend.app.core.database import engine
    from backend.app.core.config import get_settings
    schema=get_settings().legacy_database_name
    if not schema or not schema.replace("_","").isalnum():raise ValueError("Invalid configured database")
    with engine.connect() as c:
        b=c.execute(text(f"""SELECT b.id,b.fecha_muestreo,b.prom_peso_g,b.cantidad_muestreo
            FROM {schema}.biometrias b JOIN {schema}.campania_etapas ce ON ce.id=b.campania_etapa_id
            WHERE b.deleted_at IS NULL AND ce.deleted_at IS NULL AND ce.piscina_id=:pond
            AND b.fecha_muestreo<=:today AND b.updated_at<=:now
            ORDER BY b.fecha_muestreo DESC,b.id DESC LIMIT 1"""),
            {"pond":pond_id,"today":now.date(),"now":now.replace(tzinfo=None)}).mappings().first()
        last=c.execute(text(f"""SELECT MAX(fecha_medicion) FROM {schema}.parametro_aguas
            WHERE deleted_at IS NULL AND piscina_id=:pond AND fecha_medicion<=:now AND created_at<=:now"""),
            {"pond":pond_id,"now":now.replace(tzinfo=None)}).scalar()
    if b is None:raise ValueError("No available biometric weight for this pond")
    return {"biometry_id":b["id"],"biometry_date":b["fecha_muestreo"].isoformat(),
            "observed_weight_g":float(b["prom_peso_g"]),"sample_n":b["cantidad_muestreo"],
            "latest_sensor_measurement":None if last is None else last.replace(tzinfo=timezone.utc).isoformat()}


@router.get("/ponds/{pond_id}/models/tilapia-growth-ml/forecast")
def growth_ml_for_pond(pond_id:int,request:Request,projection_days:int=Query(default=1,ge=1,le=30)):
    if pond_id<=0:raise HTTPException(422,"Positive pond identifier required")
    now=datetime.now(timezone.utc)
    try:context=latest_pond_context(pond_id,now)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    chosen=assets(request)["selected"]
    if chosen["specification"]["environmental"]:
        raise HTTPException(503,"Selected environmental model requires a live forecast provider")
    body=GrowthMLRequest(initial_weight_g=context["observed_weight_g"],
        initial_weight_at=timestamp(context["biometry_date"]+"T00:00:00+00:00"),
        issued_at=now,target_at=now+timedelta(days=projection_days))
    result=growth_ml_predict(body,request)
    last=context["latest_sensor_measurement"]
    age=None if last is None else (now-timestamp(last)).total_seconds()/3600
    result.update({"pond_id":pond_id,"biometry":context,"projection_days":projection_days,
                   "sensor_age_hours":age,"environmental_branch_ready":age is not None and age<=24,
                   "selection_reason":"Best donor grouped score selected the size/time RF; environmental variant did not improve it",
                   "warning":"Experimental forecast; local evidence is retrospective and donor quality remains provisional"})
    return result
