"""Vercel FastAPI entrypoint.

Vercel autodetects FastAPI when an `app` object is exported from a supported
entrypoint such as `api/main.py`.
"""

from backend.app.main import app
