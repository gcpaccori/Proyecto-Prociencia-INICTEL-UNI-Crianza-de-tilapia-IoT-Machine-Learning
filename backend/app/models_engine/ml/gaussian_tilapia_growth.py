"""One Gaussian process: elapsed time + measured history -> mean fish weight.

Only observed biometric means train the GP. Dense points are posterior estimates,
never additional labels. JSON inference uses no sklearn, pickle or sensor models.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
import math,statistics

VERSION='0.1.0-gaussian-experimental'
SENSORS=('temperature_c','oxygen_mg_l','ph')
LIMITS={'temperature_c':(0.,50.),'oxygen_mg_l':(0.,30.),'ph':(0.,14.)}
CENTERS={'elapsed_days':0.,'temperature_c_mean':28.,'oxygen_mg_l_p10':4.,'ph_mean':7.}
SCALES={'elapsed_days':30.,'temperature_c_mean':5.,'oxygen_mg_l_p10':2.,'ph_mean':1.}
MIN_COVERAGE=.70

def instant(value):
    d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timezone required')
    return d.astimezone(timezone.utc)

def percentile(values,p=.10):
    a=sorted(values);pos=p*(len(a)-1);lo=math.floor(pos);hi=math.ceil(pos)
    return a[lo]+(a[hi]-a[lo])*(pos-lo)

def features_from_hours(hours,cohort_start,query_at,issued_at=None):
    start=instant(cohort_start);query=instant(query_at)
    issue=instant(issued_at) if issued_at else query
    if query<start:raise ValueError('Query precedes cohort reference weight')
    if query>issue:raise ValueError('Only reconstruction/nowcast; query must not exceed issue')
    begin=start-timedelta(days=7)
    expected=math.floor((query-begin).total_seconds()/3600)
    values={k:[] for k in SENSORS};last={k:None for k in SENSORS};seen=set();late=0
    for row in hours:
        t=instant(row['hour_end'])
        if t.minute or t.second or t.microsecond:raise ValueError('Complete hour ends required')
        if t in seen:raise ValueError('Duplicate hour')
        seen.add(t)
        if t>issue:raise ValueError('Future sensor observation')
        if row.get('available_at') and instant(row['available_at'])>issue:late+=1
        if not begin<t<=query:continue
        for k in SENSORS:
            if row.get(k) is None:continue
            v=float(row[k]);lo,hi=LIMITS[k]
            if not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Unsupported sensor range/unit: '+k)
            values[k].append(v);last[k]=max(last[k],t) if last[k] else t
    cov={k:len(v)/expected for k,v in values.items()}
    if any(v>1+1e-10 for v in cov.values()):raise ValueError('More sensor hours than expected')
    f={'elapsed_days':(query-start).total_seconds()/86400}
    if all(values.values()):
        f.update(temperature_c_mean=statistics.mean(values['temperature_c']),
                 oxygen_mg_l_p10=percentile(values['oxygen_mg_l']),ph_mean=statistics.mean(values['ph']))
    return f,{'coverage':cov,'minimum_coverage':MIN_COVERAGE,
      'latest_gap_hours':{k:(query-t).total_seconds()/3600 if t else None for k,t in last.items()},
      'late_received_hour_rows':late,'physical_clock_alignment_verified':False,
      'window_start':begin.isoformat(),'window_end':query.isoformat()}

def standardized(features,names):
    return [(float(features[n])-CENTERS[n])/SCALES[n] for n in names]

def fit_gp(rows,with_sensors=True):
    import numpy as np
    import warnings
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import Kernel,ConstantKernel,Matern,WhiteKernel
    class TimeLinear(Kernel):
        def __init__(self):pass
        def __call__(self,X,Y=None,eval_gradient=False):
            X=np.asarray(X);Y=X if Y is None else np.asarray(Y)
            k=1.+np.outer(X[:,0],Y[:,0])
            return (k,np.empty(k.shape+(0,))) if eval_gradient else k
        def diag(self,X):return 1.+np.asarray(X)[:,0]**2
        def is_stationary(self):return False
    if len(rows)<2:raise ValueError('At least two real biometries required')
    if len({r['date'] for r in rows})!=len(rows):raise ValueError('Duplicate observed date')
    names=['elapsed_days']+(['temperature_c_mean','oxygen_mg_l_p10','ph_mean'] if with_sensors else [])
    if with_sensors and any(any(r['quality']['coverage'][k]<MIN_COVERAGE for k in SENSORS) for r in rows):
        raise ValueError('Insufficient observed water coverage')
    x=np.array([standardized(r['features'],names) for r in rows]);y=np.array([r['weight_g'] for r in rows])
    yscale=float(np.std(y)) or 1.
    noise=np.array([r['sample_se_g']**2 for r in rows])/yscale**2+1e-10
    # Three learned amplitudes only; physical input scales and Matern length are
    # fixed before evaluation, not searched against the held-out weights.
    kernel=(ConstantKernel(1.,(1e-3,100.))*TimeLinear()+
            ConstantKernel(.3,(1e-3,10.))*Matern(length_scale=1.,length_scale_bounds='fixed',nu=1.5)+
            WhiteKernel(.01,(1e-4,.5)))
    model=GaussianProcessRegressor(kernel=kernel,alpha=noise,normalize_y=True,
         n_restarts_optimizer=0,random_state=20261022)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');model.fit(x,y)
    return model,names,[str(w.message) for w in caught]

def export_gp(model,names,rows,warnings):
    kernel=model.kernel_;linear=float(kernel.k1.k1.k1.constant_value)
    smooth=float(kernel.k1.k2.k1.constant_value);nugget=float(kernel.k2.noise_level)
    return {'model_code':'TILAPIA_GAUSSIAN_WEIGHT_ML','model_version':VERSION,
      'target':'observed_mean_weight_g','feature_names':names,'centers':{n:CENTERS[n] for n in names},
      'scales':{n:SCALES[n] for n in names},'kernel':{'kind':'time_linear_plus_matern32_plus_white',
       'linear_amplitude':linear,'smooth_amplitude':smooth,'white_variance':nugget,'matern_length':1.},
      'x_train':model.X_train_.tolist(),'alpha_vector':model.alpha_.tolist(),'cholesky_L':model.L_.tolist(),
      'y_mean_g':float(model._y_train_mean),'y_scale_g':float(model._y_train_std),
      'n_observed_biometries':len(rows),'training_dates':[r['date'] for r in rows],
      'sampling_variances_g2':[r['sample_se_g']**2 for r in rows],
      'feature_bounds':{n:[min(r['features'][n] for r in rows),max(r['features'][n] for r in rows)] for n in names},
      'sensor_features_used':list(SENSORS) if len(names)>1 else [],
      'light_used':False,'light_reason':'insufficient paired temporal coverage',
      'no_synthetic_weight_labels':True,'no_sensor_prediction_submodels':True,
      'no_prescribed_biological_growth_equation':True,'uncertainty_calibrated':False,
      'interval_scope':'conditional_GP_mean_weight; not individual-fish distribution; excludes new sample measurement error',
      'sampling_assumption':'independent representative random samples across dates; design not verified',
      'fit_warnings':warnings,'production_ready':False,'activated':False}

def cross_kernel(a,b,k):
    d=math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))/k['matern_length'];r=math.sqrt(3.)*d
    return k['linear_amplitude']*(1.+a[0]*b[0])+k['smooth_amplitude']*(1.+r)*math.exp(-r)

def predict_gp(asset,features):
    names=asset['feature_names'];x=[]
    for n in names:
        v=float(features[n])
        if not math.isfinite(v):raise ValueError('Non-finite GP feature')
        x.append((v-asset['centers'][n])/asset['scales'][n])
    k=asset['kernel'];cross=[cross_kernel(x,z,k) for z in asset['x_train']]
    mu=asset['y_mean_g']+asset['y_scale_g']*sum(v*a for v,a in zip(cross,asset['alpha_vector']))
    v=[]
    for i,row in enumerate(asset['cholesky_L']):
        v.append((cross[i]-sum(row[j]*v[j] for j in range(i)))/row[i])
    latent_var=cross_kernel(x,x,k)-sum(q*q for q in v)
    if latent_var < -1e-7:raise ValueError('Invalid GP covariance')
    sd=asset['y_scale_g']*math.sqrt(max(0.,latent_var)+k['white_variance'])
    outside=[n for n in names if not asset['feature_bounds'][n][0]-1e-10<=float(features[n])<=asset['feature_bounds'][n][1]+1e-10]
    return {'predicted_mean_weight_g':mu,'posterior_sd_g':sd,
      'conditional_95_lower_g':mu-1.96*sd,'conditional_95_upper_g':mu+1.96*sd,
      'outside_training_domain':outside,'uncertainty_calibrated':False,
      'production_ready':False,'activated':False}

def predict_history(asset,hours,query_at,issued_at):
    f,q=features_from_hours(hours,asset['cohort_start_at'],query_at,issued_at)
    if asset['sensor_features_used'] and any(v<MIN_COVERAGE for v in q['coverage'].values()):
        raise ValueError('Insufficient observed sensor coverage')
    p=predict_gp(asset,f)
    p.update(input_features=f,source_quality=q,query_at=query_at,
      estimate_kind='retrospective_reconstruction' if instant(query_at)<=instant(asset['training_dates'][-1]+'T00:00:00+00:00') else 'nowcast')
    return p
