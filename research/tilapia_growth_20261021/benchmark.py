"""Reproduce the external-only pilot. No local biometric labels are read."""
import csv
import json
from pathlib import Path

from backend.app.models_engine.ml.tilapia_interval_growth import GrowthTrainingInterval, grouped_benchmark

HERE = Path(__file__).resolve().parent


def main():
    raw=list(csv.DictReader((HERE/'data/kamble_2024_tank_intervals.csv').open()))
    rows=[GrowthTrainingInterval(study_id=r['study_id'],cohort_id=r['tank_id'],
        duration_days=float(r['duration_days']),initial_weight_g=float(r['initial_weight_g']),
        final_weight_g=float(r['final_weight_g']),
        temperature_mean_c=float(r['weekly_summary_mean_temperature_c']),
        do_mean_mg_l=float(r['weekly_summary_mean_do_mg_l']),
        source_reference='doi:10.5281/zenodo.11174309 Tables 1,3,8-14') for r in raw]
    groups=[r['treatment'] for r in raw]
    out={name:grouped_benchmark(rows,groups,environmental=env)
         for name,env in [('initial_size_only',False),('initial_size_temperature_oxygen',True)]}
    out['protocol']={'group':'dietary treatment, 7 groups, 3 tanks each',
        'selection':'two predeclared pilots; no hyperparameter search',
        'label':'tank mean at day 60; not individual matched growth',
        'environment':'weekly mean summaries, not daily or hourly forecasts',
        'unresolved':'one external study; no independent farm or study holdout',
        'not_used':['local new/corrected biometrics','Piura environmental covariates (absent)',
                    'Opiyo quarantined interval duration','interpolated weight labels'],
        'production_ready':False}
    (HERE/'benchmark_results.json').write_text(json.dumps(out,indent=2))
    for name in ('initial_size_only','initial_size_temperature_oxygen'):
        print(name,{k:v for k,v in out[name].items() if k!='predictions'})


if __name__=='__main__':main()
