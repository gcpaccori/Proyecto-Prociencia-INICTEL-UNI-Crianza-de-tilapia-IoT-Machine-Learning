"""Fit 10 sensor ML candidates with purged chronological train/validation/test.

Stored measurement clocks and receipt clocks are not aligned. Evaluation is a
retrospective measurement-clock diagnostic, not proof of operational accuracy.
No synthetic growth labels and no interpolation through gaps.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from backend.app.models_engine.ml.tilapia_sensor_forecast import (
    RANGES, export_sensor_pipeline, predict_sensor)

SEED=20261022
SPECS=([{'algorithm':'ridge','alpha':a} for a in [1.,10.,100.]] +
       [{'algorithm':a,'depth':d} for a in ['rf','extra'] for d in [3,6]])


def clean(value):
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    if isinstance(value,(float,np.floating)):return float(value) if np.isfinite(value) else None
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,(datetime,pd.Timestamp)):return value.isoformat()
    return value


def dump(path,value):path.write_text(json.dumps(clean(value),indent=2,allow_nan=False))


def load_source(snapshot):
    out={};qc={}
    for kind in ['water','light']:
        q=pd.DataFrame(snapshot[kind+'_hourly'],columns=snapshot[kind+'_hour_columns'])
        q['hour_end']=pd.to_datetime(q.hour_end);q['last_received']=pd.to_datetime(q.last_received)
        q=q.set_index('hour_end').sort_index()
        if not q.index.is_unique:raise ValueError('Duplicated source hour')
        for variable in [c for c in q if c in RANGES]:
            s=pd.to_numeric(q[variable],errors='coerce').astype(float)
            lo,hi=RANGES[variable];bad=s.notna() & ~s.between(lo,hi)
            invalid=int(bad.sum());s[bad]=np.nan
            s=s.reindex(pd.date_range(s.index.min(),s.index.max(),freq='h'))
            flagged=0
            if variable=='oxygen_mg_l':
                stuck=s.sub(7.22).abs().lt(1e-8).rolling(8,min_periods=8).sum().eq(8)
                flagged=int(stuck.sum());s[stuck]=np.nan
            out[variable]=s
            qc[variable]={'observed_hour_bins':int(s.notna().sum()),'invalid_hourly_means_removed':invalid,
                'previously_flagged_oxygen_7_22_run_hours_removed':flagged,
                'first_stored_hour_end':s.index.min(),'last_stored_hour_end':s.index.max(),
                'last_received':q.last_received.max(),
                'physical_calibration_verified':False,
                'unit_convention':'unverified_native_units' if variable=='nitrate_native_units' else 'project_declared_units'}
    return out,qc


def features(s):
    x=pd.DataFrame(index=s.index)
    for lag in [0,1,2,3,6,12,24,48,168]:x['lag_'+str(lag)]=s.shift(lag)
    for hours,minimum in [(6,4),(24,18),(72,36)]:
        r=s.rolling(hours,min_periods=minimum)
        for name in ['mean','std','min','max']:x[name+'_'+str(hours)]=getattr(r,name)()
    for lag in [1,6,24]:x['change_'+str(lag)]=s-s.shift(lag)
    for period,key in [(24,'hour'),(168,'week')]:
        t=(x.index-pd.Timestamp('2025-01-01')).total_seconds()/3600
        x['sin_'+key]=np.sin(2*np.pi*t/period);x['cos_'+key]=np.cos(2*np.pi*t/period)
    return x


def supervised(s,horizon):
    x=features(s)
    # The 24 h target is the mean of all 24 future observed hourly means.
    # The current hour is an input; it must never appear in the future target.
    y=s.shift(-1) if horizon==1 else s.rolling(24,min_periods=24).mean().shift(-24)
    baseline=s if horizon==1 else s.rolling(24,min_periods=18).mean()
    mask=s.notna() & y.notna() & x.mean_24.notna() & baseline.notna()
    return x.loc[mask],y.loc[mask],baseline.loc[mask]


def masks(index,horizon):
    n=len(index)
    if n<60:raise ValueError('Insufficient observed supervised sensor windows')
    end=index+pd.Timedelta(hours=horizon)
    # Select split from timestamps/counts only, before reading errors/targets.
    # Sparse light can have fewer than 24 hours in the nominal validation block.
    for val_fraction,test_fraction in [(.6,.8),(.4,.7)]:
        validation_start=index[int(n*val_fraction)];test_start=index[int(n*test_fraction)]
        train=end<validation_start
        validation=(index>=validation_start)&(end<test_start)
        test=index>=test_start
        refit=end<test_start
        if min(train.sum(),validation.sum(),test.sum())>=10:
            return train,validation,test,refit,validation_start,test_start
    raise ValueError('Insufficient windows after temporal purge')


def build(spec):
    if spec['algorithm']=='ridge':reg=Ridge(alpha=spec['alpha'])
    else:
        cls=RandomForestRegressor if spec['algorithm']=='rf' else ExtraTreesRegressor
        reg=cls(n_estimators=120,max_depth=spec['depth'],min_samples_leaf=8,
                random_state=SEED,n_jobs=1)
    return Pipeline([('impute',SimpleImputer(keep_empty_features=True)),
                     ('scale',StandardScaler()),('reg',reg)])


def scores(y,p):
    return {'n_correlated_windows':len(y),'MAE':mean_absolute_error(y,p),
        'RMSE':float(np.sqrt(mean_squared_error(y,p))),
        'R2':r2_score(y,p) if len(y)>2 and np.var(y)>0 else None,
        'distinct_target_days':len(pd.DatetimeIndex(y.index).normalize().unique())}


def bounded(values,variable):return np.clip(values,*RANGES[variable])


def main(args):
    args.out.mkdir(parents=True,exist_ok=True)
    raw=args.snapshot.read_bytes();snapshot=json.loads(gzip.decompress(raw))
    series,qc=load_source(snapshot)
    protocol={'written_before_new_fit':datetime.now(timezone.utc).isoformat(),
        'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'candidates':SPECS,
        'selection':'minimum validation MAE among ML candidates; test scores excluded',
        'split':'eligible origins chronological 60/20/20; 40/30/30 fallback only if purged counts <10; split chosen from timestamps/counts, never errors; training and validation target ends purged before next block',
        'baseline':'last observed hour for 1h; past 24h mean with >=18 observed hours for 24h',
        'target_24h':'all 24 future hourly means observed; no gap imputation in targets',
        'input_imputation':'fit only on training block; no forward/backward interpolation',
        'known_data':'This campaign and portions of its sensor records were already examined in earlier development; new split is not a new blind study',
        'prior_attempt':'The initial run stopped before light/24h fitting because nominal purging left zero validation rows; initial scores retained separately. Nitrate range changed from arbitrary 10000 to DECIMAL(8,2) schema bound, units remain unverified. Final diagnostics are not independent of earlier development.',
        'availability':'historical stored-measurement-clock diagnostic; receipt availability and physical clock alignment unverified',
        'final_refit':'selected ML candidate refitted on all observed supervised windows only after frozen test predictions',
        'promotion':'a trained ML candidate is retained even if baseline is better; no automatic activation',
        'growth_fusion':'sensor prediction performance does not establish sensor effects on growth'}
    dump(args.out/'protocol.json',protocol);dump(args.out/'source_quality.json',qc)
    bundle={'model_code':'TILAPIA_SENSOR_FORECAST_BUNDLE','model_version':'0.1.0-trained-experimental',
        'created_at':datetime.now(timezone.utc).isoformat(),'snapshot_sha256':protocol['snapshot_sha256'],
        'clock_alignment_verified':False,'production_ready':False,'models':{}}
    results=[];predictions=[]
    for variable,s in series.items():
        for horizon in [1,24]:
            key=f'{variable}/{horizon}h'
            x,y,b=supervised(s,horizon)
            train,val,test,refit,val_start,test_start=masks(x.index,horizon)
            candidates=[]
            for spec in SPECS:
                model=build(spec).fit(x.loc[train],y.loc[train])
                p=bounded(model.predict(x.loc[val]),variable)
                candidates.append({'specification':spec,'validation':scores(y.loc[val],p)})
            candidates.sort(key=lambda z:(z['validation']['MAE'],json.dumps(z['specification'],sort_keys=True)))
            chosen=candidates[0]['specification']
            # Freeze test predictions before final all-data refit.
            model=build(chosen).fit(x.loc[refit],y.loc[refit])
            p=bounded(model.predict(x.loc[test]),variable)
            test_score=scores(y.loc[test],p);base_score=scores(y.loc[test],b.loc[test])
            for t,a,v,base in zip(x.index[test],y.loc[test],p,b.loc[test]):
                predictions.append({'variable':variable,'horizon_hours':horizon,'source_origin':t,
                    'target_end':t+pd.Timedelta(hours=horizon),'observed':a,'predicted_ML':v,'baseline':base})
            result={'variable':variable,'horizon_hours':horizon,'supervised_windows':len(x),
                'train_windows':int(train.sum()),'validation_windows':int(val.sum()),'test_windows':int(test.sum()),
                'validation_start':val_start,'test_start':test_start,'selected_ML':chosen,
                'selected_validation_MAE':candidates[0]['validation']['MAE'],
                'test_ML':test_score,'test_baseline':base_score,'ML_beats_baseline':test_score['MAE']<base_score['MAE'],
                'MAE_ratio_to_baseline':test_score['MAE']/base_score['MAE'] if base_score['MAE']>0 else None}
            dump(args.out/(variable+'_'+str(horizon)+'h_selection.json'),candidates)
            final=build(chosen).fit(x,y)
            asset=export_sensor_pipeline(final,x.columns)
            # Roundtrip before shipping a portable artifact; never unpickle on server.
            checks=x.iloc[np.linspace(0,len(x)-1,min(20,len(x)),dtype=int)]
            expected=bounded(final.predict(checks),variable)
            got=[predict_sensor(asset,row,variable) for row in checks.to_dict('records')]
            if not np.allclose(expected,got,rtol=1e-9,atol=1e-8):raise AssertionError('Portable sensor mismatch')
            last_time=s.last_valid_index();tail=features(s).loc[last_time].to_dict()
            asset.update(variable=variable,horizon_hours=horizon,specification=chosen,
                training_windows=len(x),training_last_source_target=(x.index+pd.Timedelta(hours=horizon)).max(),
                target_kind='next_hour_mean' if horizon==1 else 'next_24h_mean',
                validation=result,offline_tail_projection={'source_anchor_time':last_time,
                    'source_target_end':last_time+pd.Timedelta(hours=horizon),
                    'value':predict_sensor(asset,tail,variable),'generated_at':datetime.now(timezone.utc).isoformat(),
                    'status':'offline_projection_not_an_archived_or_current_operational_forecast'})
            bundle['models'][key]=asset;results.append(result)
            dump(args.out/'sensor_bundle.json',bundle);dump(args.out/'sensor_scores.json',results)
            pd.DataFrame(predictions).to_csv(args.out/'sensor_test_predictions.csv',index=False)
            print(json.dumps(clean({'trained':key,'selected':chosen,'windows':len(x),
                'test_MAE':test_score['MAE'],'baseline_MAE':base_score['MAE']})),flush=True)
    dump(args.out/'training_manifest.json',{'completed_at':datetime.now(timezone.utc).isoformat(),
        'models_trained':len(bundle['models']),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'artifact_sha256':hashlib.sha256((args.out/'sensor_bundle.json').read_bytes()).hexdigest(),
        'final_refit_covers_all_eligible_observed_windows':True,'test_predictions_frozen_before_refit':True,
        'biological_validation_completed':False,'production_ready':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
