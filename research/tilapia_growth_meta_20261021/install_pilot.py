"""Restore this candidate after container recreation, without touching public API."""
from pathlib import Path
import hashlib
import json
import subprocess
import secrets

BASE = Path(__file__).resolve().parent
CONTAINER = 'aquaculture_backend'
DEST = '/app/backend/research_runs/tilapia_growth_adaptive_20261021'
FILES = {
    'adaptive_model.py': '/app/backend/app/models_engine/ml/adaptive_tilapia_growth.py',
    'adaptive_api.py': '/app/backend/app/api/v1/tilapia_growth_adaptive.py',
    'shared_model.py': '/app/backend/app/models_engine/ml/supervised_tilapia_growth.py',
    'sensor_model.py': '/app/backend/app/models_engine/ml/tilapia_sensor_forecast.py',
    'sensor_api.py': '/app/backend/app/api/v1/tilapia_sensor_forecast.py',
    'direct_model.py': '/app/backend/app/models_engine/ml/direct_sensor_growth.py',
    'direct_api.py': '/app/backend/app/api/v1/direct_sensor_growth.py',
}


def run(args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


# Preflight all source files before copying any of them.
for name, target in FILES.items():
    expected = hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    code = 'import pathlib,hashlib;p=pathlib.Path('+repr(target)+');print(hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "missing")'
    found = run(['docker', 'exec', CONTAINER, 'python', '-c', code])
    if found not in ['missing', expected]:
        raise RuntimeError('Refusing to overwrite a different source file: '+target)
for name, target in FILES.items():
    run(['docker', 'cp', str(BASE/name), CONTAINER+':'+target])
run(['docker', 'exec', CONTAINER, 'mkdir', '-p', DEST])
# Preserve first publication time across restart when model contents are identical.
code = '''from pathlib import Path
import json
p=Path('/app/backend/research_runs/tilapia_growth_adaptive_20261021/serving_model.json')
print(p.read_text() if p.exists() else '{}')
'''
previous = json.loads(run(['docker','exec',CONTAINER,'python','-c',code]))
incoming = json.loads((BASE/'serving_model.json').read_text())
prior_time = None
if previous and {k:v for k,v in previous.items() if k!='available_at'} == {k:v for k,v in incoming.items() if k!='available_at'}:
    prior_time = previous.get('available_at')
for name in ['pilot_service.py', 'serving_model.json']:
    run(['docker', 'cp', str(BASE/name), CONTAINER+':'+DEST+'/'+name])
key = BASE/'api.key'
if not key.exists():
    key.write_text(secrets.token_urlsafe(48)); key.chmod(0o600)
run(['docker', 'cp', str(key), CONTAINER+':'+DEST+'/api.key'])
run(['docker', 'exec', CONTAINER, 'chmod', '600', DEST+'/api.key'])
if (BASE/'sensor_bundle.json').exists():
    run(['docker','cp',str(BASE/'sensor_bundle.json'),CONTAINER+':'+DEST+'/sensor_bundle.json'])
if (BASE/'stacked_candidate.json').exists():
    run(['docker','cp',str(BASE/'stacked_candidate.json'),CONTAINER+':'+DEST+'/stacked_candidate.json'])
if (BASE/'direct_bundle.json').exists():
    run(['docker','cp',str(BASE/'direct_bundle.json'),CONTAINER+':'+DEST+'/direct_bundle.json'])
# Use the serving host clock for operational availability, not the analysis host.
code = '''from pathlib import Path
import json
from datetime import datetime,timezone
p=Path('/app/backend/research_runs/tilapia_growth_adaptive_20261021/serving_model.json')
a=json.loads(p.read_text());a['available_at']=PRIOR_TIME or datetime.now(timezone.utc).isoformat();p.write_text(json.dumps(a))
'''
code = code.replace('PRIOR_TIME',repr(prior_time))
run(['docker', 'exec', CONTAINER, 'python', '-c', code])
subprocess.run(['python3',str(BASE/'stop_pilot.py')],check=True)
print('Adaptive candidate installed on private Docker port 8013 with bearer authentication')
