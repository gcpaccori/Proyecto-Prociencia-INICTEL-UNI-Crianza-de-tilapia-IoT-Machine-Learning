"""Authenticated by the private pilot; a current estimate requires verified clocks."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field

from backend.app.models_engine.ml.direct_sensor_growth import CODE,VERSION,predict_direct,timestamp

router=APIRouter()


class SensorHour(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    hour_end:datetime
    available_at:datetime|None=None
    temperature_c:float|None=None
    oxygen_mg_l:float|None=None
    ph:float|None=None
    light_lux:float|None=None


class DirectRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    mode:Literal['forecast','nowcast']
    issued_at:datetime
    target_at:datetime
    anchor_observed_at:datetime
    initial_weight_g:float=Field(gt=0)
    hourly_measurements:list[SensorHour]=Field(min_length=1,max_length=1440)
    inference_mode:Literal['current','retrospective_fit_diagnostic']='current'


def bundle(request:Request):
    a=getattr(request.app.state,'direct_sensor_growth_bundle',None)
    if a is not None:return a
    path=os.environ.get('TILAPIA_DIRECT_GROWTH_BUNDLE')
    if not path:raise HTTPException(503,'Direct sensor growth artifact is not configured')
    try:
        raw=Path(path).read_bytes();a=json.loads(raw)
        if a.get('model_code')!='TILAPIA_DIRECT_SENSOR_GROWTH_BUNDLE' or a.get('model_version')!=VERSION:
            raise ValueError('Unexpected direct model bundle')
        if set(a.get('models',{}))!={'forecast','nowcast'}:raise ValueError('Incomplete direct bundle')
        for key,model in a['models'].items():
            if model['model_code']!=CODE or model['mode']!=key or model['target']!='observed_weight_gain_g':
                raise ValueError('Unexpected direct model semantics')
        a['loaded_sha256']=hashlib.sha256(raw).hexdigest()
    except (OSError,ValueError,KeyError,TypeError) as e:raise HTTPException(503,'Direct sensor growth artifact cannot be loaded') from e
    request.app.state.direct_sensor_growth_bundle=a
    return a


@router.get('/models/tilapia-growth-direct/status')
def direct_status(request:Request):
    a=bundle(request)
    return {'model_code':a['model_code'],'model_version':a['model_version'],
        'artifact_sha256':a.get('loaded_sha256'),'available_at':a['available_at'],
        'production_ready':False,'activated':False,'clock_alignment_verified':False,
        'no_sensor_prediction_submodels':True,'no_prescribed_biological_growth_equation':True,
        'current_inference_status':'blocked_until_server_clock_alignment_verification',
        'models':{key:{k:m[k] for k in ['target','specification','training_endpoint_pairs',
            'distinct_observed_target_dates','sensor_features_used','sensor_support','development_metrics']}
            for key,m in a['models'].items()}}


@router.post('/models/tilapia-growth-direct/predict')
def direct_prediction(body:DirectRequest,request:Request):
    a=bundle(request);data=body.model_dump(mode='json')
    try:
        issue=timestamp(data['issued_at'])
        if body.inference_mode=='current':
            if os.environ.get('TILAPIA_DIRECT_CLOCK_VERIFIED')!='1':
                raise HTTPException(503,'Current direct inference requires verified physical clock alignment')
            if issue<timestamp(a['available_at']):raise ValueError('Artifact was unavailable at issue time')
            if (issue-datetime.now(timezone.utc)).total_seconds()>60:raise ValueError('Cannot issue a current prediction in the future')
        result=predict_direct(a['models'][body.mode],data)
    except (ValueError,OverflowError) as e:raise HTTPException(422,str(e)) from e
    return {**result,'artifact_sha256':a.get('loaded_sha256'),'inference_mode':body.inference_mode,
        'may_reuse_training_labels':body.inference_mode=='retrospective_fit_diagnostic',
        'diagnostic_does_not_validate_unseen_weights':body.inference_mode=='retrospective_fit_diagnostic'}
