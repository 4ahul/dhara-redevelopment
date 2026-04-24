"""
Site Analysis Service - Google Maps API Integration
Main entry point for FastAPI application.
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
from core import settings
from routers.site_router import router
from shared.dhara_common.logging import setup_logging
from shared.dhara_common.exceptions import setup_exception_handlers

from core.banner import print_banner as _print_banner
_print_banner()

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
setup_exception_handlers(app)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "site_analysis"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
