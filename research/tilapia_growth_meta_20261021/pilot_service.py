"""Private ML candidate service; no existing public applications are restarted."""
from pathlib import Path
import os

from fastapi import FastAPI
from backend.app.api.v1.tilapia_growth_adaptive import router

os.environ.setdefault("TILAPIA_GROWTH_ADAPTIVE_ARTIFACT", str(Path(__file__).parent/'serving_model.json'))
app = FastAPI(title="Tilapia adaptive growth ML - experimental", version="0.3.0")
app.include_router(router, prefix="/api/v1")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8013, log_level='warning')
