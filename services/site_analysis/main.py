from dhara_shared.dhara_common.banner import print_banner
import sys, os
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path: sys.path.insert(0, _dir)
_root = os.path.dirname(os.path.dirname(_dir))
if _root not in sys.path: sys.path.append(_root)
import sys
import os
from pathlib import Path

# Fix pathing for standalone execution and internal service imports
SERVICE_ROOT = str(Path(os.path.abspath(__file__)).resolve().parent)
MONOREPO_ROOT = str(Path(SERVICE_ROOT).resolve().parent.parent)

for p in [SERVICE_ROOT, MONOREPO_ROOT]:
    if p not in sys.path:
        sys.path.insert(0, p)
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
from services.site_analysis.core import settings
from services.site_analysis.routers.site_router import router
from dhara_shared.dhara_shared.dhara_common.logging import setup_logging
from dhara_shared.dhara_shared.dhara_common.exceptions import setup_exception_handlers

from services.site_analysis.core.banner import print_banner as _print_banner


setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

print_banner(settings.APP_NAME)

setup_exception_handlers(app)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "site_analysis"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)





