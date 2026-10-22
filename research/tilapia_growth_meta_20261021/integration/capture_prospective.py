"""Host-side hourly append-only audit, with independent growth and sensor outcomes.

No label updates, no refits. A blocked sensor is an audit record, not a forecast.
Run beside api.key on the trusted host; files remain private and dated in UTC.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

BASE = Path(__file__).resolve().parent

CAPTURE = r'''
import json, urllib.request, urllib.error
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import text
from backend.app.core.database import engine
from backend.app.core.config import get_settings
now=datetime.now(timezone.utc)
key=Path('/app/backend/research_runs/tilapia_growth_adaptive_20261021/api.key').read_text().strip()
def call(url,method='GET',private=False):
    headers={'Authorization':'Bearer '+key} if private else {}
    req=urllib.request.Request(url,method=method,headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=40) as r:return {'http_status':r.status,'body':json.load(r)}
    except urllib.error.HTTPError as e:return {'http_status':e.code,'error':'service_error'}
    except Exception as e:return {'error':type(e).__name__}
schema=get_settings().legacy_database_name
assert schema and schema.replace('_','').isalnum()
with engine.connect() as c:
    water=c.execute(text(f'SELECT id,fecha_medicion,created_at,temperatura,ph,oxigeno_disuelto FROM {schema}.parametro_aguas WHERE piscina_id=1 AND deleted_at IS NULL ORDER BY fecha_medicion DESC,id DESC LIMIT 1')).mappings().first()
    received=c.execute(text(f'SELECT id,fecha_medicion,created_at FROM {schema}.parametro_aguas WHERE piscina_id=1 AND deleted_at IS NULL ORDER BY created_at DESC,id DESC LIMIT 1')).mappings().first()
    light=c.execute(text(f'SELECT id,fecha_medicion,created_at,iluminancia FROM {schema}.parametro_ambientes WHERE piscina_id=1 ORDER BY fecha_medicion DESC,id DESC LIMIT 1')).mappings().first()
    light_received=c.execute(text(f'SELECT id,fecha_medicion,created_at FROM {schema}.parametro_ambientes WHERE piscina_id=1 ORDER BY created_at DESC,id DESC LIMIT 1')).mappings().first()
result={'recorded_at':now.isoformat(),'pond_id':1,'source_schema':schema,
 'clock_alignment_verified':False,'water_latest_measurement':dict(water) if water else None,
 'water_latest_received':dict(received) if received else None,
 'light_latest_measurement':dict(light) if light else None,
 'light_latest_received':dict(light_received) if light_received else None,
 'growth_forecasts':[call('http://127.0.0.1:8013/api/v1/ponds/1/models/tilapia-growth-adaptive/forecast?projection_days='+str(d),private=True) for d in [7,14,28]],
 'trained_sensor_bundle':call('http://127.0.0.1:8013/api/v1/models/tilapia-sensor-forecast/status',private=True),
 'trained_stack_candidate':call('http://127.0.0.1:8013/api/v1/models/tilapia-sensor-forecast/stack-status',private=True),
 'direct_sensor_growth':call('http://127.0.0.1:8013/api/v1/models/tilapia-growth-direct/status',private=True),
 'oxygen_existing_model':call('http://127.0.0.1:8000/api/v1/ponds/1/models/svm-od/forecast',method='POST'),
 'sensor_fusion':{'status':'blocked','eligible_forecasts':{},'reasons':[
 'measurement_and_receipt_clock_alignment_unverified',
 'existing_oxygen_target_1h_does_not_equal_next_24h_mean',
 'no_verified_current_24h_forecasts_for_temperature_ph_light',
 'growth_artifact_has_no_sensor_features']},
 'biological_validation':'pending_future_observed_biometries'}
if result['oxygen_existing_model'].get('body',{}).get('status')=='not_ready':
    result['sensor_fusion']['reasons'].append('oxygen_model_no_active_asset')
print(json.dumps(result,default=str,allow_nan=False))
'''


def main():
    proc = subprocess.run(['docker','exec','-i','-e','PYTHONPATH=/app','aquaculture_backend','python','-'],
                          input=CAPTURE,text=True,capture_output=True,timeout=220,check=True)
    record = json.loads(proc.stdout)
    record['collector_version'] = '0.1.0'
    record['collector_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    raw = json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False).encode()
    out = BASE/'prospective'
    out.mkdir(mode=0o700,exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    path = out/(stamp+'.json')
    with path.open('xb') as f:f.write(raw)
    path.chmod(0o600)
    with path.with_suffix('.sha256').open('x') as f:f.write(hashlib.sha256(raw).hexdigest()+'  '+path.name+'\n')
    print(json.dumps({'saved':path.name,'sha256':hashlib.sha256(raw).hexdigest(),
        'growth_http':[r.get('http_status') for r in record['growth_forecasts']],
        'oxygen_http':record['oxygen_existing_model'].get('http_status'),
        'sensor_fusion':record['sensor_fusion']['status']}))


if __name__ == '__main__':main()
