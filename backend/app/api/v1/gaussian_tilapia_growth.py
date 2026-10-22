"""Experimental GP reconstruction, served behind the authenticated private pilot."""
from datetime import datetime,timezone
import hashlib,json,os
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from backend.app.api.v1.direct_sensor_growth import SensorHour
from backend.app.models_engine.ml.gaussian_tilapia_growth import VERSION,instant,predict_history

router=APIRouter()

class GaussianRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    issued_at:datetime
    query_at:datetime
    hourly_measurements:list[SensorHour]=Field(min_length=1,max_length=10000)
    inference_mode:Literal['current','retrospective_fit_diagnostic']='current'

def bundle(request):
    a=getattr(request.app.state,'gaussian_growth_bundle',None)
    if a is not None:return a
    try:
        raw=Path(os.environ['TILAPIA_GAUSSIAN_BUNDLE']).read_bytes();a=json.loads(raw)
        if a['model_code']!='TILAPIA_GAUSSIAN_GROWTH_BUNDLE' or a['model_version']!=VERSION:raise ValueError('Version')
        if set(a['models'])!={'with_sensors','time_only'}:raise ValueError('Incomplete GP bundle')
        for m in a['models'].values():
            if m['target']!='observed_mean_weight_g' or not m['no_synthetic_weight_labels']:raise ValueError('Semantics')
        a['loaded_sha256']=hashlib.sha256(raw).hexdigest()
    except (OSError,KeyError,ValueError,TypeError) as e:raise HTTPException(503,'Gaussian artifact unavailable') from e
    request.app.state.gaussian_growth_bundle=a;return a

@router.get('/models/tilapia-growth-gaussian/status')
def gaussian_status(request:Request):
    a=bundle(request)
    return {k:a[k] for k in ['model_code','model_version','cohort_id','pond_id','created_at','development_metrics']}|{
      'artifact_sha256':a['loaded_sha256'],'production_ready':False,'activated':False,'uncertainty_calibrated':False,
      'clock_alignment_verified':False,'current_inference_status':'blocked_until_physical_clock_alignment_verified',
      'models':{k:{q:m[q] for q in ['feature_names','n_observed_biometries','training_dates','sensor_features_used','light_used','no_synthetic_weight_labels']} for k,m in a['models'].items()}}

@router.get('/models/tilapia-growth-gaussian/curve')
def gaussian_curve(request:Request):
    a=bundle(request)
    try:
        raw=Path(os.environ['TILAPIA_GAUSSIAN_CURVE']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=a['curve_sha256']:raise ValueError('Curve does not belong to loaded model')
        curve=json.loads(raw)
    except (OSError,KeyError,ValueError) as e:raise HTTPException(503,'Gaussian curve unavailable') from e
    return {'artifact_sha256':a['loaded_sha256'],'curve_kind':'full_fit_retrospective_reconstruction',
      'estimated_not_measured':True,'uses_later_biometries':True,'new_training_labels':0,
      'uncertainty_calibrated':False,'points':[r for r in curve if r['is_daily']]}

@router.post('/models/tilapia-growth-gaussian/predict')
def gaussian_predict(body:GaussianRequest,request:Request):
    a=bundle(request);data=body.model_dump(mode='json')
    try:
        issue=instant(data['issued_at']);query=instant(data['query_at'])
        if body.inference_mode=='current':
            if os.environ.get('TILAPIA_GAUSSIAN_CLOCK_VERIFIED')!='1':
                raise HTTPException(503,'Current Gaussian inference requires verified physical sensor clocks')
            if query!=issue:raise ValueError('Current mode estimates weight at issue time')
            if issue<instant(a['created_at']):raise ValueError('Artifact unavailable at issue time')
            if (issue-datetime.now(timezone.utc)).total_seconds()>60:raise ValueError('Future issue time')
        result=predict_history(a['models']['with_sensors'],data['hourly_measurements'],data['query_at'],data['issued_at'])
        quality=result['source_quality']
        if body.inference_mode=='current' and (quality['late_received_hour_rows'] or any(v is None or v>48 for v in quality['latest_gap_hours'].values())):
            raise ValueError('Current GP needs timely available sensor hours and gaps <=48h')
    except (ValueError,KeyError,OverflowError) as e:raise HTTPException(422,str(e)) from e
    return result|{'artifact_sha256':a['loaded_sha256'],'inference_mode':body.inference_mode,
      'may_reuse_training_labels':body.inference_mode=='retrospective_fit_diagnostic',
      'diagnostic_does_not_validate_unseen_weights':True,'estimated_not_measured':True}
