"""One learned regressor: measured sensor window + context -> weight gain in g.

No sensor forecasting model, growth-rate model, donor growth model or prescribed
biological growth equation is called. Summary statistics are input preparation.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime,timedelta,timezone

from backend.app.models_engine.ml.supervised_tilapia_growth import portable_regression,timestamp
from backend.app.models_engine.ml.tilapia_sensor_forecast import export_sensor_pipeline

CODE='TILAPIA_DIRECT_SENSOR_GROWTH_ML'
VERSION='0.1.0-direct-experimental'
WATER=('temperature_c','oxygen_mg_l','ph')
OPTIONAL=('light_lux',)
CONTEXT=('initial_weight_g','duration_days')
STATS=('mean','sd','minimum','maximum','change','coverage')
LIMITS={'temperature_c':(0,50),'oxygen_mg_l':(0,30),'ph':(0,14),'light_lux':(0,200000)}
MIN_COVERAGE=.70


def summarize(values:list[float],expected_hours:int)->dict:
    if expected_hours<=0:raise ValueError('Positive number of expected hours required')
    if len(values)>expected_hours:raise ValueError('More observed hours than expected')
    if not values:return dict.fromkeys(STATS[:-1],None)|{'coverage':0.}
    if any(not math.isfinite(v) for v in values):raise ValueError('Non-finite sensor value')
    return {'mean':statistics.mean(values),'sd':statistics.pstdev(values),
        'minimum':min(values),'maximum':max(values),'change':values[-1]-values[0],
        'coverage':len(values)/expected_hours}


def summarize_request(payload:dict)->dict:
    mode=payload['mode'];issue=timestamp(payload['issued_at']);anchor=timestamp(payload['anchor_observed_at'])
    target=timestamp(payload['target_at']);initial=float(payload['initial_weight_g'])
    if not math.isfinite(initial) or initial<=0:raise ValueError('Positive finite initial weight required')
    if mode=='forecast':
        if issue!=anchor:raise ValueError('Forecast is trained at a fresh observed biometry origin; anchor must equal issue')
        if target<=issue:raise ValueError('Forecast target must be after issue')
        begin=issue-timedelta(days=7);end=issue
    elif mode=='nowcast':
        if target!=issue:raise ValueError('Nowcast target must equal issue; observed interval sensors are not a future forecast')
        if anchor>=issue:raise ValueError('Nowcast anchor must precede issue')
        begin=anchor;end=issue
    else:raise ValueError('Unknown direct model mode')
    duration=(target-anchor).total_seconds()/86400
    if not 0<duration<=60:raise ValueError('Direct model duration must be in (0,60] days')
    expected=int((end-begin).total_seconds()//3600)
    if expected<1:raise ValueError('At least one complete sensor hour required')
    collected={k:[] for k in WATER+OPTIONAL};seen=set()
    for row in payload['hourly_measurements']:
        t=timestamp(row['hour_end'])
        if t.minute or t.second or t.microsecond:raise ValueError('Input timestamps must identify complete hour ends')
        if t in seen:raise ValueError('Duplicate sensor hour')
        seen.add(t)
        if t>issue:raise ValueError('Future sensor measurements cannot be used')
        if row.get('available_at') and timestamp(row['available_at'])>issue:
            raise ValueError('Sensor observation was unavailable at issue time')
        if not begin<t<=end:continue
        for key in collected:
            if row.get(key) is None:continue
            v=float(row[key]);lo,hi=LIMITS[key]
            if not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Unsupported sensor unit/range: '+key)
            collected[key].append((t,v))
    result={'initial_weight_g':initial,'duration_days':duration}
    for key,rows in collected.items():
        stats=summarize([v for _,v in sorted(rows)],expected)
        result.update({key+'_'+name:v for name,v in stats.items()})
    return result


def names_for_training(rows:list[dict],with_sensors:bool)->tuple[list[str],dict]:
    support={};names=list(CONTEXT)
    for variable in WATER+OPTIONAL:
        supported=[r for r in rows if r['features'].get(variable+'_coverage',0)>=MIN_COVERAGE]
        dates={r['target_date'] for r in supported}
        varying=len({r['features'][variable+'_mean'] for r in supported})>=2
        eligible=with_sensors and len(dates)>=3 and varying
        support[variable]={'eligible':eligible,'distinct_observed_target_dates':len(dates),
            'within_sample_variation':varying,'minimum_coverage':MIN_COVERAGE}
        if eligible:names.extend(variable+'_'+s for s in STATS)
    return names,support


def fit_direct(rows:list[dict],spec:dict,with_sensors:bool=True):
    import numpy as np
    from collections import Counter
    from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    if len(rows)<2:raise ValueError('At least two observed endpoint pairs required')
    names,support=names_for_training(rows,with_sensors)
    x=[[r['features'].get(k,float('nan')) for k in names] for r in rows]
    y=[r['observed_gain_g'] for r in rows]
    if spec['algorithm']=='ridge':reg=Ridge(alpha=spec['alpha'])
    else:
        cls=RandomForestRegressor if spec['algorithm']=='rf' else ExtraTreesRegressor
        reg=cls(n_estimators=120,max_depth=2,min_samples_leaf=2,random_state=20261022,n_jobs=1)
    counts=Counter(r['target_date'] for r in rows)
    weights=np.array([len(rows)/(len(counts)*counts[r['target_date']]) for r in rows])
    model=Pipeline([('impute',SimpleImputer(keep_empty_features=True)),('scale',StandardScaler()),('reg',reg)])
    model.fit(x,y,reg__sample_weight=weights)
    return model,names,support


def export_direct(model,names,support,rows,spec,mode)->dict:
    a=export_sensor_pipeline(model,names)
    if a['regressor']['kind']=='linear':
        used={i for i,v in enumerate(a['regressor']['coefficients']) if abs(v)>1e-12}
    else:used={i for t in a['regressor']['trees'] for i in t['feature'] if i>=0}
    active=[v for v in WATER+OPTIONAL if any(i in used and k.startswith(v+'_') for i,k in enumerate(names))]
    bounds={}
    for key in names:
        vv=[float(r['features'][key]) for r in rows if r['features'].get(key) is not None]
        bounds[key]=[min(vv),max(vv)] if vv else None
    a.update(model_code=CODE,model_version=VERSION,mode=mode,specification=spec,
        target='observed_weight_gain_g',training_endpoint_pairs=len(rows),
        distinct_observed_target_dates=len({r['target_date'] for r in rows}),
        sensor_support=support,sensor_features_used=active,
        supported_sensor_groups=[v for v,s in support.items() if s['eligible']],
        feature_bounds=bounds,
        no_sensor_prediction_submodels=True,no_prescribed_biological_growth_equation=True,
        clock_alignment_verified=False,production_ready=False,activated=False,
        prediction_interval_g=None,uncertainty_calibrated=False,
        created_at=datetime.now(timezone.utc).isoformat(),
        training_last_target=max(r['target_date'] for r in rows))
    return a


def predict_features(asset:dict,features:dict)->dict:
    z=[]
    for i,name in enumerate(asset['feature_names']):
        value=features.get(name)
        value=asset['impute_values'][i] if value is None or math.isnan(float(value)) else float(value)
        if not math.isfinite(value):raise ValueError('Invalid direct model feature')
        z.append((value-asset['means'][i])/asset['scales'][i])
    gain=portable_regression(asset['regressor'],z)
    if not math.isfinite(gain):raise ValueError('Unstable direct ML prediction')
    total=float(features['initial_weight_g'])+gain
    if total<=0:raise ValueError('Direct model produced a nonpositive final weight')
    outside=[k for k,bounds in asset.get('feature_bounds',{}).items() if bounds is not None
        and features.get(k) is not None and not bounds[0]-1e-10<=float(features[k])<=bounds[1]+1e-10]
    return {'predicted_weight_gain_g':gain,
        'predicted_final_mean_weight_g':total,'outside_training_domain':outside,
        'sensor_features_used':asset['sensor_features_used'],
        'production_ready':False,'activated':False,'prediction_interval_g':None}


def predict_direct(asset:dict,payload:dict)->dict:
    if asset['mode']!=payload['mode']:raise ValueError('Artifact and measurement window mode differ')
    f=summarize_request(payload)
    for variable in asset['sensor_features_used']:
        if f.get(variable+'_coverage',0)<MIN_COVERAGE:
            raise ValueError('Insufficient observed hours for trained sensor: '+variable)
    return {**predict_features(asset,f),'model_code':CODE,'model_version':VERSION,'mode':asset['mode'],
        'target':asset['target'],'input_features':f,
        'clock_alignment_verified':False,'no_sensor_prediction_submodels':True,
        'no_prescribed_biological_growth_equation':True}
