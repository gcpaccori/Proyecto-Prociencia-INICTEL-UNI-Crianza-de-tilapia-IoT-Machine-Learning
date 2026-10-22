"""Real biometric means only; GP curve is an output, never a pseudo-label.

Rolling evaluation is a NOWCAST issued on the withheld biometry date using its
observed sensor history, never a forecast issued before those measurements.
"""
import argparse,csv,gzip,hashlib,json,math
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from backend.app.models_engine.ml.gaussian_tilapia_growth import (
    SENSORS,LIMITS,MIN_COVERAGE,features_from_hours,fit_gp,export_gp,predict_gp)

def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def source(snapshot):
    frame=pd.DataFrame(snapshot['water_hourly'],columns=snapshot['water_hour_columns'])
    frame['hour_end']=pd.to_datetime(frame.hour_end,utc=True);frame=frame.set_index('hour_end').sort_index()
    if not frame.index.is_unique:raise ValueError('Duplicate source hour')
    qc={}
    for v in SENSORS:
        frame[v]=pd.to_numeric(frame[v],errors='coerce');lo,hi=LIMITS[v]
        bad=~frame[v].between(lo,hi);qc[v]={'invalid_hourly_means_removed':int(bad.sum())};frame.loc[bad,v]=np.nan
    # Carry forward the previously flagged 7.22 OD plateau rule, not a newly
    # selected threshold. Index is complete so gaps cannot extend a run.
    all_hours=frame.reindex(pd.date_range(frame.index.min(),frame.index.max(),freq='h'))
    stuck=all_hours.oxygen_mg_l.sub(7.22).abs().lt(1e-8).rolling(8,min_periods=8).sum().eq(8)
    qc['oxygen_mg_l']['previously_flagged_plateau_hours_removed']=int(stuck.sum())
    frame.loc[frame.index.intersection(stuck[stuck].index),'oxygen_mg_l']=np.nan
    hours=[]
    for t,r in frame.iterrows():
        h={'hour_end':t.isoformat(),'available_at':str(r.last_received).replace(' ','T')+'+00:00'}
        for v in SENSORS:h[v]=None if pd.isna(r[v]) else float(r[v])
        hours.append(h)
    return hours,qc

def rows_for(snapshot,hours):
    cohort=snapshot['biometries'][0]['fecha_muestreo']+'T00:00:00+00:00';rows=[]
    for b in snapshot['biometries']:
        t=b['fecha_muestreo']+'T00:00:00+00:00'
        # Retrospective development uses stored measurement order. The actual
        # receipt clock is audited, not silently asserted to have been timely.
        past=[h for h in hours if h['hour_end']<=t]
        f,q=features_from_hours(past,cohort,t,t)
        rows.append({'biometry_id':b['id'],'date':b['fecha_muestreo'],'weight_g':b['sample_mean_g'],
          'sample_n':b['sample_n'],'sample_sd_g':b['sample_sd_g'],
          'sample_se_g':b['sample_sd_g']/math.sqrt(b['sample_n']),'features':f,'quality':q})
    return cohort,rows

def fitted(rows,with_sensors,cohort):
    model,names,warnings=fit_gp(rows,with_sensors);a=export_gp(model,names,rows,warnings)
    a['cohort_start_at']=cohort
    for r in rows:
        x=np.array([[(r['features'][n]-a['centers'][n])/a['scales'][n] for n in names]])
        mu,sd=model.predict(x,return_std=True);portable=predict_gp(a,r['features'])
        assert abs(portable['predicted_mean_weight_g']-mu[0])<1e-7
        assert abs(portable['posterior_sd_g']-sd[0])<1e-7
    return a

