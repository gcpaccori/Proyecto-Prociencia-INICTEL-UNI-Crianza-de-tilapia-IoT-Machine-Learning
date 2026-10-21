import copy
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.tilapia_growth_ml import router
from backend.app.models_engine.ml.supervised_tilapia_growth import (
    train,export_pipeline,predict,vector,endpoint,predict_with_forecasts,select_external)


@pytest.fixture
def bundle():
    # Numerical software fixture, not biological evidence or training corpus.
    rows=[{"study_id":"fixture","initial_weight_g":float(w),"final_weight_g":float(w+7),
           "duration_days":7.,"temperature_c":27.,"oxygen_mg_l":5.,"ph":7.}
          for w in [4,8,16,32,64,128]]
    out={}
    for label,env in [("selected",False),("environmental",True)]:
        spec={"algorithm":"random_forest","target":"absolute_rate","environmental":env}
        out[label]=export_pipeline(train(rows,spec),spec,rows)
    return out


def payload():
    f={"value":27.,"issued_at":"2026-06-24T00:00:00+00:00",
       "trained_until":"2026-06-23T23:00:00+00:00","valid_until":"2026-06-25T00:00:00+00:00",
       "model_version":"fixture-v1","target_kind":"next_24h_mean"}
    fs={k:{**f,"value":v} for k,v in [("temperature_c",27.),("oxygen_mg_l",5.),("ph",7.)]}
    return {"initial_weight_g":63.,"initial_weight_at":f["issued_at"],"issued_at":f["issued_at"],
            "target_at":"2026-06-25T00:00:00+00:00","model":"environmental","sensor_forecasts":fs}


def test_portable_forest_is_identical_to_sklearn_on_unseen_values(bundle):
    rows=[{"study_id":"fixture","initial_weight_g":float(w),"final_weight_g":float(w+np.sqrt(w)),"duration_days":7.}
          for w in [4,8,16,32,64,128,256,512]]
    spec={"algorithm":"random_forest","target":"absolute_rate","environmental":False}
    fitted=train(rows,spec);asset=export_pipeline(fitted,spec,rows)
    for w in [5.3,29.7,98.4,300.1]:
        direct=endpoint(float(fitted.predict([vector(w,14,{},False)])[0]),w,14,"absolute_rate")
        assert predict(asset,w,14,{})["predicted_mean_weight_g"]==pytest.approx(direct,rel=1e-7)


@pytest.mark.parametrize("change",["future_forecast","future_training","expired","stale","old_weight","unbacked_horizon"])
def test_temporal_contract_rejects_leaks_and_unsupported_horizons(bundle,change):
    p=payload()
    if change=="future_forecast":p["sensor_forecasts"]["temperature_c"]["issued_at"]="2026-06-24T01:00:00+00:00"
    if change=="future_training":p["sensor_forecasts"]["temperature_c"]["trained_until"]="2026-06-24T01:00:00+00:00"
    if change=="expired":p["sensor_forecasts"]["temperature_c"]["valid_until"]="2026-06-24T00:00:00+00:00"
    if change=="stale":p["sensor_forecasts"]["temperature_c"].update(issued_at="2026-06-22T00:00:00+00:00",trained_until="2026-06-21T00:00:00+00:00")
    if change=="old_weight":p["initial_weight_at"]="2026-06-23T00:00:00+00:00"
    if change=="unbacked_horizon":p["target_at"]="2026-07-01T00:00:00+00:00"
    with pytest.raises(ValueError):predict_with_forecasts(bundle["environmental"],p)


def test_endpoint_accepts_real_contract_and_labels_scenario(bundle):
    app=FastAPI();app.state.tilapia_growth_models=bundle;app.include_router(router,prefix="/api/v1")
    c=TestClient(app);p=payload()
    assert c.get("/api/v1/models/tilapia-growth-ml/status").json()["artifact_loaded"]
    p["target_at"]="2026-07-01T00:00:00+00:00";p["allow_conditional_scenario"]=True
    r=c.post("/api/v1/models/tilapia-growth-ml/predict",json=p)
    assert r.status_code==200
    assert r.json()["conditional_scenario"] is True
    assert r.json()["production_ready"] is False
    assert len(r.json()["sensor_models"])==3


def test_size_only_selected_model_does_not_require_sensor_inputs(bundle):
    app=FastAPI();app.state.tilapia_growth_models=bundle;app.include_router(router)
    p=payload();p["model"]="selected";p["sensor_forecasts"]={}
    r=TestClient(app).post("/models/tilapia-growth-ml/predict",json=p)
    assert r.status_code==200 and r.json()["environment_used"] is False


def test_size_model_advances_from_old_observed_weight_without_relabeling_date(bundle):
    app=FastAPI();app.state.tilapia_growth_models=bundle;app.include_router(router)
    p=payload();p.update(model="selected",sensor_forecasts={},initial_weight_at="2026-06-20T00:00:00+00:00")
    r=TestClient(app).post("/models/tilapia-growth-ml/predict",json=p)
    assert r.status_code==200
    assert r.json()["anchor_age_days"]==4
    assert r.json()["predicted_mean_weight_g"]==pytest.approx(68.)


def test_current_mode_rejects_growth_artifact_from_future(bundle):
    bundle["selected"]["available_at"]="2026-06-25T00:00:00+00:00"
    app=FastAPI();app.state.tilapia_growth_models=bundle;app.include_router(router)
    p=payload();p.update(model="selected",sensor_forecasts={})
    assert TestClient(app).post("/models/tilapia-growth-ml/predict",json=p).status_code==422


def test_corpus_selector_refuses_local_test_labels():
    with pytest.raises(ValueError):select_external([{"study_id":"local"},{"study_id":"external"}])


def test_pond_forecast_reads_anchor_and_reports_missing_live_environment(bundle,monkeypatch):
    import backend.app.api.v1.tilapia_growth_ml as api
    monkeypatch.setattr(api,"latest_pond_context",lambda pond,now:{"biometry_id":7,
        "biometry_date":"2026-10-16","observed_weight_g":150.53,"sample_n":100,
        "latest_sensor_measurement":"2026-10-04T11:39:31+00:00"})
    app=FastAPI();app.state.tilapia_growth_models=bundle;app.include_router(router)
    r=TestClient(app).get("/ponds/1/models/tilapia-growth-ml/forecast?projection_days=1")
    assert r.status_code==200
    assert r.json()["biometry"]["biometry_id"]==7
    assert r.json()["environmental_branch_ready"] is False
    assert r.json()["environment_used"] is False
