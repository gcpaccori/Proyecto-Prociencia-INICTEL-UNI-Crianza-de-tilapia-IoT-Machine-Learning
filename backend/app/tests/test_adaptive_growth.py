"""Software contract checks. Numerical fixtures are not biometric evidence."""
import copy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.models_engine.ml.adaptive_tilapia_growth import (
    fit, export, predict_history, predict_row, sensor_support, vector)
from backend.app.api.v1.tilapia_growth_adaptive import router


@pytest.fixture
def asset():
    rows = [dict(study='numerical_fixture', cohort='fixture', w=float(w), days=float(days),
        prev_days=7., rate=.2+w/200, rate2=.1+w/250, y=.3+w/220)
        for w in [10,20,30,40,60,80] for days in [7,14,21]]
    spec = {'algorithm':'extra','history':True,'target':'direct'}
    model, keys, support = fit(rows, spec)
    a = export(model, rows, spec, keys, support)
    a['training_local_cutoff']='2025-01-01T00:00:00+00:00'
    for r in [dict(w=18.,days=11.,prev_days=8.,rate=.4,rate2=.3),
              dict(w=95.,days=31.,prev_days=10.,rate=.7,rate2=None)]:
        expected=r['w']+r['days']*float(model.predict([vector(r,True)])[0])
        assert predict_row(a,r)['predicted_mean_weight_g']==pytest.approx(expected,rel=1e-8)
    return a


def payload():
    return {'cohort_id':'fixture','issued_at':'2026-01-22T00:00:00+00:00',
        'target_at':'2026-01-29T00:00:00+00:00',
        'biometries':[{'observed_at':f'2026-01-{day:02d}T00:00:00+00:00','mean_weight_g':w,'cohort_id':'fixture'}
                      for day,w in [(1,20.),(8,23.),(15,27.)]],'sensor_forecasts':{},
        'inference_mode':'historical_replay'}


def sensor():
    return {'value':26.,'issued_at':'2026-01-22T00:00:00+00:00',
        'trained_until':'2026-01-21T00:00:00+00:00','valid_until':'2026-01-23T00:00:00+00:00',
        'model_version':'fixture','target_kind':'next_24h_mean'}


def test_portable_model_keeps_observed_anchor_date_and_learned_correction(asset):
    r=predict_history(asset,payload())
    assert r['anchor_age_days']==7 and r['duration_from_observed_anchor_days']==14
    assert r['anchor_observed_weight_g']==27
    assert r['predicted_mean_weight_g']==pytest.approx(r['recent_trend_weight_g']+r['learned_correction_to_trend_g'])
    assert r['sensor_features_used']==[] and r['prediction_interval_g'] is None


@pytest.mark.parametrize('bad',['future_biometry','duplicate_time','mixed_cohort','future_availability','future_labels','naive_time'])
def test_history_rejects_temporal_and_cohort_leakage(asset,bad):
    p=payload()
    if bad=='future_biometry':p['biometries'][-1]['observed_at']='2026-01-23T00:00:00+00:00'
    if bad=='duplicate_time':p['biometries'][-1]['observed_at']=p['biometries'][-2]['observed_at']
    if bad=='mixed_cohort':p['biometries'][0]['cohort_id']='other'
    if bad=='future_availability':p['biometries'][0]['available_at']='2026-01-23T00:00:00+00:00'
    if bad=='future_labels':asset['training_local_cutoff']='2026-01-23T00:00:00+00:00'
    if bad=='naive_time':p['issued_at']='2026-01-22T00:00:00'
    with pytest.raises(ValueError):predict_history(asset,p)


@pytest.mark.parametrize('bad',['future_forecast','future_training','expired','unversioned','bad_units','unknown'])
def test_forecast_metadata_checked_even_when_sensor_is_not_yet_trained(asset,bad):
    p=payload();f=sensor();key='temperature_c'
    if bad=='future_forecast':f['issued_at']='2026-01-22T01:00:00+00:00'
    if bad=='future_training':f['trained_until']='2026-01-22T01:00:00+00:00'
    if bad=='expired':f['valid_until']='2026-01-21T00:00:00+00:00'
    if bad=='unversioned':f['model_version']=''
    if bad=='bad_units':f['value']=2700
    if bad=='unknown':key='unknown'
    p['sensor_forecasts']={key:f}
    with pytest.raises(ValueError):predict_history(asset,p)


def test_repeated_horizons_do_not_inflate_sensor_training_support():
    row={'study':'a','cohort':'a','issued_at':'2026-01-22T00:00:00+00:00',
         'target_at':'2026-01-29T00:00:00+00:00','sensor_forecasts':{'temperature_c':sensor()}}
    support=sensor_support([copy.deepcopy(row) for _ in range(100)])
    assert support['temperature_c']['paired_training_examples']==1
    assert support['temperature_c']['eligible'] is False


def test_sensor_can_be_eligible_only_with_multiple_studies_and_real_issue_variation():
    rows=[]
    for study in ['a','b']:
        for i in range(5):
            t=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(days=i)
            f=sensor();f.update(value=25.+i,issued_at=t.isoformat(),trained_until=t.isoformat(),valid_until=(t+timedelta(days=1)).isoformat())
            rows.append({'study':study,'cohort':study,'issued_at':t.isoformat(),
                'target_at':(t+timedelta(days=7)).isoformat(),'sensor_forecasts':{'temperature_c':f}})
    assert sensor_support(rows)['temperature_c']['eligible'] is True


def test_api_contract_and_actual_cohort_route(asset,monkeypatch):
    import backend.app.api.v1.tilapia_growth_adaptive as api
    app=FastAPI();app.state.tilapia_adaptive_model=asset;app.include_router(router,prefix='/api/v1')
    client=TestClient(app)
    r=client.post('/api/v1/models/tilapia-growth-adaptive/predict',json=payload())
    assert r.status_code==200 and r.json()['production_ready'] is False
    assert client.get('/api/v1/models/tilapia-growth-adaptive/status').json()['specification']['algorithm']=='extra'
    monkeypatch.setattr(api,'pond_history',lambda pond,now:{'cohort_id':'fixture','biometries':payload()['biometries'],
        'biometry_ids':[1,2,3],'sensor_clock_alignment_verified':False})
    r=client.get('/api/v1/ponds/1/models/tilapia-growth-adaptive/forecast?projection_days=14')
    assert r.status_code==200 and r.json()['source_context']['biometry_ids']==[1,2,3]
    assert r.json()['anchor_observed_weight_g']==27.


@pytest.mark.parametrize('mode',['current','historical_replay'])
def test_api_rejects_unavailable_growth_artifact_even_in_replay(asset,mode):
    p=payload();p['inference_mode']=mode;asset['available_at']='2026-01-23T00:00:00+00:00'
    app=FastAPI();app.state.tilapia_adaptive_model=asset;app.include_router(router)
    r=TestClient(app).post('/models/tilapia-growth-adaptive/predict',json=p)
    assert r.status_code==422
