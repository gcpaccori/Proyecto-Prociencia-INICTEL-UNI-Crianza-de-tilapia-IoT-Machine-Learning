"""Private experimental interval GP. Entered feed is not certified delivery."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.v1.direct_sensor_growth import SensorHour
from backend.app.models_engine.ml.gaussian_tilapia_growth import instant
from backend.app.models_engine.ml.interval_context_growth import (
    VERSION, CODE, VARIANTS, interval_features, predict_interval)

router = APIRouter()


class IntervalContextRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    anchor_observed_at: datetime
    target_at: datetime
    issued_at: datetime
    initial_weight_g: float = Field(gt=0)
    initial_fish_count: float = Field(gt=0)
    entered_feed_total_kg: float = Field(ge=0)
    hourly_measurements: list[SensorHour] = Field(min_length=1, max_length=10000)
    inference_mode: Literal['current', 'retrospective_fit_diagnostic'] = 'current'


def bundle(request):
    asset = getattr(request.app.state, 'interval_context_bundle', None)
    if asset is not None:
        return asset
    try:
        raw = Path(os.environ['TILAPIA_INTERVAL_CONTEXT_BUNDLE']).read_bytes()
        asset = json.loads(raw)
        if asset['model_code'] != 'TILAPIA_INTERVAL_CONTEXT_BUNDLE' or asset['model_version'] != VERSION:
            raise ValueError('Version')
        if set(asset['models']) != set(VARIANTS):
            raise ValueError('Incomplete interval comparison')
        for name, model in asset['models'].items():
            if (model['model_code'] != CODE or model['target'] != 'observed_final_mean_weight_g'
                    or model['feature_names'] != list(VARIANTS[name])
                    or not model['no_synthetic_weight_labels']):
                raise ValueError('Semantics')
        asset['loaded_sha256'] = hashlib.sha256(raw).hexdigest()
    except (OSError, KeyError, ValueError, TypeError) as e:
        raise HTTPException(503, 'Interval context artifact unavailable') from e
    request.app.state.interval_context_bundle = asset
    return asset


@router.get('/models/tilapia-growth-interval-context/status')
def status(request: Request):
    a = bundle(request)
    return {k: a[k] for k in ['model_code', 'model_version', 'created_at', 'pond_id', 'cohort_id',
            'development_metrics', 'n_observed_intervals_total', 'n_eligible_training_intervals',
            'excluded_interval_targets']} | {
        'artifact_sha256': a['loaded_sha256'], 'production_ready': False, 'activated': False,
        'clock_alignment_verified': a['clock_alignment_verified'],
        'entered_feed_verified': a['entered_feed_verified'], 'uncertainty_calibrated': False,
        'current_inference_status': 'blocked_until_audited_inputs_and_new_biological_validation',
        'no_synthetic_weight_labels': True, 'no_sensor_prediction_submodels': True,
        'models': {name: {k: m[k] for k in ['feature_names', 'n_observed_intervals',
                    'training_targets', 'entered_feed_used', 'light_used']}
                   for name, m in a['models'].items()}}


@router.post('/models/tilapia-growth-interval-context/predict')
def prediction(body: IntervalContextRequest, request: Request):
    a = bundle(request)
    data = body.model_dump(mode='json')
    if body.inference_mode == 'current':
        # A request field or environment toggle cannot certify historic feed.
        # A newly audited artifact is required to change these provenance flags.
        if not (a['clock_alignment_verified'] and a['entered_feed_verified'] and a['production_ready']):
            raise HTTPException(503, 'Current inference requires audited feed, clocks and independent biological validation')
    try:
        issue = instant(data['issued_at'])
        if body.inference_mode == 'current':
            if instant(data['target_at']) != issue:
                raise ValueError('Current nowcast target must equal issue time')
            if issue < instant(a['created_at']):
                raise ValueError('Artifact unavailable at issue time')
            if (issue-datetime.now(timezone.utc)).total_seconds() > 60:
                raise ValueError('Future issue time')
            if any(not r.get('available_at') for r in data['hourly_measurements']):
                raise ValueError('Current inference needs receipt timestamps')
        f, q = interval_features(data)
        if not q['water_eligible']:
            raise ValueError('Insufficient interval water coverage or latest gap >48h')
        if body.inference_mode == 'current' and q['late_received_hour_rows']:
            raise ValueError('Sensor observations unavailable at issue time')
        result = predict_interval(a['models']['weight_time_feed_water'], f)
    except (ValueError, KeyError, OverflowError) as e:
        raise HTTPException(422, str(e)) from e
    return result | {'artifact_sha256': a['loaded_sha256'], 'input_features': f,
                     'source_quality': q, 'inference_mode': body.inference_mode,
                     'task': 'end_of_interval_nowcast', 'entered_feed_verified': False,
                     'may_reuse_training_labels': body.inference_mode == 'retrospective_fit_diagnostic',
                     'diagnostic_does_not_validate_unseen_weights': True}
