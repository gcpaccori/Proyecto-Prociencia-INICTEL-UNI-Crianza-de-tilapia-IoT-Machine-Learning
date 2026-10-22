"""Direct sensor->observed gain ML, two explicitly different time semantics.

Forecast uses only the seven days before a fresh biometric origin.
Nowcast uses observed sensors between the anchor and the target/issue, estimating
growth already experienced. Neither calls a sensor model or a growth formula.
All endpoint labels and many sensor data were previously examined: development.
"""
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.models_engine.ml.direct_sensor_growth import (
    WATER,OPTIONAL,MIN_COVERAGE,CONTEXT,summarize,fit_direct,export_direct,predict_features)
from research.tilapia_full_training_20261022.train_sensors import load_source,dump

SPECS=[{'algorithm':'ridge','alpha':a} for a in [1.,10.,100.]]+[{'algorithm':'rf'},{'algorithm':'extra'}]


def dataset(snapshot,mode):
    series,qc=load_source(snapshot);bios=snapshot['biometries'];rows=[];audit=[]
    for i,a in enumerate(bios[:-1]):
        origin=pd.Timestamp(a['date'])
        for j in range(i+1,len(bios)):
            b=bios[j];target=pd.Timestamp(b['date']);days=(target-origin).days
            if days>60:continue
            start,end=(origin-pd.Timedelta(days=7),origin) if mode=='forecast' else (origin,target)
            expected=int((end-start).total_seconds()/3600)
            f={'initial_weight_g':float(a['weight_g']),'duration_days':days}
            source_times={}
            for variable in WATER+OPTIONAL:
                s=series[variable];q=s.loc[(s.index>start)&(s.index<=end)].dropna()
                f.update({variable+'_'+name:v for name,v in summarize(q.tolist(),expected).items()})
                source_times[variable]=q.index.max().isoformat() if len(q) else None
                if len(q):assert q.index.max()<=end
            valid=all(f[v+'_coverage']>=MIN_COVERAGE for v in WATER)
            row={'anchor_id':a['id'],'target_id':b['id'],'anchor_date':a['date'],'target_date':b['date'],
                'issued_at':origin.isoformat() if mode=='forecast' else target.isoformat(),
                'window_start':start.isoformat(),'window_end':end.isoformat(),
                'observed_gain_g':float(b['weight_g'])-float(a['weight_g']),
                'actual_final_weight_g':float(b['weight_g']),'features':f,'sensor_last_source_time':source_times,
                'adjacent_biometries':j==i+1,'water_coverage_eligible':valid}
            audit.append(row)
            if valid:rows.append(row)
    return rows,audit,qc


def point(model,names,row):
    return float(model.predict([[row['features'].get(k,float('nan')) for k in names]])[0])


def select(rows,with_sensors):
    # Candidate validation uses only target dates already in the current prefix.
    validation_rows=[r for r in rows if r['adjacent_biometries']]
    scores=[]
    for spec in SPECS:
        errors=[]
        for r in validation_rows:
            fitrows=[q for q in rows if q['target_date']<=r['anchor_date']]
            if len({q['target_date'] for q in fitrows})<2:continue
            assert all(q['target_date']<=r['anchor_date']<r['target_date'] for q in fitrows)
            model,names,support=fit_direct(fitrows,spec,with_sensors)
            errors.append(abs(point(model,names,r)-r['observed_gain_g']))
        if errors:scores.append({'specification':spec,'MAE_past_validation_g':float(np.mean(errors)),
                                'n_past_validation_dates':len(errors)})
    scores.sort(key=lambda q:(q['MAE_past_validation_g'],json.dumps(q['specification'],sort_keys=True)))
    return (scores[0]['specification'] if scores else {'algorithm':'ridge','alpha':100.}),scores


def metrics(rows):
    if not rows:return {'n_dates':0}
    keys=['sensor_ML_gain_g','matched_context_only_gain_g','fixed_recipe_context_gain_g',
          'persistence_gain_g','recent_trend_gain_g','previous_ML_gain_g']
    return {'n_dates':len(rows),**{k+'_MAE':float(np.mean([abs(r[k]-r['actual_gain_g']) for r in rows])) for k in keys},
        'dates':[r['target_date'] for r in rows],
        'interpretation':'previously_known_single_campaign_retrospective_development; no prospective accuracy claim'}


