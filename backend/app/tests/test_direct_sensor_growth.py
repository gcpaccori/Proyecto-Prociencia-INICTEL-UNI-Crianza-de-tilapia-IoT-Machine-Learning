"""Numerical tests of one-stage sensor->gain ML, not biological evidence."""
import copy
from datetime import datetime,timedelta,timezone

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.direct_sensor_growth import router
from backend.app.models_engine.ml.direct_sensor_growth import (
    CONTEXT,WATER,fit_direct,export_direct,predict_features,predict_direct,summarize_request,names_for_training)


def payload():
    issue=datetime(2025,1,8,tzinfo=timezone.utc)
    return {'mode':'forecast','issued_at':issue.isoformat(),'anchor_observed_at':issue.isoformat(),
        'target_at':(issue+timedelta(days=20)).isoformat(),'initial_weight_g':50.,
        'hourly_measurements':[{'hour_end':(issue-timedelta(hours=i)).isoformat(),
             'temperature_c':26.,'oxygen_mg_l':5.,'ph':7.} for i in reversed(range(168))],
        'inference_mode':'retrospective_fit_diagnostic'}


@pytest.fixture
def fixture_rows():
    rows=[]
    for i in range(12):
        f={'initial_weight_g':30.+i,'duration_days':10.+i}
        for v,base in [('temperature_c',25.),('oxygen_mg_l',4.),('ph',6.5)]:
            f.update({v+'_mean':base+i*.02,v+'_sd':.1+i*.001,v+'_minimum':base-1+i*.02,
                v+'_maximum':base+1+i*.02,v+'_change':i*.01,v+'_coverage':1.})
        f.update(light_lux_mean=None,light_lux_coverage=0.)
        rows.append({'target_date':f'2025-01-{i+1:02d}','features':f,'observed_gain_g':2.+i*.3})
    return rows


@pytest.mark.parametrize('spec',[{'algorithm':'ridge','alpha':10.},{'algorithm':'extra'}])
def test_gain_is_direct_model_output_matching_sklearn(spec,fixture_rows):
    m,names,support=fit_direct(fixture_rows,spec,True)
    a=export_direct(m,names,support,fixture_rows,spec,'forecast')
    for r in fixture_rows:
        expected=float(m.predict([[r['features'].get(k) for k in names]])[0])
        result=predict_features(a,r['features'])
        assert result['predicted_weight_gain_g']==pytest.approx(expected,abs=1e-8)
        assert result['predicted_final_mean_weight_g']==pytest.approx(r['features']['initial_weight_g']+expected)
    assert a['no_sensor_prediction_submodels'] and a['no_prescribed_biological_growth_equation']


def test_changing_sensor_features_can_change_gain_without_changing_context(fixture_rows):
    m,names,support=fit_direct(fixture_rows,{'algorithm':'ridge','alpha':10.},True)
    a=export_direct(m,names,support,fixture_rows,{'algorithm':'ridge','alpha':10.},'forecast')
    first=copy.deepcopy(fixture_rows[0]['features']);changed=copy.deepcopy(first)
    changed['temperature_c_mean']=fixture_rows[-1]['features']['temperature_c_mean']
    assert first['initial_weight_g']==changed['initial_weight_g'] and first['duration_days']==changed['duration_days']
    assert abs(predict_features(a,first)['predicted_weight_gain_g']-predict_features(a,changed)['predicted_weight_gain_g'])>1e-5


def test_missing_light_is_not_an_imputed_learned_light_effect(fixture_rows):
    names,support=names_for_training(fixture_rows,True)
    assert not any(k.startswith('light_lux_') for k in names)
    assert support['light_lux']['eligible'] is False
    repeated=[copy.deepcopy(fixture_rows[0]) for _ in range(100)]
    assert names_for_training(repeated,True)[0]==list(CONTEXT)


def test_forecast_uses_only_pre_origin_hours_and_rejects_future_measurements():
    p=payload();f=summarize_request(p)
    assert f['temperature_c_coverage']==1 and f['temperature_c_mean']==26
    p['hourly_measurements'].append({'hour_end':'2025-01-09T00:00:00+00:00','temperature_c':40})
    with pytest.raises(ValueError,match='Future'):summarize_request(p)


@pytest.mark.parametrize('bad',['duplicate','future_available','naive'])
def test_hourly_data_rejects_ambiguous_availability_or_duplicates(bad):
    p=payload()
    if bad=='duplicate':p['hourly_measurements'].append(p['hourly_measurements'][0].copy())
    if bad=='future_available':p['hourly_measurements'][0]['available_at']='2025-01-09T00:00:00+00:00'
    if bad=='naive':p['issued_at']='2025-01-08T00:00:00'
    with pytest.raises(ValueError):summarize_request(p)


def test_nowcast_cannot_be_mislabeled_as_future_prediction():
    p=payload();p['mode']='nowcast';p['anchor_observed_at']='2025-01-01T00:00:00+00:00'
    with pytest.raises(ValueError,match='Nowcast target'):summarize_request(p)
    p['target_at']=p['issued_at'];assert summarize_request(p)['duration_days']==7


def test_request_with_insufficient_sensor_coverage_is_rejected(fixture_rows):
    m,names,support=fit_direct(fixture_rows,{'algorithm':'ridge','alpha':10.},True)
    a=export_direct(m,names,support,fixture_rows,{'algorithm':'ridge','alpha':10.},'forecast')
    p=payload();p['hourly_measurements']=p['hourly_measurements'][:10]
    with pytest.raises(ValueError,match='Insufficient'):predict_direct(a,p)


def test_api_diagnostic_is_marked_and_live_mode_fails_without_verified_clocks(fixture_rows,monkeypatch):
    m,names,support=fit_direct(fixture_rows,{'algorithm':'ridge','alpha':10.},True)
    a=export_direct(m,names,support,fixture_rows,{'algorithm':'ridge','alpha':10.},'forecast')
    app=FastAPI();app.include_router(router);app.state.direct_sensor_growth_bundle={
        'model_code':'TILAPIA_DIRECT_SENSOR_GROWTH_BUNDLE','model_version':'0.1.0-direct-experimental',
        'available_at':'2025-01-01T00:00:00+00:00','models':{'forecast':a},'loaded_sha256':'numerical_fixture'}
    c=TestClient(app);p=payload();r=c.post('/models/tilapia-growth-direct/predict',json=p)
    assert r.status_code==200 and r.json()['may_reuse_training_labels'] is True
    monkeypatch.delenv('TILAPIA_DIRECT_CLOCK_VERIFIED',raising=False)
    p['inference_mode']='current';assert c.post('/models/tilapia-growth-direct/predict',json=p).status_code==503
    p=payload();p['sensor_forecasts']={}
    assert c.post('/models/tilapia-growth-direct/predict',json=p).status_code==422
