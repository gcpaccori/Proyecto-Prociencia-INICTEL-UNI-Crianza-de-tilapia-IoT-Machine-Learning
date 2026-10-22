"""Software checks on numerical fixtures; these are not biological validation."""
from datetime import datetime,timedelta,timezone
import hashlib,json,math
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app.models_engine.ml.gaussian_tilapia_growth import (
    SENSORS,features_from_hours,fit_gp,export_gp,predict_gp,standardized)
from backend.app.api.v1.gaussian_tilapia_growth import router

def fixture_rows():
    return [{'date':f'2026-05-{i+1:02d}','weight_g':10.+i*3+math.sin(i),
      'sample_se_g':.8+i*.1,'features':{'elapsed_days':float(i),'temperature_c_mean':27.+.2*i,
      'oxygen_mg_l_p10':3.+.1*i,'ph_mean':7.-.02*i},
      'quality':{'coverage':{k:1. for k in SENSORS}}} for i in range(7)]

def asset(sensor=True):
    rows=fixture_rows();m,n,w=fit_gp(rows,sensor);a=export_gp(m,n,rows,w)
    a['cohort_start_at']='2026-05-01T00:00:00+00:00'
    return a,m

@pytest.mark.parametrize('with_sensors',[True,False])
def test_json_portable_matches_sklearn_at_unseen_inputs(with_sensors):
    a,m=asset(with_sensors);a=json.loads(json.dumps(a))
    for t in [-2.,2.4,9.]:
        f={'elapsed_days':t,'temperature_c_mean':28.,'oxygen_mg_l_p10':3.5,'ph_mean':7.2}
        p=predict_gp(a,f);mu,sd=m.predict(np.array([standardized(f,a['feature_names'])]),return_std=True)
        assert p['predicted_mean_weight_g']==pytest.approx(mu[0],abs=1e-7)
        assert p['posterior_sd_g']==pytest.approx(sd[0],abs=1e-7)
        assert not p['uncertainty_calibrated']
        if t==9.:assert 'elapsed_days' in p['outside_training_domain']

def hours():
    start=datetime(2026,5,1,tzinfo=timezone.utc)-timedelta(days=7)
    return [{'hour_end':(start+timedelta(hours=i)).isoformat(),'temperature_c':28.,'oxygen_mg_l':4.,'ph':7.} for i in range(1,169)]

def test_feature_window_excludes_future_to_query_but_rejects_future_to_issue():
    h=hours();f,q=features_from_hours(h,'2026-05-01T00:00:00+00:00','2026-05-01T00:00:00+00:00')
    assert f['elapsed_days']==0 and q['coverage']['ph']==1.
    assert f['oxygen_mg_l_p10']==4.
    h.append(h[-1]|{'hour_end':'2026-05-01T01:00:00+00:00'})
    with pytest.raises(ValueError,match='Future sensor'):features_from_hours(h,'2026-05-01T00:00:00+00:00','2026-05-01T00:00:00+00:00')
    f,q=features_from_hours(h,'2026-05-01T00:00:00+00:00','2026-05-01T00:00:00+00:00','2026-05-02T00:00:00+00:00')
    assert q['coverage']['ph']==1.

def test_duplicate_hours_naive_times_and_nonfinite_values_rejected():
    h=hours()
    with pytest.raises(ValueError,match='Duplicate'):features_from_hours(h+[h[0]],'2026-05-01T00:00:00+00:00','2026-05-01T00:00:00+00:00')
    with pytest.raises(ValueError,match='Timezone'):features_from_hours(h,'2026-05-01','2026-05-01T00:00:00+00:00')
    h[0]['ph']=float('inf')
    with pytest.raises(ValueError,match='range'):features_from_hours(h,'2026-05-01T00:00:00+00:00','2026-05-01T00:00:00+00:00')

def test_noise_comes_from_measured_mean_precision_not_dense_points():
    a,m=asset();rows=fixture_rows()
    assert a['n_observed_biometries']==7
    assert a['sampling_variances_g2']==pytest.approx([r['sample_se_g']**2 for r in rows])
    assert a['no_synthetic_weight_labels'] and not a['light_used']
    assert np.allclose(m.alpha, np.array(a['sampling_variances_g2'])/a['y_scale_g']**2+1e-10)
    with pytest.raises(ValueError,match='Duplicate observed'):fit_gp(rows+[rows[0]])

def test_sensors_can_affect_posterior_without_another_fitted_model():
    a,_=asset();f=fixture_rows()[3]['features'];before=predict_gp(a,f)
    after=predict_gp(a,f|{'temperature_c_mean':40.,'oxygen_mg_l_p10':1.})
    assert abs(before['predicted_mean_weight_g']-after['predicted_mean_weight_g'])>1e-6
    assert a['no_sensor_prediction_submodels']

def test_api_marks_diagnostic_and_blocks_unverified_live_clock(monkeypatch,tmp_path):
    a,_=asset();b,_=asset(False);bundle={'model_code':'TILAPIA_GAUSSIAN_GROWTH_BUNDLE','model_version':a['model_version'],
      'models':{'with_sensors':a,'time_only':b},'created_at':'2026-10-22T00:00:00+00:00'}
    app=FastAPI();app.state.gaussian_growth_bundle=bundle;app.include_router(router)
    body={'query_at':'2026-05-01T00:00:00+00:00','issued_at':'2026-05-01T00:00:00+00:00',
      'hourly_measurements':hours(),'inference_mode':'retrospective_fit_diagnostic'}
    with TestClient(app) as c:
        bundle['loaded_sha256']='fixture';response=c.post('/models/tilapia-growth-gaussian/predict',json=body)
        assert response.status_code==200
        assert response.json()['may_reuse_training_labels'] and response.json()['estimated_not_measured']
        monkeypatch.delenv('TILAPIA_GAUSSIAN_CLOCK_VERIFIED',raising=False)
        assert c.post('/models/tilapia-growth-gaussian/predict',json=body|{'inference_mode':'current'}).status_code==503
        assert c.post('/models/tilapia-growth-gaussian/predict',json=body|{'sensor_forecasts':{}}).status_code==422
        assert c.post('/models/tilapia-growth-gaussian/predict',json=body|{'hourly_measurements':hours()[:10]}).status_code==422

def test_curve_bound_to_model_and_never_returned_as_measured_labels(monkeypatch,tmp_path):
    app=FastAPI();raw=json.dumps([{'is_daily':True,'estimated_not_measured':True}]).encode()
    path=tmp_path/'curve.json';path.write_bytes(raw)
    app.state.gaussian_growth_bundle={'loaded_sha256':'fixture','curve_sha256':hashlib.sha256(raw).hexdigest()}
    monkeypatch.setenv('TILAPIA_GAUSSIAN_CURVE',str(path));app.include_router(router)
    with TestClient(app) as c:
        r=c.get('/models/tilapia-growth-gaussian/curve');assert r.status_code==200
        assert r.json()['new_training_labels']==0 and r.json()['uses_later_biometries']
        path.write_text('[]');assert c.get('/models/tilapia-growth-gaussian/curve').status_code==503
