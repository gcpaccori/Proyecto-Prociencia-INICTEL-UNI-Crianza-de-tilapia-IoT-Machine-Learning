"""Train an explicitly small-sample stacked ML candidate, without activating it.

Upstream Ridge recipes are fixed before local comparisons and reconstructed using
only sensor labels whose stored measurement end is <= the biometric origin.
The meta-regressor learns a correction to the external/history ML growth rate.
Four eligible local origins are still four origins, never expanded into daily
synthetic weights. Unverified clock alignment limits the whole experiment.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.models_engine.ml.adaptive_tilapia_growth import fit,export,predict_row
from backend.app.models_engine.ml.tilapia_sensor_forecast import RANGES,export_sensor_pipeline
from backend.app.models_engine.ml.supervised_tilapia_growth import portable_regression
from research.tilapia_growth_meta_20261021.execute import corpus,examples
from research.tilapia_full_training_20261022.train_sensors import (
    load_source,supervised,features,build,dump,clean)

SENSOR_KEYS=['temperature_c','oxygen_mg_l','ph']
RECIPE={'algorithm':'ridge','alpha':10.}
META_RECIPE={'algorithm':'ridge','alpha':100.}
GROWTH_RECIPE={'algorithm':'extra','history':True,'target':'direct'}
NAMES=['base_growth_rate_g_day','previous_growth_rate_g_day','log_weight_g','log_duration_days',
       *[v+'_forecast_24h' for v in SENSOR_KEYS]]


def main(args):
    args.out.mkdir(parents=True,exist_ok=True)
    dump(args.out/'protocol.json',{'written_before_fit':datetime.now(timezone.utc).isoformat(),
        'fixed_sensor_recipe':RECIPE,'fixed_meta_recipe':META_RECIPE,'fixed_growth_recipe':GROWTH_RECIPE,
        'features':NAMES,'local_target':'observed daily growth rate minus base ML predicted daily growth rate',
        'training_labels':'observed endpoint means only; no interpolated daily weights',
        'history_gate':'current source hour observed and >=18 of preceding 24 hours per water variable',
        'temporal_sensor_rule':'upstream future-mean target end <= biometric origin; later sensor targets excluded',
        'meta_replay':'start after two prior eligible observed growth targets; fixed recipes, no test tuning',
        'availability_warning':'historical stored-measurement-clock reconstruction; physical alignment and realtime receipt availability not verified',
        'previously_examined_data':True,'not_blind_validation':True,
        'light':'exclude if no complete causal history at eligible biometric origins; never impute an entirely unobserved effect',
        'promotion':'candidate remains offline; too few origins for reliable integrated growth validation'})
    raw=args.snapshot.read_bytes();snapshot=json.loads(gzip.decompress(raw))
    series,qc=load_source(snapshot);bios=snapshot['biometries']
    dates=[pd.Timestamp(b['date']) for b in bios];times=[(d-dates[0]).days for d in dates]
    weights=[float(b['weight_g']) for b in bios];external=examples(corpus())
    audit=[];rows=[];held=[]
    datasets={v:supervised(series[v],24) for v in SENSOR_KEYS}
    feature_frames={v:features(series[v]) for v in SENSOR_KEYS}
    for i in range(1,len(bios)-1):
        origin=dates[i];target=dates[i+1];days=(target-origin).days
        a={'origin_biometry_id':bios[i]['id'],'target_biometry_id':bios[i+1]['id'],
           'origin':origin,'target':target,'water_histories':{},'light_history_hours':0}
        light=series['light_lux'];prior=light.loc[(light.index<=origin)&(light.index>origin-pd.Timedelta(hours=24))]
        a['light_history_hours']=int(prior.notna().sum());valid=True
        for v in SENSOR_KEYS:
            s=series[v];q=s.loc[(s.index<=origin)&(s.index>origin-pd.Timedelta(hours=24))]
            current=origin in s.index and pd.notna(s.loc[origin]);n=int(q.notna().sum())
            a['water_histories'][v]={'observed_prior24_hours':n,'current_hour_observed':bool(current)}
            if n<18 or not current:valid=False
        a['eligible_water_stack']=valid;a['eligible_complete_light_stack']=valid and a['light_history_hours']>=18
        audit.append(a)
        if not valid:continue
        forecasts={};trained_limits={}
        for v in SENSOR_KEYS:
            x,y,b=datasets[v];end=x.index+pd.Timedelta(hours=24);mask=end<=origin
            if int(mask.sum())<30:raise ValueError('Insufficient preceding sensor training windows')
            model=build(RECIPE).fit(x.loc[mask],y.loc[mask])
            forecasts[v]=float(np.clip(model.predict(feature_frames[v].loc[[origin]])[0],*RANGES[v]))
            trained_limits[v]=(x.index[mask]+pd.Timedelta(hours=24)).max()
            assert trained_limits[v]<=origin
        local=examples([('local','pond1_campaign2',times[:i+1],weights[:i+1])],max_days=60)
        base,keys,support=fit(external+local,GROWTH_RECIPE)
        asset=export(base,external+local,GROWTH_RECIPE,keys,support)
        prev=times[i]-times[i-1];rate=(weights[i]-weights[i-1])/prev
        older=(weights[i-1]-weights[i-2])/(times[i-1]-times[i-2]) if i>=2 else None
        p=predict_row(asset,{'w':weights[i],'days':days,'prev_days':prev,'rate':rate,'rate2':older})
        xx=[p['learned_rate_g_day'],rate,np.log(weights[i]),np.log(days),*[forecasts[v] for v in SENSOR_KEYS]]
        actual_rate=(weights[i+1]-weights[i])/days
        row={'origin':origin,'target':target,'initial_g':weights[i],'actual_g':weights[i+1],'days':days,
            'base_prediction_g':p['predicted_mean_weight_g'],'base_rate':p['learned_rate_g_day'],
            'recent_trend_g':weights[i]+days*rate,'features':xx,
            'target_residual_rate':actual_rate-p['learned_rate_g_day'],
            'sensor_forecasts_reconstructed':forecasts,'sensor_training_last_target':trained_limits,
            'meta_training_target_cutoff':dates[i]}
        if len(rows)>=2:
            # Prior target must already be observed by the current origin.
            assert all(r['target']<=origin for r in rows)
            x0=pd.DataFrame([r['features'] for r in rows],columns=NAMES);y0=[r['target_residual_rate'] for r in rows]
            meta=build(META_RECIPE).fit(x0,y0)
            correction=float(meta.predict(pd.DataFrame([xx],columns=NAMES))[0])
            prediction=weights[i]+days*(p['learned_rate_g_day']+correction)
            held.append({'target':target,'actual_g':weights[i+1],'prediction_g':prediction,
                'base_prediction_g':p['predicted_mean_weight_g'],'trend_g':row['recent_trend_g'],
                'prior_meta_origins':len(rows)})
        rows.append(row)
    dump(args.out/'origin_audit.json',audit);dump(args.out/'training_rows.json',rows)
    if len(rows)<3:raise ValueError('Too few eligible observed origins even for a small experimental meta-regressor')
    xx=pd.DataFrame([r['features'] for r in rows],columns=NAMES);yy=[r['target_residual_rate'] for r in rows]
    final=build(META_RECIPE).fit(xx,yy);meta_asset=export_sensor_pipeline(final,NAMES)
    # This target is a signed residual, so do not clamp it as a physical sensor.
    for row,want in zip(xx.to_dict('records'),final.predict(xx)):
        z=[(row[k]-meta_asset['means'][j])/meta_asset['scales'][j] for j,k in enumerate(NAMES)]
        assert abs(portable_regression(meta_asset['regressor'],z)-want)<1e-9
    upstream={}
    for v,(x,y,b) in datasets.items():
        model=build(RECIPE).fit(x,y);upstream[v]=export_sensor_pipeline(model,x.columns)
        upstream[v].update(horizon_hours=24,training_windows=len(x),
            training_last_source_target=(x.index+pd.Timedelta(hours=24)).max())
    result={'model_code':'TILAPIA_STACKED_GROWTH_CANDIDATE','model_version':'0.1.0-small-sample-experimental',
        'created_at':datetime.now(timezone.utc).isoformat(),'snapshot_sha256':hashlib.sha256(raw).hexdigest(),
        'meta_pipeline':meta_asset,'meta_recipe':META_RECIPE,'upstream_sensor_recipe':RECIPE,
        'base_growth_recipe':GROWTH_RECIPE,'upstream_sensor_models':upstream,
        'base_growth_artifact_sha256':hashlib.sha256(args.growth_artifact.read_bytes()).hexdigest(),
        'observed_training_origins':len(rows),'sensor_features_used':SENSOR_KEYS,'light_feature_used':False,
        'light_support_at_eligible_origins':sum(a['eligible_complete_light_stack'] for a in audit),
        'clock_alignment_verified':False,'validation_status':'previously_known_single_cohort_retrospective_reconstruction',
        'not_a_prospective_archived_forecast':True,'production_ready':False,'activated':False,
        'purpose':'offline candidate that actually learns a residual from causal-reconstructed sensor model outputs; sample too small to promote'}
    metrics={'n_replayed_target_dates':len(held),'dates':held,
        'MAE_g':float(np.mean([abs(r['prediction_g']-r['actual_g']) for r in held])) if held else None,
        'base_ML_MAE_g_same_dates':float(np.mean([abs(r['base_prediction_g']-r['actual_g']) for r in held])) if held else None,
        'trend_MAE_g_same_dates':float(np.mean([abs(r['trend_g']-r['actual_g']) for r in held])) if held else None,
        'reliable_generalization_established':False}
    result['development_replay_metrics']=metrics
    result['activation_block_reason']='four_observed_origins_two_replay_dates_unverified_clock_no_light_support'
    dump(args.out/'stacked_candidate.json',result);dump(args.out/'replay_metrics.json',metrics)
    dump(args.out/'manifest.json',{'completed_at':datetime.now(timezone.utc).isoformat(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'artifact_sha256':hashlib.sha256((args.out/'stacked_candidate.json').read_bytes()).hexdigest(),
        'trained':True,'observed_training_origins':len(rows),'activated':False})
    print(json.dumps({'trained':True,'origins':len(rows),'light_support':result['light_support_at_eligible_origins'],
        'replay':clean(metrics)},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--growth-artifact',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
