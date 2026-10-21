"""Restore only this loopback pilot after container/host restarts.

Run on the authorized host from the private serving bundle. Refuses to overwrite
different source files; stops only the exact pilot process, never the main API.
"""
from pathlib import Path
import hashlib
import json
import subprocess
from datetime import datetime,timezone

BASE=Path(__file__).resolve().parent
CONTAINER="aquaculture_backend"
DEST="/app/backend/research_runs/tilapia_execution_20261021"

def run(args):return subprocess.run(args,check=True,text=True,capture_output=True).stdout.strip()

for name,target in [("model.py","/app/backend/app/models_engine/ml/supervised_tilapia_growth.py"),
                    ("api_v2.py","/app/backend/app/api/v1/tilapia_growth_ml.py")]:
    expected=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    code="import pathlib,hashlib;p=pathlib.Path("+repr(target)+");print(hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else 'missing')"
    found=run(["docker","exec",CONTAINER,"python","-c",code])
    if found not in ["missing",expected]:raise RuntimeError("Refusing to overwrite different source: "+target)
    run(["docker","cp",str(BASE/name),CONTAINER+":"+target])
run(["docker","exec",CONTAINER,"mkdir","-p",DEST])
for name in ["pilot_service.py","growth_models.json","refitted_candidate_models.json",
             "api_request_example.json","readiness.json","local_metrics.json"]:
    run(["docker","cp",str(BASE/name),CONTAINER+":"+DEST+"/"+name])
code="""import pathlib,json
from datetime import datetime,timezone
p=pathlib.Path('/app/backend/research_runs/tilapia_execution_20261021')
models=json.loads((p/'refitted_candidate_models.json').read_text())
for a in models.values():
 a['available_at']=datetime.now(timezone.utc).isoformat()
 a['training_local_biometry_cutoff']='2026-10-16'
(p/'serving_models.json').write_text(json.dumps(models))
"""
run(["docker","exec",CONTAINER,"python","-c",code])
subprocess.run(["python3",str(BASE/"stop_pilot.py")],check=True)
print("Executed supervised-growth artifact installed; loopback pilot only")
