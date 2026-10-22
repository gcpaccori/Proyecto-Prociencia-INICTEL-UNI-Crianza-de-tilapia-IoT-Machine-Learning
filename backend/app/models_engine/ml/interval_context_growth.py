"""One learned GP maps an observed interval and its management to final weight.

No interpolated weight labels, sensor forecast submodels, or biological growth
equations. Entered feed totals are an explicitly unverified diagnostic input.
"""
from __future__ import annotations

import math
import statistics
from datetime import timedelta

from backend.app.models_engine.ml.gaussian_tilapia_growth import instant, percentile

VERSION = '0.1.0-interval-context-experimental'
CODE = 'TILAPIA_INTERVAL_CONTEXT_GP'
WATER = ('temperature_c', 'oxygen_mg_l', 'ph')
LIMITS = {'temperature_c': (0., 50.), 'oxygen_mg_l': (0., 30.), 'ph': (0., 14.)}
BASE = ('initial_weight_g', 'duration_days')
FEED = ('entered_feed_g_per_initial_fish_day',)
ENVIRONMENT = ('temperature_c_mean', 'oxygen_mg_l_p10', 'ph_mean')
VARIANTS = {
    'weight_time': BASE,
    'weight_time_water': BASE + ENVIRONMENT,
    'weight_time_feed': BASE + FEED,
    'weight_time_feed_water': BASE + FEED + ENVIRONMENT,
}
CENTERS = dict(initial_weight_g=0., duration_days=0.,
               entered_feed_g_per_initial_fish_day=0.,
               temperature_c_mean=28., oxygen_mg_l_p10=4., ph_mean=7.)
SCALES = dict(initial_weight_g=100., duration_days=30.,
              entered_feed_g_per_initial_fish_day=1.,
              temperature_c_mean=5., oxygen_mg_l_p10=2., ph_mean=1.)
MIN_COVERAGE = .70
MAX_GAP_HOURS = 48.


def positive(value, name, allow_zero=False):
    v = float(value)
    if not math.isfinite(v) or (v < 0 if allow_zero else v <= 0):
        raise ValueError('Invalid ' + name)
    return v


def interval_features(data):
    """Features stop at target; input origin is an actual measured biometry.

    Late receipts are counted, never silently represented as timely history.
    Statistical evaluation may inspect stored measurement order as a diagnostic;
    operational callers must additionally require verified clocks/availability.
    """
    start = instant(data['anchor_observed_at'])
    end = instant(data['target_at'])
    issue = instant(data['issued_at'])
    if not start < end <= issue:
        raise ValueError('Require anchor < target <= issue; future environment is unavailable')
    if any(t.minute or t.second or t.microsecond for t in (start, end)):
        raise ValueError('Anchor and target must be complete hour boundaries')
    days = (end - start).total_seconds() / 86400
    expected = int((end - start).total_seconds() / 3600)
    f = {'initial_weight_g': positive(data['initial_weight_g'], 'initial weight'),
         'duration_days': days}
    feed = data.get('entered_feed_total_kg')
    if feed is not None:
        n = positive(data['initial_fish_count'], 'initial fish count')
        f[FEED[0]] = positive(feed, 'entered feed', True) * 1000 / n / days
    samples = {k: [] for k in WATER}
    last = {k: None for k in WATER}
    seen = set()
    late = 0
    observed_light = 0
    for h in data.get('hourly_measurements', []):
        t = instant(h['hour_end'])
        if t.minute or t.second or t.microsecond:
            raise ValueError('Complete hour ends required')
        if t in seen:
            raise ValueError('Duplicate hour')
        seen.add(t)
        if t > issue:
            raise ValueError('Future sensor observation')
        if not start < t <= end:
            continue
        if h.get('available_at') and instant(h['available_at']) > issue:
            late += 1
        if h.get('light_lux') is not None:
            positive(h['light_lux'], 'light lux', True)
            observed_light += 1
        for k in WATER:
            if h.get(k) is None:
                continue
            v = float(h[k])
            lo, hi = LIMITS[k]
            if not math.isfinite(v) or not lo <= v <= hi:
                raise ValueError('Unsupported sensor range/unit: ' + k)
            samples[k].append(v)
            last[k] = t if last[k] is None else max(last[k], t)
    coverage = {k: len(v) / expected for k, v in samples.items()}
    gaps = {k: (end - t).total_seconds() / 3600 if t else None for k, t in last.items()}
    if any(v > 1. + 1e-10 for v in coverage.values()):
        raise ValueError('More hours than interval permits')
    if all(samples.values()):
        f.update(temperature_c_mean=statistics.mean(samples['temperature_c']),
                 oxygen_mg_l_p10=percentile(samples['oxygen_mg_l']),
                 ph_mean=statistics.mean(samples['ph']))
    eligible = all(v >= MIN_COVERAGE for v in coverage.values()) and all(
        v is not None and v <= MAX_GAP_HOURS for v in gaps.values())
    return f, {'coverage': coverage, 'latest_gap_hours': gaps,
               'expected_hours': expected, 'late_received_hour_rows': late,
               'water_eligible': eligible, 'minimum_coverage': MIN_COVERAGE,
               'maximum_latest_gap_hours': MAX_GAP_HOURS,
               'light_observed_hours': observed_light, 'light_used': False,
               'entered_feed_verified': False,
               'physical_clock_alignment_verified': False}


