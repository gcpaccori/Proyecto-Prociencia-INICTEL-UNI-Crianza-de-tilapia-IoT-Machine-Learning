"""Frozen four-way ablation on observed chronological intervals, no pseudo-labels."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from backend.app.models_engine.ml.interval_context_growth import (
    VERSION, VARIANTS, interval_features, fit_interval, predict_interval, standardized)
from research.tilapia_gaussian_20261022.train_gaussian import source


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def build_rows(snapshot):
    hours, qc = source(snapshot)
    # Reuse the same pre-existing water QC, never select thresholds from weights.
    rows = []
    bios = snapshot['biometries']
    for left, right in zip(bios, bios[1:]):
        origin = left['fecha_muestreo'] + 'T00:00:00+00:00'
        target = right['fecha_muestreo'] + 'T00:00:00+00:00'
        data = {'anchor_observed_at': origin, 'target_at': target, 'issued_at': target,
                'initial_weight_g': left['sample_mean_g'],
                'initial_fish_count': left['cantidad_peces_actuales'],
                'entered_feed_total_kg': right['total_alimento_consumido_kg'],
                'hourly_measurements': [h for h in hours if origin < h['hour_end'] <= target]}
        f, q = interval_features(data)
        row = {k: data[k] for k in data if k != 'hourly_measurements'}
        row.update(initial_biometry_id=left['id'], target_biometry_id=right['id'],
                   final_weight_g=right['sample_mean_g'],
                   target_sample_se_g=right['sample_sd_g'] / math.sqrt(right['sample_n']),
                   target_sample_n=right['sample_n'], initial_sample_n=left['sample_n'],
                   initial_sample_se_g=left['sample_sd_g'] / math.sqrt(left['sample_n']),
                   features=f, quality=q)
        rows.append(row)
    return rows, qc


def train_checked(rows, variant):
    a, model = fit_interval(rows, variant)
    # Independent runtime numerical cross-check, including inputs between rows.
    features = [r['features'] for r in rows]
    features += [{n: sum(r['features'][n] for r in rows)/len(rows) for n in VARIANTS[variant]}]
    for f in features:
        mu, sd = model.predict(np.array([standardized(f, VARIANTS[variant])]), return_std=True)
        p = predict_interval(a, f)
        assert abs(p['predicted_final_mean_weight_g'] - mu[0]) < 1e-7
        assert abs(p['conditional_posterior_sd_g'] - sd[0]) < 1e-7
    return a


def main(args):
    args.out.mkdir(parents=True, exist_ok=True)
    raw = args.snapshot.read_bytes()
    protocol = {
        'written_before_fitting_at': datetime.now(timezone.utc).isoformat(),
        'snapshot_sha256': hashlib.sha256(raw).hexdigest(),
        'task': 'retrospective end-of-interval nowcast; not future forecast',
        'label': 'observed final biometric sample mean',
        'variants': {k: list(v) for k, v in VARIANTS.items()},
        'recipe': 'single GP: linear all inputs + Matern32 + white; three learned amplitudes; fixed input scales and length; no hyperparameter search',
        'minimum_training_intervals': 2,
        'evaluation': 'expanding chronological prefix; each label held out; identical eligible rows for all variants; train target <= issue origin',
        'water_eligibility': 'each variable coverage >=70% and latest gap <=48h; incomplete intervals excluded identically from all primary fits/evaluation',
        'feeding': 'entered total at interval endpoint; physical delivery, clock and availability unverified; diagnostic only',
        'excluded_target_derived_inputs': ['FCR', 'final biomass', 'computed growth rate', 'target-dependent feeding schedule'],
        'clock_alignment_verified': False, 'known_development_dates': True,
        'no_interpolated_labels': True, 'external_data_training_rows': 0,
        'external_reason': 'new external means lack aligned interval environment and verified feed; reference only',
        'light_reason': 'insufficient paired interval coverage; no invented history',
        'uncertainty': 'target sample SE included; conditional, not calibrated; initial sample error and interval correlation not modeled',
        'activation_rule': 'do not activate on these already-inspected development labels; requires audited feed/clocks and new independent biological evaluation'}
    dump(args.out / 'protocol.json', protocol)
    snapshot = json.loads(gzip.decompress(raw))
    rows, qc = build_rows(snapshot)
    dump(args.out / 'observed_intervals.json', rows)
    results = []
    for i in range(2, len(rows)):
        r = rows[i]
        train = [p for p in rows[:i] if p['quality']['water_eligible']]
        if not r['quality']['water_eligible'] or len(train) < 2:
            results.append({'target_at': r['target_at'], 'eligible': False,
                            'reason': 'insufficient interval water coverage or excessive latest gap',
                            'quality': r['quality']})
            continue
        assert all(p['target_at'] <= r['anchor_observed_at'] for p in train)
        pred = {name: predict_interval(train_checked(train, name), r['features'])
                for name in VARIANTS}
        prior = rows[i-1]
        trend = (prior['final_weight_g'] - prior['features']['initial_weight_g']) / prior['features']['duration_days']
        results.append({'target_at': r['target_at'], 'anchor_observed_at': r['anchor_observed_at'],
                        'eligible': True, 'actual_weight_g': r['final_weight_g'],
                        'training_targets': [p['target_at'] for p in train],
                        'predictions': pred,
                        'persistence_g': r['features']['initial_weight_g'],
                        'recent_observed_trend_g': r['features']['initial_weight_g'] + trend * r['features']['duration_days'],
                        'quality': r['quality']})
    evaluated = [r for r in results if r['eligible']]
    metrics = {'task': protocol['task'], 'not_blind_validation': True,
               'entered_feed_verified': False, 'n_dates': len(evaluated),
               'dates': [r['target_at'] for r in evaluated],
               'excluded_dates': [r['target_at'] for r in results if not r['eligible']], 'variants': {}}
    for name in VARIANTS:
        errors = [r['predictions'][name]['predicted_final_mean_weight_g'] - r['actual_weight_g'] for r in evaluated]
        metrics['variants'][name] = {'MAE_g': float(np.mean(np.abs(errors))),
                                     'RMSE_g': float(np.sqrt(np.mean(np.square(errors)))),
                                     'bias_g': float(np.mean(errors))}
    for key in ['persistence_g', 'recent_observed_trend_g']:
        metrics[key] = {'MAE_g': float(np.mean([abs(r[key]-r['actual_weight_g']) for r in evaluated]))}
    metrics['sensor_increment_with_feed_MAE_g'] = (metrics['variants']['weight_time_feed']['MAE_g']
                                                   - metrics['variants']['weight_time_feed_water']['MAE_g'])
    metrics['feed_increment_with_water_MAE_g'] = (metrics['variants']['weight_time_water']['MAE_g']
                                                 - metrics['variants']['weight_time_feed_water']['MAE_g'])
    eligible = [r for r in rows if r['quality']['water_eligible']]
    bundle = {'model_code': 'TILAPIA_INTERVAL_CONTEXT_BUNDLE', 'model_version': VERSION,
              'created_at': datetime.now(timezone.utc).isoformat(),
              'cohort_id': snapshot['cohort_id'], 'pond_id': snapshot['pond_id'],
              'snapshot_sha256': protocol['snapshot_sha256'],
              'models': {name: train_checked(eligible, name) for name in VARIANTS},
              'development_metrics': metrics, 'source_quality': qc,
              'n_observed_intervals_total': len(rows), 'n_eligible_training_intervals': len(eligible),
              'excluded_interval_targets': [r['target_at'] for r in rows if not r['quality']['water_eligible']],
              'production_ready': False, 'activated': False, 'clock_alignment_verified': False,
              'entered_feed_verified': False, 'uncertainty_calibrated': False}
    dump(args.out / 'interval_bundle.json', bundle)
    dump(args.out / 'evaluation.json', results)
    dump(args.out / 'metrics.json', metrics)
    with (args.out / 'predictions.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['date','eligible','actual_weight_g',*VARIANTS,'persistence_g','recent_observed_trend_g'])
        w.writeheader()
        for r in results:
            row = {'date': r['target_at'][:10], 'eligible': r['eligible']}
            if r['eligible']:
                row.update(actual_weight_g=r['actual_weight_g'], persistence_g=r['persistence_g'],
                           recent_observed_trend_g=r['recent_observed_trend_g'])
                row.update({name: r['predictions'][name]['predicted_final_mean_weight_g'] for name in VARIANTS})
            w.writerow(row)
    dump(args.out / 'manifest.json', {'snapshot_sha256': protocol['snapshot_sha256'],
         'bundle_sha256': hashlib.sha256((args.out/'interval_bundle.json').read_bytes()).hexdigest(),
         'trainer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'observed_intervals_total': len(rows), 'fitted_intervals': len(eligible),
         'pseudo_labels_used': 0, 'external_reference_rows_used_for_training': 0})
    print(json.dumps(metrics, indent=2), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    main(p.parse_args())
