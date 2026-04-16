"""
Report Generator Service
Main app factory.
"""

import sys
import os
from pathlib import Path

# Add the service directory to sys.path to resolve internal imports
service_dir = os.path.dirname(os.path.abspath(__file__))
if service_dir not in sys.path:
    sys.path.append(service_dir)

from fastapi import FastAPI
from core.config import settings
from routers.report_router import router

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "report_generator"}

app.include_router(router)
