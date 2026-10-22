"""Read-only inventory of trained sensor candidates. Does not claim live forecasts."""
import hashlib
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from backend.app.models_engine.ml.tilapia_sensor_forecast import RANGES

router=APIRouter()


@router.get('/models/tilapia-sensor-forecast/status')
def sensor_status(request: Request):
    bundle=getattr(request.app.state,'tilapia_sensor_bundle',None)
    if bundle is None:
        path=os.environ.get('TILAPIA_SENSOR_BUNDLE')
        if not path:raise HTTPException(503,'Trained sensor bundle is not configured')
        try:
            raw=Path(path).read_bytes();bundle=json.loads(raw)
            if not isinstance(bundle,dict) or bundle.get('model_code')!='TILAPIA_SENSOR_FORECAST_BUNDLE':
                raise ValueError('Invalid sensor bundle')
            if bundle.get('model_version')!='0.1.0-trained-experimental':raise ValueError('Invalid bundle version')
            required={f'{v}/{h}h' for v in RANGES for h in [1,24]}
            if set(bundle.get('models',{}))!=required:raise ValueError('Incomplete sensor bundle')
            for key,a in bundle['models'].items():
                for name in ['variable','horizon_hours','target_kind','specification','training_windows',
                             'training_last_source_target','validation']:
                    if name not in a:raise ValueError('Incomplete model metadata')
                if a['variable']+'/'+str(a['horizon_hours'])+'h'!=key:raise ValueError('Mismatched model metadata')
            if not bundle.get('created_at') or not bundle.get('snapshot_sha256'):raise ValueError('Missing provenance')
            bundle['loaded_artifact_sha256']=hashlib.sha256(raw).hexdigest()
        except (OSError,ValueError,TypeError) as e:raise HTTPException(503,'Trained sensor bundle cannot be loaded') from e
        request.app.state.tilapia_sensor_bundle=bundle
    return {'model_code':bundle['model_code'],'model_version':bundle['model_version'],
        'created_at':bundle['created_at'],'trained_models':len(bundle['models']),
        'artifact_sha256':bundle.get('loaded_artifact_sha256'),
        'snapshot_sha256':bundle['snapshot_sha256'],'production_ready':False,
        'operational_forecast_status':'blocked_clock_alignment_and_current_input_not_verified',
        'used_by_growth_model':False,'biological_validation_completed':False,
        'models':{key:{k:a[k] for k in ['variable','horizon_hours','target_kind','specification',
            'training_windows','training_last_source_target','validation']} for key,a in bundle['models'].items()}}


@router.get('/models/tilapia-sensor-forecast/stack-status')
def stack_status():
    path=os.environ.get('TILAPIA_STACKED_CANDIDATE')
    if not path:raise HTTPException(503,'Stacked candidate is not configured')
    try:
        raw=Path(path).read_bytes();a=json.loads(raw)
        if not isinstance(a,dict) or a.get('model_code')!='TILAPIA_STACKED_GROWTH_CANDIDATE':
            raise ValueError('Unexpected artifact')
        keys=['model_code','model_version','created_at','observed_training_origins','sensor_features_used',
            'light_feature_used','light_support_at_eligible_origins','validation_status',
            'development_replay_metrics','activation_block_reason']
        result={k:a[k] for k in keys}
    except (OSError,ValueError,KeyError,TypeError) as e:raise HTTPException(503,'Stacked candidate cannot be loaded') from e
    return {**result,'artifact_sha256':hashlib.sha256(raw).hexdigest(),
            'production_ready':False,'activated':False,'clock_alignment_verified':False}
