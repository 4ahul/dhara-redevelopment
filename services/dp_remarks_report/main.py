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
DP Report Service
FastAPI entry point - attempts to discover MCGM DP zone layer at startup.
"""

import sys
import os
import logging
from contextlib import asynccontextmanager

service_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(service_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir); sys.path.insert(0, os.path.join(service_dir, 'services'))

from fastapi import FastAPI

from services.dp_remarks_report.core import settings
from services.dp_remarks_report.routers import router

from services.dp_remarks_report.core.banner import print_banner as _print_banner


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing DP Remarks Report (ArcGIS Layer Discovery)...")

    # Pre-discover the MCGM DP zone ArcGIS layer URL
    try:
        import httpx
        from services.dp_remarks_report.services.dp_arcgis_client import DPArcGISClient

        async with httpx.AsyncClient() as http:
            client = DPArcGISClient()
            url = await client.discover_zone_layer(http)
            if url:
                DPArcGISClient._zone_layer_url = url
                logger.info("DP zone layer URL discovered: %s", url)
            else:
                logger.warning(
                    "Could not discover DP zone layer URL — "
                    "browser scraper will be used as primary method"
                )
    except Exception as e:
        logger.warning("DP zone layer discovery failed at startup: %s", e)

    yield
    logger.info("Shutting down DP Report Service...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "dp_remarks_report"}

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)









