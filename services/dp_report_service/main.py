"""
DP Report Service
FastAPI entry point — attempts to discover MCGM DP zone layer at startup.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core import settings
from routers import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DP Report Service...")

    # Pre-discover the MCGM DP zone ArcGIS layer URL
    try:
        import httpx
        from services.dp_arcgis_client import DPArcGISClient

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
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8009)