def main(args):
    args.out.mkdir(parents=True,exist_ok=True);raw=args.snapshot.read_bytes();s=json.loads(gzip.decompress(raw))
    protocol={'created_before_fit':datetime.now(timezone.utc).isoformat(),
      'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'labels':'one row per observed biometry, no interpolated labels',
      'candidate':'single fixed kernel recipe; three amplitudes optimized by training-only log marginal likelihood',
      'features':'elapsed days; observed T mean, OD p10, pH mean since 7 days before first biometry',
      'normalization':'fixed physical input scales; output mean/std and all fit quantities from training prefix only',
      'sampling_noise':'sample SD squared / sample n for observed weight means; assumes independent representative samples',
      'evaluation':'rolling nowcast; first 3 measured weights train, next one withheld; observed sensor hours through target date allowed',
      'not_a_forecast':'evaluation issue equals target, not previous biometric anchor',
      'known_labels':'all seven labels examined previously: development, not new blind validation',
      'curve':'full-refit posterior reconstruction; uses later biometric labels; not historical forecasts or new ground truth',
      'quality':'physical timezone and receipt availability unverified; late receipts audited; 70% cumulative water coverage',
      'light':'not fitted: only recent sparse history, insufficient paired coverage',
      'feeding':'not fitted: endpoint totals and calculated schedules are not verified timestamped actual feed',
      'deployment':'experimental private candidate; current inference remains blocked until verified source clocks'}
    dump(args.out/'protocol.json',protocol)
    hours,qc=source(s);cohort,rows=rows_for(s,hours);results=[]
    for i in range(3,len(rows)):
        past=rows[:i];r=rows[i]
        yes=fitted(past,True,cohort);no=fitted(past,False,cohort)
        a=predict_gp(yes,r['features']);b=predict_gp(no,r['features'])
        p,q=past[-2:];days=r['features']['elapsed_days']-q['features']['elapsed_days']
        slope=(q['weight_g']-p['weight_g'])/(q['features']['elapsed_days']-p['features']['elapsed_days'])
        results.append({'date':r['date'],'issued_at':r['date'],'actual_weight_g':r['weight_g'],
           'training_dates':[p['date'] for p in past],'training_rows':len(past),
           'gp_with_sensors':a,'gp_time_only':b,'persistence_g':q['weight_g'],
           'recent_trend_g':q['weight_g']+slope*days,'source_quality':r['quality']})
    models={'with_sensors':fitted(rows,True,cohort),'time_only':fitted(rows,False,cohort)}
    metric={'n_dates':len(results),'dates':[r['date'] for r in results],
      'task':'rolling retrospective nowcast; sensors observed through target date',
      'not_blind_validation':True}
    for name in models:
        key='gp_'+name
        errors=[r[key]['predicted_mean_weight_g']-r['actual_weight_g'] for r in results]
        metric[key]={'MAE_g':float(np.mean(np.abs(errors))),'RMSE_g':float(np.sqrt(np.mean(np.square(errors)))),
          'conditional_band_covers_known_mean_count':sum(r[key]['conditional_95_lower_g']<=r['actual_weight_g']<=r[key]['conditional_95_upper_g'] for r in results)}
    for key in ['persistence_g','recent_trend_g']:
        metric[key]={'MAE_g':float(np.mean([abs(r[key]-r['actual_weight_g']) for r in results]))}
    metric['sensor_MAE_improvement_g']=metric['gp_time_only']['MAE_g']-metric['gp_with_sensors']['MAE_g']
    metric['caution']='Four correlated dates cannot establish calibration or generalization; compare only same task/dates.'
    bundle={'model_code':'TILAPIA_GAUSSIAN_GROWTH_BUNDLE','model_version':'0.1.0-gaussian-experimental',
      'created_at':datetime.now(timezone.utc).isoformat(),'cohort_id':2,'pond_id':1,
      'cohort_start_at':cohort,'snapshot_sha256':protocol['snapshot_sha256'],
      'models':models,'development_metrics':metric,'source_quality':qc,
      'clock_alignment_verified':False,'production_ready':False,'activated':False,'uncertainty_calibrated':False}
    dump(args.out/'gaussian_bundle.json',bundle);dump(args.out/'observed_rows.json',rows)
    dump(args.out/'evaluation.json',results);dump(args.out/'metrics.json',metric)
    # Dense posterior estimates: outputs only, no second fit on this curve.
    start=pd.Timestamp(cohort);end=pd.Timestamp(rows[-1]['date'],tz='UTC')
    grid=sorted(set(pd.date_range(start,end,freq='D'))|set(pd.Timestamp(h['hour_end']) for h in hours if start<=pd.Timestamp(h['hour_end'])<=end))
    curve=[]
    for t in grid:
        ti=t.isoformat();past=[h for h in hours if h['hour_end']<=ti]
        f,q=features_from_hours(past,cohort,ti,ti)
        good=all(v>=MIN_COVERAGE for v in q['coverage'].values())
        record={'at':ti,'is_daily':t.hour==0,'estimated_not_measured':True,
          'uses_full_refit_biometries_including_later_dates':True,
          'minimum_water_coverage':min(q['coverage'].values()),
          'max_gap_hours':max(v for v in q['latest_gap_hours'].values() if v is not None),
          'with_sensors':predict_gp(models['with_sensors'],f) if good else None,
          'time_only':predict_gp(models['time_only'],f)}
        curve.append(record)
    dump(args.out/'curve.json',curve)
    bundle['curve_sha256']=hashlib.sha256((args.out/'curve.json').read_bytes()).hexdigest()
    dump(args.out/'gaussian_bundle.json',bundle)
    with (args.out/'curve_hourly_and_daily.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['at','is_daily','estimated_not_measured','minimum_water_coverage','max_gap_hours',
          'gp_sensor_mean_g','gp_sensor_sd_g','gp_sensor_lower_g','gp_sensor_upper_g','gp_time_mean_g'])
        w.writeheader()
        for r in curve:
            p=r['with_sensors'];w.writerow({k:r[k] for k in ['at','is_daily','estimated_not_measured','minimum_water_coverage','max_gap_hours']}|
               {'gp_sensor_mean_g':p['predicted_mean_weight_g'] if p else None,'gp_sensor_sd_g':p['posterior_sd_g'] if p else None,
                'gp_sensor_lower_g':p['conditional_95_lower_g'] if p else None,'gp_sensor_upper_g':p['conditional_95_upper_g'] if p else None,
                'gp_time_mean_g':r['time_only']['predicted_mean_weight_g']})
    dump(args.out/'manifest.json',{'completed_at':datetime.now(timezone.utc).isoformat(),
      'artifact_sha256':hashlib.sha256((args.out/'gaussian_bundle.json').read_bytes()).hexdigest(),
      'trainer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      'core_sha256':hashlib.sha256((Path(__file__).parents[2]/'backend/app/models_engine/ml/gaussian_tilapia_growth.py').read_bytes()).hexdigest(),
      'observed_labels':len(rows),'dense_output_rows':len(curve),'dense_rows_used_as_labels':0})
    print(json.dumps({'metrics':metric,'kernel_fitted':{k:v['kernel'] for k,v in models.items()},'rows':len(curve)},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    main(p.parse_args())
