"""Add the authenticated panel; preserve all changed files and the previous Vite build.

Run on vmi2770917 beside the Laravel templates. Does not alter the database,
existing model controller, public Python API or unrelated worktree changes.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
APP = Path('/root/sismapiscis')
SERVING = Path('/root/flask_sismapiscis/aquaculture_backend/backend/research_runs/20261021_growth_adaptive/serving')

def main():
    route = APP/'routes/system/monitoreo.php'
    vue = APP/'resources/js/Pages/Modules/Views/ModelosMl.vue'
    source = vue.read_text()
    marker = '<div class="module-intro__actions">'
    assert source.count(marker) == 1
    addition = '''
                <a :href="'/modelos-ml/crecimiento-ml?piscina_id=' + (form.piscina_id === 'T' ? '1' : form.piscina_id)" class="el-button el-button--primary">Crecimiento ML · experimental</a>'''
    routes = '''
// Experimental growth ML: same authentication and module permission as model dashboard.
Route::get('/modelos-ml/crecimiento-ml', [\\App\\Http\\Controllers\\TilapiaGrowthController::class, 'index'])->name('monitoreo.crecimientoml.index')->middleware('modulo:modelosml');
Route::get('/modelos-ml/crecimiento-ml/datos', [\\App\\Http\\Controllers\\TilapiaGrowthController::class, 'data'])->name('monitoreo.crecimientoml.data')->middleware('modulo:modelosml');
'''
    targets = {
        APP/'app/Http/Controllers/TilapiaGrowthController.php': BASE/'laravel/TilapiaGrowthController.php',
        APP/'resources/views/tilapia-growth.blade.php': BASE/'laravel/tilapia-growth.blade.php',
    }
    for dst, src in targets.items():
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise RuntimeError('Refusing to overwrite another panel implementation: '+str(dst))
    backup = SERVING.parent/('panel_backup_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    backup.mkdir()
    saved = {}
    for p in [route, vue, *targets]:
        if p.exists():
            dst=backup/p.relative_to(APP);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
            saved[str(p.relative_to(APP))] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:saved[str(p.relative_to(APP))] = None
    if (APP/'public/build').exists():shutil.copytree(APP/'public/build',backup/'public/build')
    (backup/'manifest.json').write_text(json.dumps(saved,indent=2))
    for dst,src in targets.items():shutil.copy2(src,dst)
    if '/modelos-ml/crecimiento-ml' not in route.read_text():route.write_text(route.read_text()+routes)
    if 'Crecimiento ML · experimental' not in source:vue.write_text(source.replace(marker,marker+addition,1))
    key=APP/'storage/app/private/tilapia-growth-api.key'
    key.parent.mkdir(parents=True,exist_ok=True)
    raw=(SERVING/'api.key').read_bytes()
    if key.exists() and key.read_bytes()!=raw:raise RuntimeError('Existing panel key differs')
    key.write_bytes(raw);key.chmod(0o640);shutil.chown(key,user='www-data',group='www-data')
    for p in [*targets,route]:
        if p.suffix=='.php':subprocess.run(['docker','exec','sismapiscis_app','php','-l','/var/www/html/'+str(p.relative_to(APP))],check=True)
    subprocess.run(['docker','exec','sismapiscis_app','php','artisan','route:clear'],check=True)
    subprocess.run(['docker','exec','sismapiscis_app','php','artisan','view:clear'],check=True)
    print(json.dumps({'backup':str(backup),'status':'source_installed_build_pending'}))

if __name__ == '__main__':main()
