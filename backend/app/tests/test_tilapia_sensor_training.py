"""Numerical software fixtures, not fish data or biological validation."""
import json

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.tilapia_sensor_forecast import router
from backend.app.models_engine.ml.tilapia_sensor_forecast import RANGES,export_sensor_pipeline,predict_sensor
from research.tilapia_full_training_20261022.train_sensors import features,supervised,masks,build


def test_next_24h_target_excludes_present_and_rejects_missing_future_hour():
    s=pd.Series(np.arange(200.),index=pd.date_range('2026-01-01',periods=200,freq='h'))
    x,y,b=supervised(s,24);t=s.index[80]
    assert y.loc[t]==pytest.approx(np.mean(np.arange(81.,105.)))
    s.loc[s.index[90]]=np.nan
    assert t not in supervised(s,24)[0].index


def test_future_readings_cannot_change_current_features():
    s=pd.Series(np.sin(np.arange(300.)/7)+25,index=pd.date_range('2026-01-01',periods=300,freq='h'))
    t=s.index[200];before=features(s).loc[t].copy();s.loc[s.index>t]=999.
    assert np.allclose(before,features(s).loc[t],equal_nan=True)


def test_temporal_purge_removes_training_and_validation_label_overlap():
    i=pd.date_range('2026-01-01',periods=500,freq='h')
    train,val,test,refit,v,t=masks(i,24)
    assert max(i[train]+pd.Timedelta(hours=24))<v
    assert max(i[val]+pd.Timedelta(hours=24))<t
    assert max(i[refit]+pd.Timedelta(hours=24))<min(i[test])
    assert set(i[val]).isdisjoint(i[train])


@pytest.mark.parametrize('spec',[{'algorithm':'ridge','alpha':10.},{'algorithm':'extra','depth':3}])
def test_portable_sensor_prediction_matches_sklearn_after_json_roundtrip(spec):
    x=pd.DataFrame({'a':np.arange(100.),'b':np.sin(np.arange(100.))});x.loc[::9,'b']=np.nan
    y=20+x.a/20
    m=build(spec).fit(x,y);a=json.loads(json.dumps(export_sensor_pipeline(m,x.columns)))
    expected=np.clip(m.predict(x),*RANGES['temperature_c'])
    actual=[predict_sensor(a,row,'temperature_c') for row in x.to_dict('records')]
    assert np.allclose(expected,actual,rtol=1e-9,atol=1e-8)


def test_sensor_status_rejects_partial_bundle_and_keeps_training_distinct_from_growth(tmp_path,monkeypatch):
    app=FastAPI();app.include_router(router);client=TestClient(app)
    p=tmp_path/'sensor.json';monkeypatch.setenv('TILAPIA_SENSOR_BUNDLE',str(p))
    assert client.get('/models/tilapia-sensor-forecast/status').status_code==503
    p.write_text(json.dumps({'model_code':'TILAPIA_SENSOR_FORECAST_BUNDLE','models':{}}))
    assert client.get('/models/tilapia-sensor-forecast/status').status_code==503
    bundle={'model_code':'TILAPIA_SENSOR_FORECAST_BUNDLE','model_version':'0.1.0-trained-experimental',
        'created_at':'2026-01-01T00:00:00+00:00','snapshot_sha256':'numerical_fixture','models':{}}
    for v in RANGES:
        for h in [1,24]:bundle['models'][f'{v}/{h}h']={'variable':v,'horizon_hours':h,'target_kind':'fixture',
            'specification':{},'training_windows':100,'training_last_source_target':'fixture','validation':{}}
    p.write_text(json.dumps(bundle));r=client.get('/models/tilapia-sensor-forecast/status')
    assert r.status_code==200 and r.json()['trained_models']==10
    assert r.json()['used_by_growth_model'] is False and r.json()['production_ready'] is False


def test_sensor_predict_rejects_infinite_features():
    with pytest.raises(ValueError,match='Infinite'):
        predict_sensor({'feature_names':['a']},{'a':float('inf')},'temperature_c')


def test_stack_inventory_never_claims_activation_or_readiness(tmp_path,monkeypatch):
    app=FastAPI();app.include_router(router);client=TestClient(app)
    p=tmp_path/'stack.json';monkeypatch.setenv('TILAPIA_STACKED_CANDIDATE',str(p))
    assert client.get('/models/tilapia-sensor-forecast/stack-status').status_code==503
    fields=['model_version','created_at','observed_training_origins','sensor_features_used',
        'light_feature_used','light_support_at_eligible_origins','validation_status',
        'development_replay_metrics','activation_block_reason']
    a={k:None for k in fields};a.update(model_code='TILAPIA_STACKED_GROWTH_CANDIDATE',
        activated=True,production_ready=True)
    p.write_text(json.dumps(a));r=client.get('/models/tilapia-sensor-forecast/stack-status')
    assert r.status_code==200 and r.json()['activated'] is False and r.json()['production_ready'] is False
