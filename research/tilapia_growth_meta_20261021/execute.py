"""Select on complete external studies, replay local origins, export the ML API artifact.

All weights were already examined in this project. This is development evidence,
not a new blind validation. Local evaluation scores never enter model selection.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.models_engine.ml.adaptive_tilapia_growth import fit, export, predict_row, vector

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")


def corpus():
    p = pd.read_csv(REPO / 'research/tilapia_growth_20261021/data/garcia_2012_observed_weekly_means.csv')
    series = [('piura', 'piura', p.days_since_first_sample.tolist(), p.mean_weight_g.tolist())]
    ss = pd.read_csv(HERE / 'data/alrashada_2023_weekly_observations.csv')
    for name, q in ss.groupby('source_row_id'):
        q = q.sort_values('elapsed_days')
        series.append(('saudi', name, q.elapsed_days.tolist(), q.weight_g.tolist()))
    return series


def examples(series, max_days=28):
    rows = []
    for study, cohort, times, weights in series:
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError("Source time must be strictly increasing")
        for i in range(1, len(times)-1):
            previous_days = times[i]-times[i-1]
            rate = (weights[i]-weights[i-1])/previous_days
            older = (weights[i-1]-weights[i-2])/(times[i-1]-times[i-2]) if i >= 2 else None
            for j in range(i+1, len(times)):
                duration = times[j]-times[i]
                if duration > max_days:
                    break
                rows.append({'study': study, 'cohort': cohort, 'start': times[i], 'end': times[j],
                    'w': weights[i], 'days': duration, 'prev_days': previous_days, 'rate': rate, 'rate2': older,
                    'y': (weights[j]-weights[i])/duration, 'actual': weights[j],
                    'target_observation_key': f'{study}:{cohort}:{times[j]}'})
    return rows


def point(model, keys, r, spec):
    rate = float(model.predict([vector(r, spec['history'], keys)])[0])
    if spec['target'] == 'residual':
        rate += r['rate']
    return r['w']+r['days']*rate


def score(rows):
    return {'n_prediction_windows': len(rows),
        'MAE_g': float(np.mean([abs(r['prediction']-r['actual']) for r in rows])),
        'MAPE_percent': 100*float(np.mean([abs(r['prediction']-r['actual'])/r['actual'] for r in rows])),
        'recent_trend_MAE_g': float(np.mean([abs(r['trend']-r['actual']) for r in rows])),
        'persistence_MAE_g': float(np.mean([abs(r['initial']-r['actual']) for r in rows]))}


def main(args):
    args.out.mkdir(parents=True, exist_ok=True)
    series = corpus()
    external = examples(series)
    specs = [{'algorithm': a, 'history': h, 'target': t}
             for a in ['ridge', 'rf', 'extra', 'boost'] for h in [False, True] for t in ['residual', 'direct']]
    protocol = {'version': '0.3.0-development', 'candidates': specs,
        'selection': 'minimum study-macro MAE relative to recent trend; complete-study-disjoint folds',
        'external_training_horizons_days': [7, 14, 21, 28], 'local_history_max_observed_interval_days': 60,
        'local_scores_used_for_selection': False, 'previously_examined_external_studies': ['piura', 'saudi'],
        'all_local_biometries_previously_known': True,
        'prior_exploration': 'Algorithm family explored with this same external criterion before final implementation; not preregistered blind evidence',
        'labels': 'Only published or local observed endpoint weights; no daily interpolated or mechanistically generated labels',
        'source_quality': 'Saudi preliminary only; Piura sample-count conflict; Kamble excluded from new training',
        'sensor_rule': 'Dated paired forecasts, >=10 examples, within-study variation in >=2 studies',
        'interpretation': 'Selection/development evidence, not independent prospective certification'}
    dump(args.out / 'development_protocol.json', protocol)
    selection, fold_predictions = [], []
    for spec in specs:
        folds = []
        for held in ['piura', 'saudi']:
            train = [r for r in external if r['study'] != held]
            test = [r for r in external if r['study'] == held]
            assert {r['study'] for r in train}.isdisjoint({r['study'] for r in test})
            model, keys, support = fit(train, spec)
            rows = []
            for r in test:
                rows.append({'study': held, 'cohort': r['cohort'], 'days': r['days'],
                    'start': r['start'], 'actual': r['actual'], 'initial': r['w'],
                    'prediction': point(model, keys, r, spec), 'trend': r['w']+r['days']*r['rate']})
            metrics = score(rows)
            metrics.update(study=held, relative_MAE=metrics['MAE_g']/metrics['recent_trend_MAE_g'])
            folds.append(metrics)
            fold_predictions.extend({**r, 'algorithm': spec['algorithm'], 'history': spec['history'], 'target': spec['target']} for r in rows)
        selection.append({'specification': spec, 'folds': folds,
            'macro_relative_MAE': float(np.mean([r['relative_MAE'] for r in folds]))})
    selection.sort(key=lambda r: (r['macro_relative_MAE'], r['specification']['algorithm'], r['specification']['target']))
    selected = selection[0]['specification']
    dump(args.out / 'selection.json', selection)
    pd.DataFrame(fold_predictions).to_csv(args.out / 'all_candidate_external_predictions.csv', index=False)
    chosen = [r for r in fold_predictions if all(r[k] == v for k, v in selected.items())]
    pd.DataFrame(chosen).to_csv(args.out / 'selected_external_predictions.csv', index=False)
    by_horizon = []
    for study in ['piura', 'saudi']:
        for days in [7, 14, 21, 28]:
            q = [r for r in chosen if r['study'] == study and r['days'] == days]
            by_horizon.append({'study': study, 'horizon_days': days, **score(q)})
    dump(args.out / 'external_by_horizon.json', by_horizon)

    # Temporal diagnostic within each source: retain all data available by the cut.
    # No overlapping future labels in fit. These labels already informed selection.
    cuts = {study: times[int((len(times)-1)*.6)] for study, _, times, _ in series}
    train = [r for r in external if r['end'] <= cuts[r['study']]]
    tests = [r for r in external if r['start'] >= cuts[r['study']]]
    model, keys, support = fit(train, selected)
    diagnostic = [{'study': r['study'], 'cohort': r['cohort'], 'start': r['start'], 'end': r['end'],
        'days': r['days'], 'initial': r['w'], 'actual': r['actual'], 'prediction': point(model, keys, r, selected),
        'trend': r['w']+r['rate']*r['days']} for r in tests]
    pd.DataFrame(diagnostic).to_csv(args.out / 'temporal_development_predictions.csv', index=False)
    dump(args.out / 'temporal_development_metrics.json',
         [{'study': s, **score([r for r in diagnostic if r['study'] == s])} for s in ['piura', 'saudi']])

    bios = json.loads(args.biometrics.read_text())
    dates = [pd.Timestamp(b['date']) for b in bios]
    times = [(d-dates[0]).days for d in dates]
    weights = [float(b['weight_g']) for b in bios]
    records = []
    for j in range(2, len(bios)):
        local_train = examples([('local', 'pond1_campaign2', times[:j], weights[:j])], max_days=60)
        assert all(r['end'] <= times[j-1] for r in local_train)
        model, keys, support = fit(external+local_train, selected)
        a = export(model, external+local_train, selected, keys, support)
        r = {'w': weights[j-1], 'days': times[j]-times[j-1], 'prev_days': times[j-1]-times[j-2],
            'rate': (weights[j-1]-weights[j-2])/(times[j-1]-times[j-2]),
            'rate2': (weights[j-2]-weights[j-3])/(times[j-2]-times[j-3]) if j >= 3 else None}
        p = predict_row(a, r)
        direct = point(model, keys, r, selected)
        if abs(p['predicted_mean_weight_g']-direct) > 1e-7:
            raise AssertionError('Portable JSON inference differs from fitted sklearn')
        records.append({'target_id': bios[j]['id'], 'target_date': bios[j]['date'],
            'anchor_date': bios[j-1]['date'], 'initial': weights[j-1], 'actual': weights[j],
            'prediction': p['predicted_mean_weight_g'], 'trend': r['w']+r['days']*r['rate'],
            'n_local_training_examples': len(local_train),
            'maximum_local_training_target_date': bios[j-1]['date'],
            'outside_training_domain': p['outside_training_domain']})
    dump(args.out / 'local_predictions.json', records)
    pd.DataFrame(records).to_csv(args.out / 'local_predictions.csv', index=False)
    local_metrics = {'all_five_dates': score(records), 'four_dates_excluding_previously_known_B3': score(records[1:]),
        'interpretation': 'Retrospective development replay; all local labels already known in this project; ingestion-time availability not established for historical dates'}
    dump(args.out / 'local_metrics.json', local_metrics)

    final_rows = external+examples([('local', 'pond1_campaign2', times, weights)], max_days=60)
    model, keys, support = fit(final_rows, selected)
    final = export(model, final_rows, selected, keys, support)
    final.update(training_local_cutoff=bios[-1]['date']+'T00:00:00-05:00',
        source_quality='Saudi preliminary and Piura published means; Piura sample-size conflict remains; local corrected labels verified against details previously',
        development_external_selection=selection[0], development_local_metrics=local_metrics,
        available_at=datetime.now(timezone.utc).isoformat(),
        observational_support={'external_published_weight_values': 169, 'local_weight_means': len(bios),
            'new_training_uses_kamble': False, 'new_training_uses_silva': False,
            'training_examples_are_correlated': True, 'local_independent_growth_intervals': len(bios)-1})
    for r in final_rows[::max(1, len(final_rows)//25)]:
        assert abs(predict_row(final, r)['predicted_mean_weight_g']-point(model, keys, r, selected)) < 1e-7
    dump(args.out / 'serving_model.json', final)
    dump(args.out / 'delivery_manifest.json', {
        'model_version': final['model_version'], 'selected': selected,
        'inputs_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.biometrics,
            HERE/'data/alrashada_2023_weekly_observations.csv',
            REPO/'research/tilapia_growth_20261021/data/garcia_2012_observed_weekly_means.csv']},
        'artifact_sha256': hashlib.sha256((args.out/'serving_model.json').read_bytes()).hexdigest(),
        'source_sha256': {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
            Path(__file__), REPO/'backend/app/models_engine/ml/adaptive_tilapia_growth.py']},
        'production_ready': False})
    print(json.dumps({'selected': selected, 'external_development': selection[0],
        'local_development': local_metrics, 'training_examples': len(final_rows), 'sensor_features': list(keys)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--biometrics', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    main(parser.parse_args())
