"""Portable inference for trained sensor candidates; not biometric validation."""
from __future__ import annotations

import math
from backend.app.models_engine.ml.supervised_tilapia_growth import portable_regression

RANGES = {'temperature_c': (0., 50.), 'oxygen_mg_l': (0., 30.), 'ph': (0., 14.),
          'light_lux': (0., 200000.), 'nitrate_native_units': (0., 999999.99)}
# Nitrate upper bound is the DECIMAL(8,2) storage bound, not a physical-unit claim.


def export_sensor_pipeline(model, feature_names):
    im, scale, reg = [model.named_steps[k] for k in ['impute','scale','reg']]
    out = {'feature_names': list(feature_names), 'impute_values': im.statistics_.tolist(),
           'means': scale.mean_.tolist(), 'scales': scale.scale_.tolist()}
    if hasattr(reg, 'coef_'):
        out['regressor'] = {'kind':'linear', 'coefficients':reg.coef_.tolist(),
                            'intercept':float(reg.intercept_)}
    else:
        out['regressor'] = {'kind':'forest', 'trees':[
            {'left':t.tree_.children_left.tolist(), 'right':t.tree_.children_right.tolist(),
             'feature':t.tree_.feature.tolist(), 'threshold':t.tree_.threshold.tolist(),
             'value':t.tree_.value[:,0,0].tolist()} for t in reg.estimators_]}
    return out


def predict_sensor(asset: dict, features: dict, variable: str) -> float:
    if variable not in RANGES:raise ValueError('Unknown sensor variable')
    values=[]
    for i,name in enumerate(asset['feature_names']):
        v=features.get(name)
        v=float('nan') if v is None else float(v)
        if math.isinf(v):raise ValueError('Infinite sensor feature')
        if math.isnan(v):v=asset['impute_values'][i]
        values.append((v-asset['means'][i])/asset['scales'][i])
    result=portable_regression(asset['regressor'],values)
    if not math.isfinite(result):raise ValueError('Unstable sensor prediction')
    low,high=RANGES[variable]
    return min(high,max(low,result))
