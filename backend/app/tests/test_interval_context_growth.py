"""Numerical, chronology and input provenance checks, not biological validation."""
from datetime import datetime, timedelta, timezone
import json

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1.interval_context_growth import router
from backend.app.models_engine.ml.interval_context_growth import (
    VARIANTS, interval_features, fit_interval, predict_interval, standardized)
from research.tilapia_interval_context_20261022.train_interval import build_rows


def data():
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=3)
    hours = [{'hour_end': (start+timedelta(hours=i)).isoformat(),
              'temperature_c': 28., 'oxygen_mg_l': 4., 'ph': 7.}
             for i in range(1, 73)]
    return dict(anchor_observed_at=start.isoformat(), target_at=end.isoformat(), issued_at=end.isoformat(),
                initial_weight_g=30., initial_fish_count=100., entered_feed_total_kg=.3,
                hourly_measurements=hours)


def rows():
    out = []
    for i in range(5):
        d = data(); d['initial_weight_g'] += i*3; d['entered_feed_total_kg'] += i*.05
        f, q = interval_features(d)
        out.append(dict(anchor_observed_at=f'2026-05-{i*3+1:02d}T00:00:00+00:00',
                        target_at=f'2026-05-{i*3+4:02d}T00:00:00+00:00',
                        final_weight_g=34.+i*3.2, target_sample_se_g=1.+i*.1,
                        features=f, quality=q))
    return out


@pytest.mark.parametrize('variant', list(VARIANTS))
def test_portable_posterior_matches_independent_sklearn_runtime(variant):
    a, m = fit_interval(rows(), variant)
    a = json.loads(json.dumps(a))
    f = rows()[2]['features'] | {'initial_weight_g': 41., 'temperature_c_mean': 29.1}
    mu, sd = m.predict(np.array([standardized(f, VARIANTS[variant])]), return_std=True)
    p = predict_interval(a, f)
    assert p['predicted_final_mean_weight_g'] == pytest.approx(mu[0], abs=1e-7)
    assert p['conditional_posterior_sd_g'] == pytest.approx(sd[0], abs=1e-7)


def test_interval_features_do_not_average_entire_campaign_or_consume_future():
    d = data(); before = dict(d['hourly_measurements'][0], hour_end='2026-04-30T00:00:00+00:00', temperature_c=1.)
    f, q = interval_features(d | {'hourly_measurements': [before]+d['hourly_measurements']})
    assert f['temperature_c_mean'] == 28.
    assert f['entered_feed_g_per_initial_fish_day'] == 1.
    assert q['coverage']['temperature_c'] == 1.
    future = dict(before, hour_end='2026-05-05T00:00:00+00:00')
    with pytest.raises(ValueError, match='Future sensor'):
        interval_features(d | {'hourly_measurements': d['hourly_measurements']+[future]})
    with pytest.raises(ValueError, match='target <= issue'):
        interval_features(d | {'issued_at': d['anchor_observed_at']})


def test_no_water_imputation_and_late_receipts_are_visible():
    d = data(); h = d['hourly_measurements'][:20]
    h[0] = h[0] | {'available_at': '2026-06-01T00:00:00+00:00'}
    f, q = interval_features(d | {'hourly_measurements': h})
    assert not q['water_eligible']
    assert q['coverage']['ph'] == pytest.approx(20/72)
    assert q['late_received_hour_rows'] == 1
    with pytest.raises(ValueError, match='Duplicate'):
        interval_features(d | {'hourly_measurements': h+[h[0]]})
    with pytest.raises(ValueError, match='range'):
        interval_features(d | {'hourly_measurements': [h[0] | {'ph': float('inf')}]})


def test_target_derived_fields_cannot_change_features_and_cannot_enter_api():
    d = data(); f, _ = interval_features(d)
    other, _ = interval_features(d | {'final_weight_g': 999., 'FCR': .1, 'final_biomass': 999.})
    assert f == other
    app = FastAPI(); app.include_router(router)
    with TestClient(app) as c:
        assert c.post('/models/tilapia-growth-interval-context/predict', json=d | {'FCR': 1.}).status_code == 422


def test_builder_target_weight_cannot_leak_into_its_own_features():
    bios = [dict(id=i, fecha_muestreo=f'2026-05-{i*3+1:02d}', sample_mean_g=20.+i*4,
                 sample_sd_g=2., sample_n=20, cantidad_peces_actuales=100., total_alimento_consumido_kg=.3)
            for i in range(3)]
    water = [[h['hour_end'],28.,4.,7.,1,'2026-05-01 00:00:00'] for h in data()['hourly_measurements']]
    s = dict(biometries=bios, water_hour_columns=['hour_end','temperature_c','oxygen_mg_l','ph','n','last_received'], water_hourly=water)
    first, _ = build_rows(s)
    bios[1] = bios[1] | {'sample_mean_g': 900.}
    changed, _ = build_rows(s | {'biometries': bios})
    assert changed[0]['features'] == first[0]['features']
    assert changed[0]['final_weight_g'] == 900.
    assert changed[1]['features']['initial_weight_g'] == 900.


def test_api_blocks_live_unverified_feed_and_rejects_sparse_diagnostic():
    models = {name: fit_interval(rows(), name)[0] for name in VARIANTS}
    app = FastAPI(); app.include_router(router)
    app.state.interval_context_bundle = dict(models=models, loaded_sha256='fixture',
        clock_alignment_verified=False, entered_feed_verified=False, production_ready=False)
    with TestClient(app) as c:
        url = '/models/tilapia-growth-interval-context/predict'
        d = data()
        assert c.post(url, json=d).status_code == 503
        r = c.post(url, json=d | {'inference_mode': 'retrospective_fit_diagnostic'})
        assert r.status_code == 200
        assert r.json()['estimated_not_measured'] and not r.json()['entered_feed_verified']
        assert r.json()['diagnostic_does_not_validate_unseen_weights']
        assert c.post(url, json=d | {'inference_mode': 'retrospective_fit_diagnostic',
            'hourly_measurements': d['hourly_measurements'][:10]}).status_code == 422
        assert c.post(url, json=d | {'feed_verified': True}).status_code == 422
