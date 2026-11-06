"""Direct interval-growth ML with correlated biometric sampling noise.

Known-label, one-cohort development experiment. No biological growth formula,
pseudo-daily weights, sensor forecast submodels, clock shifts or deployment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from sklearn.ensemble import ExtraTreesRegressor

SEED = 20261024
CONTEXT = ['initial_weight_g', 'duration_days']
VARIANTS = {
    'context': CONTEXT,
    'water_means': CONTEXT + ['temperature_mean', 'oxygen_mean'],
    'exposure': CONTEXT + ['temperature_mean', 'oxygen_p10'],
    'exposure_variation': CONTEXT + ['temperature_mean', 'temperature_sd', 'oxygen_p10', 'oxygen_sd'],
    'exposure_ph': CONTEXT + ['temperature_mean', 'oxygen_p10', 'ph_sd'],
    'temperature_only': CONTEXT + ['temperature_mean'],
    'oxygen_only': CONTEXT + ['oxygen_p10'],
}
FAMILIES = ['gaussian_correlated', 'ridge_correlated', 'extra_trees']
MODES = ['receipt_available', 'measurement_nominal', 'measurement_available']
MIN_COVERAGE = .70
MAX_LATEST_GAP_HOURS = 48


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False, default=str))


def frame(rows, columns):
    q = pd.DataFrame(rows, columns=columns)
    q['hour_end'] = pd.to_datetime(q.hour_end)
    q['last_received'] = pd.to_datetime(q.last_received)
    assert q.hour_end.is_unique
    return q.sort_values('hour_end')


def interval_summary(water, light, start, end, enforce_receipt):
    q = water[(water.hour_end > start) & (water.hour_end <= end)]
    if enforce_receipt:
        q = q[q.last_received <= end]
    expected = int((end-start).total_seconds()/3600)
    features = {}; cov = {}; gaps = {}; last = {}
    for key, name in [('temperature_c','temperature'), ('oxygen_mg_l','oxygen'), ('ph','ph')]:
        s = pd.to_numeric(q[key], errors='coerce')
        valid = s.notna() & np.isfinite(s)
        v = s[valid].to_numpy(dtype=float)
        cov[name] = len(v)/expected
        last[name] = q.loc[valid, 'hour_end'].max().isoformat() if len(v) else None
        gaps[name] = float((end-q.loc[valid, 'hour_end'].max()).total_seconds()/3600) if len(v) else None
        features[name+'_mean'] = float(v.mean()) if len(v) else None
        features[name+'_sd'] = float(v.std()) if len(v) else None
        features[name+'_p10'] = float(np.quantile(v,.1)) if len(v) else None
        if len(v):
            assert q.loc[valid,'hour_end'].max() <= end
            if enforce_receipt:
                assert q.loc[valid,'last_received'].max() <= end
    z = light[(light.hour_end > start) & (light.hour_end <= end) & (light.last_received <= end)]
    v = pd.to_numeric(z.light_lux,errors='coerce').dropna().to_numpy(dtype=float)
    cov['light'] = len(v)/expected
    features['light_mean'] = float(v.mean()) if len(v) else None
    eligible = all(cov[k] >= MIN_COVERAGE and gaps[k] is not None
                   and gaps[k] <= MAX_LATEST_GAP_HOURS for k in ['temperature','oxygen','ph'])
    return features, {'coverage':cov, 'last_gap_hours':gaps, 'last_source_hour':last,
                      'eligible':eligible, 'expected_hours':expected}


def build_rows(snapshot, stats, mode):
    axis = 'measurement' if mode.startswith('measurement') else 'receipt'
    water = frame(snapshot[axis+'_water_hourly'],snapshot['hour_columns'])
    light = frame(snapshot['receipt_light_hourly'],snapshot['light_hour_columns'])
    bios = snapshot['biometries']; rows = []
    for i,(a,b) in enumerate(zip(bios,bios[1:])):
        start,end = pd.Timestamp(a['date']),pd.Timestamp(b['date'])
        f,qc = interval_summary(water,light,start,end,mode!='measurement_nominal')
        f.update(initial_weight_g=float(a['weight_g']),duration_days=float((end-start).days))
        rows.append({'interval_index':i,'mode':mode,'anchor':a['date'],'target':b['date'],
                     'issued_at':str(end),'initial_id':int(a['id']),'final_id':int(b['id']),
                     'initial_weight_g':float(a['weight_g']),'actual_weight_g':float(b['weight_g']),
                     'observed_gain_g':float(b['weight_g'])-float(a['weight_g']),
                     'features':f,'quality':qc})
    return rows


def sampling_covariance(rows, stats):
    """Gain errors share endpoints. Stats contain only endpoints of these rows."""
    ids=sorted({r[k] for r in rows for k in ['initial_id','final_id']})
    positions={key:i for i,key in enumerate(ids)}
    incidence=np.zeros((len(rows),len(ids)))
    var=[]
    for key in ids:
        s=stats[key]
        var.append(float(s['sd_g'])**2/int(s['n']))
    for i,r in enumerate(rows):
        incidence[i,positions[r['initial_id']]]=-1
        incidence[i,positions[r['final_id']]]=1
    return (incidence*np.array(var)) @ incidence.T


def kernel(x,z,log_parameters):
    d=x.shape[1]
    linear=math.exp(float(log_parameters[0]))*(1+x@z.T/d)
    distance=np.sqrt(np.maximum(0,((x[:,None,:]-z[None,:,:])**2).sum(2)/d))
    t=np.sqrt(3)*distance
    return linear+math.exp(float(log_parameters[1]))*(1+t)*np.exp(-t)


def fit_model(rows,stats,names,family):
    # Only training rows can determine scales, target centering or noise.
    x=np.array([[r['features'][k] for k in names] for r in rows],dtype=float)
    y=np.array([r['observed_gain_g'] for r in rows],dtype=float)
    assert np.isfinite(x).all() and np.isfinite(y).all()
    means=x.mean(0);scales=x.std(0);scales[scales<1e-10]=1
    z=(x-means)/scales
    ym=float(y.mean());ys=max(float(y.std()),1.0);yz=(y-ym)/ys
    noise=sampling_covariance(rows,stats)/ys**2
    a={'family':family,'feature_names':names,'means':means.tolist(),'scales':scales.tolist(),
       'y_mean':ym,'y_scale':ys,'n_training_intervals':len(rows),
       'training_last_target':max(r['target'] for r in rows),
       'feature_bounds':{k:[float(x[:,j].min()),float(x[:,j].max())] for j,k in enumerate(names)},
       'target':'observed_weight_gain_g','clock_alignment_verified':False,
       'production_ready':False,'activated':False,
       'sampling_assumptions':'independent representative samples at biometric dates; shared-endpoint covariance retained for Gaussian and ridge models; initial input error not fully modeled',
       'target_noise_used':'training endpoints only; target sample variance is never an input at evaluation'}
    if family=='gaussian_correlated':
        def loss(theta):
            c=kernel(z,z,theta)+noise+(math.exp(float(theta[2]))+1e-8)*np.eye(len(y))
            try:
                cf=cho_factor(c,lower=True,check_finite=False)
                return float(.5*yz@cho_solve(cf,yz,check_finite=False)+np.log(np.diag(cf[0])).sum()+len(y)*.5*np.log(2*np.pi))
            except np.linalg.LinAlgError:
                return 1e50
        result=minimize(loss,np.array([0.,0.,-2.]),method='L-BFGS-B',bounds=[(-7,7),(-7,7),(-9,5)],options={'maxiter':160})
        theta=result.x
        c=kernel(z,z,theta)+noise+(math.exp(float(theta[2]))+1e-8)*np.eye(len(y))
        L=np.linalg.cholesky(c);alpha=cho_solve((L,True),yz)
        a.update(x_train=z.tolist(),log_parameters=theta.tolist(),alpha=alpha.tolist(),cholesky=L.tolist(),
                 training_sampling_covariance_g2=(noise*ys**2).tolist(),
                 optimizer={'success':bool(result.success),'message':str(result.message),'negative_log_marginal_likelihood':float(result.fun)})
        ref=ym+ys*kernel(z,z,theta)@cho_solve((L,True),yz)
    elif family=='ridge_correlated':
        # One supervised generalized ridge regressor, not a growth formula.
        precision=np.linalg.inv(noise+.05*np.eye(len(y)))
        posterior=np.linalg.inv(z.T@precision@z+10*np.eye(z.shape[1]))
        beta=posterior@z.T@precision@yz
        a.update(coefficients=beta.tolist(),posterior=posterior.tolist(),ridge_penalty=10.,
                 training_sampling_covariance_g2=(noise*ys**2).tolist())
        ref=ym+ys*z@beta
    else:
        reg=ExtraTreesRegressor(n_estimators=240,max_depth=2,min_samples_leaf=1,random_state=SEED,n_jobs=1)
        v=np.diag(noise)*ys**2
        reg.fit(z,y,sample_weight=1/(v+1.))
        a['trees']=[{'left':t.tree_.children_left.tolist(),'right':t.tree_.children_right.tolist(),
            'feature':t.tree_.feature.tolist(),'threshold':t.tree_.threshold.tolist(),
            'value':t.tree_.value[:,0,0].tolist()} for t in reg.estimators_]
        a['sampling_assumptions']='diagonal sampling-precision weights only; shared-endpoint dependence not fully modeled by this diagnostic forest'
        ref=reg.predict(z)
    # Compare portable inference after a JSON serialization round trip.
    decoded=json.loads(json.dumps(a,allow_nan=False))
    got=np.array([predict_model(decoded,r['features'])['predicted_gain_g'] for r in rows])
    assert np.allclose(ref,got,rtol=0,atol=1e-7),(family,ref,got)
    return a


def predict_model(a,features):
    names=a['feature_names']
    x=np.array([float(features[k]) for k in names]);assert np.isfinite(x).all()
    z=(x-np.array(a['means']))/np.array(a['scales'])
    sd=None
    if a['family']=='gaussian_correlated':
        train=np.array(a['x_train']);theta=np.array(a['log_parameters'])
        k=kernel(z[None,:],train,theta)[0]
        gain=a['y_mean']+a['y_scale']*float(k@np.array(a['alpha']))
        v=np.linalg.solve(np.array(a['cholesky']),k)
        variance=float(kernel(z[None,:],z[None,:],theta)[0,0]-v@v)
        sd=a['y_scale']*math.sqrt(max(0.,variance))
    elif a['family']=='ridge_correlated':
        gain=a['y_mean']+a['y_scale']*float(z@np.array(a['coefficients']))
    else:
        out=[]
        for t in a['trees']:
            i=0
            while t['left'][i]>=0:
                i=t['left'][i] if z[t['feature'][i]]<=t['threshold'][i] else t['right'][i]
            out.append(t['value'][i])
        gain=float(np.mean(out))
    outside=[k for k,value in zip(names,x) if not a['feature_bounds'][k][0]-1e-9<=value<=a['feature_bounds'][k][1]+1e-9]
    return {'predicted_gain_g':float(gain),'predicted_weight_g':float(features['initial_weight_g'])+float(gain),
            'conditional_latent_gain_sd_g':sd,'outside_training_features':outside,
            'uncertainty_calibrated':False,'activated':False,'production_ready':False}


def evaluate(rows,stats,family,names,min_training=2):
    out=[]
    for i,r in enumerate(rows):
        past=[q for q in rows[:i] if q['quality']['eligible']]
        if not r['quality']['eligible'] or len(past)<min_training:
            continue
        assert all(q['target']<=r['anchor']<r['target'] for q in past)
        a=fit_model(past,stats,names,family)
        prediction=predict_model(a,r['features'])
        out.append({'mode':r['mode'],'family':family,'target':r['target'],'anchor':r['anchor'],
                    'actual_weight_g':r['actual_weight_g'],'observed_gain_g':r['observed_gain_g'],
                    'n_training_intervals':len(past),'training_last_target':a['training_last_target'],
                    **prediction,'absolute_error_g':abs(prediction['predicted_weight_g']-r['actual_weight_g'])})
    return out


def metrics(predictions):
    if not predictions:return {'n_dates':0,'MAE_g':None,'RMSE_g':None,'max_error_g':None,'dates':[]}
    errors=np.array([r['predicted_weight_g']-r['actual_weight_g'] for r in predictions])
    return {'n_dates':len(errors),'MAE_g':float(np.mean(abs(errors))),'RMSE_g':float(np.sqrt(np.mean(errors**2))),
            'max_error_g':float(np.max(abs(errors))),'bias_g':float(np.mean(errors)),
            'dates':[r['target'] for r in predictions]}


def main(args):
    args.out.mkdir(parents=True,exist_ok=True)
    protocol={'written_before_fit':datetime.now(timezone.utc).isoformat(),
        'task':'end-of-interval nowcast, NOT a forecast issued at the initial biometry',
        'labels':'only six adjacent differences of seven observed biometric sample means',
        'families':FAMILIES,'variants':VARIANTS,'primary_family':'gaussian_correlated','primary_variant':'exposure',
        'primary_clock':'receipt_available; reception does not establish physical event time',
        'measurement_nominal':'diagnostic only; no receipt availability guarantee',
        'measurement_available':'requires complete hour max receipt <= interval target, conservative for partly available bins',
        'minimum_training_intervals':2,'evaluation':'all eligible chronological intervals with >=2 previous eligible intervals; also report >=3 subset',
        'feature_selection':'fixed before this fit; no algorithm or variant selected by outer MAE',
        'preprocessing':'training-prefix means and scales only; no label interpolation or synthetic weights; hourly QC inherited from immutable export',
        'coverage':MIN_COVERAGE,'max_latest_gap_hours':MAX_LATEST_GAP_HOURS,
        'gaussian':'linear + Matern32 kernel, marginal-likelihood fit on prefix only; one fixed optimizer initialization; full shared-endpoint sampling covariance',
        'ridge':'generalized ridge, full shared-endpoint sampling covariance and fixed regularization 10',
        'extra_trees':'240 trees max_depth2, fixed seed; diagonal sampling-precision weights; diagnostic',
        'sampling':'SD/sqrt(n) assumes representative independent samples at dates; gains sharing endpoints correlated; initial input measurement error not fully represented',
        'excluded':'light lacks sufficient paired coverage; physical feed delivery not verified; no inferred NH3 from nitrate; no clock shift fitted to labels',
        'known_development_labels':True,'independent_campaigns':1,'causal_effect_claim':False,
        'production_ready':False,'activated':False,
        'snapshot_sha256':hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        'biometric_summary_sha256':hashlib.sha256(args.biometry_stats.read_bytes()).hexdigest()}
    dump(args.out/'protocol.json',protocol)
    snapshot=json.loads(gzip.decompress(args.snapshot.read_bytes()))
    stats={int(r['biometry_id']):r for r in pd.read_csv(args.biometry_stats).to_dict('records')}
    assert len(stats)==len(snapshot['biometries'])==7
    for b in snapshot['biometries']:
        assert abs(stats[int(b['id'])]['mean_g']-b['weight_g'])<1e-7
    results=[];all_rows=[];scores=[];assets={}
    for mode in MODES:
        rows=build_rows(snapshot,stats,mode);all_rows.extend(rows)
        eligible=[r for r in rows if r['quality']['eligible']]
        print(json.dumps({'mode':mode,'eligible_intervals':len(eligible),'targets':[r['target'] for r in eligible]}),flush=True)
        for family in FAMILIES:
            for variant,names in VARIANTS.items():
                pred=evaluate(rows,stats,family,names)
                for r in pred:r['variant']=variant
                results.extend(pred)
                scores.append({'mode':mode,'family':family,'variant':variant,**metrics(pred)})
                if len(eligible)>=2:
                    assets[mode+'/'+family+'/'+variant]=fit_model(eligible,stats,names,family)
    dump(args.out/'intervals.json',all_rows)
    pd.json_normalize(all_rows).to_csv(args.out/'intervals.csv',index=False)
    dump(args.out/'predictions.json',results)
    pd.json_normalize(results).to_csv(args.out/'predictions.csv',index=False)
    dump(args.out/'scores.json',scores)
    dump(args.out/'models.json',{'production_ready':False,'activated':False,'clock_alignment_verified':False,'models':assets})
    primary=[r for r in scores if r['mode']=='receipt_available' and r['family']=='gaussian_correlated']
    dump(args.out/'primary_summary.json',{'primary_family':'gaussian_correlated','primary_variant':'exposure',
        'clock':'receipt_available','all_four_if_eligible':primary,
        'secondary_three_dates':[{'variant':v,**metrics([p for p in results if p['mode']=='receipt_available' and p['family']=='gaussian_correlated' and p['variant']==v and p['n_training_intervals']>=3])} for v in VARIANTS],
        'known_label_development':True,'physical_clock_verified':False,'causal_validation':False})
    dump(args.out/'manifest.json',{'completed_at':datetime.now(timezone.utc).isoformat(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'snapshot_sha256':protocol['snapshot_sha256'],'biometric_summary_sha256':protocol['biometric_summary_sha256'],
        'no_new_observed_biometries':True,'no_synthetic_daily_weight_labels':True,
        'no_growth_formula_or_sensor_submodels':True})
    print(json.dumps({'primary_scores':primary,'n_exported_assets':len(assets)},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--biometry-stats',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