def standardized(features, names):
    out = []
    for n in names:
        v = float(features[n])
        if not math.isfinite(v):
            raise ValueError('Non-finite interval feature')
        out.append((v - CENTERS[n]) / SCALES[n])
    return out


def fit_interval(rows, variant):
    import warnings
    import numpy as np
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import ConstantKernel, DotProduct, Matern, WhiteKernel

    names = VARIANTS[variant]
    if len(rows) < 2:
        raise ValueError('At least two observed intervals required')
    if len({r['target_at'] for r in rows}) != len(rows):
        raise ValueError('Duplicate observed interval target')
    if any(not r['quality']['water_eligible'] for r in rows):
        raise ValueError('All comparison variants require the same eligible intervals')
    x = np.array([standardized(r['features'], names) for r in rows])
    y = np.array([r['final_weight_g'] for r in rows])
    scale = float(np.std(y)) or 1.
    alpha = np.array([r['target_sample_se_g'] ** 2 for r in rows]) / scale ** 2 + 1e-10
    # Frozen specification, three amplitude parameters only. No searches on test
    # outcomes, no imputation, and no physiological rate equation in the mean.
    kernel = (ConstantKernel(1., (1e-3, 100.)) * DotProduct(1., sigma_0_bounds='fixed')
              + ConstantKernel(.3, (1e-3, 10.)) * Matern(1., length_scale_bounds='fixed', nu=1.5)
              + WhiteKernel(.01, (1e-4, .5)))
    model = GaussianProcessRegressor(kernel=kernel, alpha=alpha, normalize_y=True,
                                     n_restarts_optimizer=0, random_state=20261022)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        model.fit(x, y)
    k = model.kernel_
    asset = {
        'model_code': CODE, 'model_version': VERSION, 'variant': variant,
        'target': 'observed_final_mean_weight_g', 'feature_names': list(names),
        'centers': {n: CENTERS[n] for n in names}, 'scales': {n: SCALES[n] for n in names},
        'kernel': {'kind': 'linear_all_features_plus_matern32_plus_white',
                   'linear_amplitude': float(k.k1.k1.k1.constant_value),
                   'smooth_amplitude': float(k.k1.k2.k1.constant_value),
                   'white_variance': float(k.k2.noise_level)},
        'x_train': model.X_train_.tolist(), 'alpha_vector': model.alpha_.tolist(),
        'cholesky_L': model.L_.tolist(), 'y_mean_g': float(model._y_train_mean),
        'y_scale_g': float(model._y_train_std),
        'training_targets': [r['target_at'] for r in rows],
        'training_origins': [r['anchor_observed_at'] for r in rows],
        'n_observed_intervals': len(rows),
        'sampling_variances_g2': [r['target_sample_se_g'] ** 2 for r in rows],
        'feature_bounds': {n: [min(r['features'][n] for r in rows),
                               max(r['features'][n] for r in rows)] for n in names},
        'entered_feed_used': FEED[0] in names, 'light_used': False,
        'no_synthetic_weight_labels': True, 'no_sensor_prediction_submodels': True,
        'no_prescribed_biological_growth_equation': True,
        'uncertainty_calibrated': False, 'production_ready': False, 'activated': False,
        'uncertainty_scope': 'conditional GP final mean; initial-weight error, correlated samples and hyperparameter uncertainty not propagated',
        'fit_warnings': [str(w.message) for w in caught]}
    return asset, model


def kernel(a, b, k):
    d = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))
    z = math.sqrt(3.) * d
    return (k['linear_amplitude'] * (1. + sum(x * y for x, y in zip(a, b)))
            + k['smooth_amplitude'] * (1. + z) * math.exp(-z))


def predict_interval(asset, features):
    x = []
    for n in asset['feature_names']:
        v = float(features[n])
        if not math.isfinite(v):
            raise ValueError('Non-finite interval feature')
        x.append((v - asset['centers'][n]) / asset['scales'][n])
    k = asset['kernel']
    cross = [kernel(x, z, k) for z in asset['x_train']]
    mu = asset['y_mean_g'] + asset['y_scale_g'] * sum(a * b for a, b in zip(cross, asset['alpha_vector']))
    solved = []
    for i, row in enumerate(asset['cholesky_L']):
        solved.append((cross[i] - sum(row[j] * solved[j] for j in range(i))) / row[i])
    variance = kernel(x, x, k) - sum(v ** 2 for v in solved)
    if variance < -1e-7:
        raise ValueError('Invalid covariance')
    sd = asset['y_scale_g'] * math.sqrt(max(0., variance) + k['white_variance'])
    return {'predicted_final_mean_weight_g': mu, 'conditional_posterior_sd_g': sd,
            'conditional_95_lower_g': mu - 1.96 * sd,
            'conditional_95_upper_g': mu + 1.96 * sd,
            'outside_training_domain': [n for n in asset['feature_names'] if not
                asset['feature_bounds'][n][0] <= float(features[n]) <= asset['feature_bounds'][n][1]],
            'estimated_not_measured': True, 'uncertainty_calibrated': False,
            'production_ready': False, 'activated': False}
