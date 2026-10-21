"""Loopback-only service for testing the executed artifact on the actual host.

Existing backend applications are not restarted. This process has no DB writes.
"""
from fastapi import FastAPI
from backend.app.api.v1.tilapia_growth_ml import router

app=FastAPI(title="Tilapia supervised growth - experimental",version="0.2.0")
app.include_router(router,prefix="/api/v1")

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=8012,log_level="warning")
