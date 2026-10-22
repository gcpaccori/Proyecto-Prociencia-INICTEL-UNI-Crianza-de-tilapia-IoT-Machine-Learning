"""Authenticated experimental service on the private Docker network (no host port)."""
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import secrets
from backend.app.api.v1.tilapia_growth_adaptive import router
from backend.app.api.v1.tilapia_sensor_forecast import router as sensor_router
from backend.app.api.v1.direct_sensor_growth import router as direct_router
from backend.app.api.v1.gaussian_tilapia_growth import router as gaussian_router

os.environ.setdefault("TILAPIA_GROWTH_ADAPTIVE_ARTIFACT", str(Path(__file__).parent/'serving_model.json'))
os.environ.setdefault('TILAPIA_SENSOR_BUNDLE', str(Path(__file__).parent/'sensor_bundle.json'))
os.environ.setdefault('TILAPIA_STACKED_CANDIDATE', str(Path(__file__).parent/'stacked_candidate.json'))
os.environ.setdefault('TILAPIA_DIRECT_GROWTH_BUNDLE', str(Path(__file__).parent/'direct_bundle.json'))
os.environ.setdefault('TILAPIA_GAUSSIAN_BUNDLE', str(Path(__file__).parent/'gaussian_bundle.json'))
os.environ.setdefault('TILAPIA_GAUSSIAN_CURVE', str(Path(__file__).parent/'gaussian_curve.json'))
app = FastAPI(title="Tilapia adaptive growth ML - experimental", version="0.3.0")

@app.middleware('http')
async def private_access(request, call_next):
    key_path = Path(os.environ.get('TILAPIA_GROWTH_API_KEY_FILE', str(Path(__file__).parent/'api.key')))
    try:
        key = key_path.read_text().strip()
    except OSError:
        return JSONResponse({'detail':'Private service key unavailable'}, status_code=503)
    if not key or not secrets.compare_digest(request.headers.get('authorization',''), 'Bearer '+key):
        return JSONResponse({'detail':'Authentication required'}, status_code=401)
    return await call_next(request)

app.include_router(router, prefix="/api/v1")
app.include_router(sensor_router, prefix='/api/v1')
app.include_router(direct_router, prefix='/api/v1')
app.include_router(gaussian_router, prefix='/api/v1')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8013, log_level='warning')
