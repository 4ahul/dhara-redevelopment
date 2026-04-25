from dhara_shared.dhara_common.banner import print_banner
"""
DP Report Service
FastAPI entry point - attempts to discover MCGM DP zone layer at startup.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.dp_remarks_report.core import settings
from services.dp_remarks_report.routers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing DP Remarks Report (ArcGIS Layer Discovery)...")

    # Pre-discover the MCGM DP zone ArcGIS layer URL
    try:
        import httpx
        from services.dp_remarks_report.logic.dp_arcgis_client import DPArcGISClient

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










