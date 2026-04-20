"""
Report Generator Service - Excel and PDF Feasibility Reports
Main app factory.
"""

import sys
import os
import logging
from pathlib import Path

service_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(service_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

from fastapi import FastAPI
from core.config import settings
from routers.report_router import router

from core.banner import print_banner as _print_banner
_print_banner()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "report_generator"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