def main(args):
    args.out.mkdir(parents=True,exist_ok=True);raw=args.snapshot.read_bytes();snapshot=json.loads(gzip.decompress(raw))
    baseline={r['target_date']:r for r in json.loads(args.previous_predictions.read_text())}
    protocol={'written_before_fit':datetime.now(timezone.utc).isoformat(),'snapshot_sha256':hashlib.sha256(raw).hexdigest(),
        'target':'observed final mean weight minus observed initial mean weight, in grams; never synthetic daily labels',
        'candidates':SPECS,'withheld_local_dates':'all labels have already been examined in previous project development',
        'outer_evaluation':'adjacent observed biometric intervals, after >=3 distinct past target dates',
        'training_pairs':'all pairs of existing observed endpoints <=60 days; correlated pairs are target-date balanced',
        'nested_selection':'minimum past validation MAE, chronological fits with target_date <= validation anchor',
        'ablation':'identical target dates/rows; compare separately selected context-only and same-recipe context-only',
        'coverage':'at least 70% observed hours for each water sensor; no interpolation through missing sensor periods',
        'feature_preparation':'mean, population SD, min, max, last-first change and observed-hour coverage; not intermediate learned/biological models',
        'context':['observed initial weight','requested duration in days'],
        'sensor_support':'at least 3 distinct observed target dates and variation, fit on training prefix only',
        'clock_alignment':'stored naive measurement clock, physical timezone and reception alignment unverified',
        'forecast':'sensor window is 7 days BEFORE the observed biometric anchor; future weights are forecast',
        'nowcast':'sensor window ends AT the estimated weight time; this is not forecasting from the anchor',
        'promotion':'new direct ML candidate stays experimental; no replacement based on two/three known dates'}
    dump(args.out/'protocol.json',protocol);bundle={'model_code':'TILAPIA_DIRECT_SENSOR_GROWTH_BUNDLE',
        'model_version':'0.1.0-direct-experimental','snapshot_sha256':protocol['snapshot_sha256'],
        'created_at':datetime.now(timezone.utc).isoformat(),'production_ready':False,'activated':False,'models':{}}
    all_metrics={};all_preds=[]
    for mode in ['forecast','nowcast']:
        rows,audit,qc=dataset(snapshot,mode);results=[]
        for r in [q for q in rows if q['adjacent_biometries']]:
            past=[q for q in rows if q['target_date']<=r['anchor_date']]
            if len({q['target_date'] for q in past})<3:continue
            spec,selection=select(past,True);cspec,cselection=select(past,False)
            m,names,support=fit_direct(past,spec,True);c,cn,cs=fit_direct(past,cspec,False)
            same,sn,ss=fit_direct(past,spec,False)
            gain=point(m,names,r);context=point(c,cn,r);fixedcontext=point(same,sn,r)
            b=baseline[r['target_date']]
            result={'mode':mode,'target_date':r['target_date'],'anchor_date':r['anchor_date'],
                'actual_gain_g':r['observed_gain_g'],'actual_final_weight_g':r['actual_final_weight_g'],
                'sensor_ML_gain_g':gain,'sensor_ML_final_weight_g':r['features']['initial_weight_g']+gain,
                'matched_context_only_gain_g':context,'fixed_recipe_context_gain_g':fixedcontext,
                'persistence_gain_g':0.,'recent_trend_gain_g':b['trend']-b['initial'],
                'previous_ML_gain_g':b['prediction']-b['initial'],
                'chosen':spec,'context_chosen':cspec,'n_training_pairs':len(past),
                'n_training_target_dates':len({q['target_date'] for q in past}),
                'training_last_target':max(q['target_date'] for q in past),'sensor_support':support,
                'sensor_feature_names':[k for k in names if k not in CONTEXT]}
            assert result['training_last_target']<=r['anchor_date']<r['target_date']
            results.append(result)
        spec,selection=select(rows,True);m,names,support=fit_direct(rows,spec,True)
        a=export_direct(m,names,support,rows,spec,mode)
        a['development_metrics']=metrics(results);a['source_quality']=qc
        # Independent sklearn vs portable inference for every actual endpoint pair.
        for r in rows:
            assert abs(predict_features(a,r['features'])['predicted_weight_gain_g']-point(m,names,r))<1e-8
        bundle['models'][mode]=a;all_metrics[mode]=metrics(results);all_preds+=results
        dump(args.out/(mode+'_rows.json'),rows);dump(args.out/(mode+'_coverage_audit.json'),audit)
        dump(args.out/(mode+'_selection.json'),selection)
        print(json.dumps({'mode':mode,'pairs':len(rows),'targets':a['distinct_observed_target_dates'],
            'selected':spec,'sensors':a['sensor_features_used'],'metrics':all_metrics[mode]},indent=2),flush=True)
    bundle['available_at']=datetime.now(timezone.utc).isoformat()
    dump(args.out/'direct_bundle.json',bundle);dump(args.out/'metrics.json',all_metrics)
    dump(args.out/'predictions.json',all_preds);pd.json_normalize(all_preds).to_csv(args.out/'predictions.csv',index=False)
    dump(args.out/'manifest.json',{'completed_at':datetime.now(timezone.utc).isoformat(),
        'artifact_sha256':hashlib.sha256((args.out/'direct_bundle.json').read_bytes()).hexdigest(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'core_sha256':hashlib.sha256((Path(__file__).parents[2]/'backend/app/models_engine/ml/direct_sensor_growth.py').read_bytes()).hexdigest(),
        'no_sensor_prediction_submodels':True,'no_prescribed_biological_growth_equation':True,
        'production_ready':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--previous-predictions',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
