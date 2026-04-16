"""
MCGM Property Lookup Service
FastAPI entry point — ArcGIS layer URL is discovered at startup.
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
    logger.info("Starting MCGM Property Lookup Service...")

    # Pre-discover the ArcGIS feature layer URL so the first request is fast.
    try:
        import httpx
        from services.arcgis_client import ArcGISClient

        async with httpx.AsyncClient() as http:
            client = ArcGISClient()
            url = await client.discover_layer_url(http)
            if url:
                ArcGISClient._layer_url = url
                logger.info("ArcGIS layer URL discovered: %s", url)
            else:
                logger.warning(
                    "Could not discover ArcGIS layer URL — direct API queries will be skipped, "
                    "browser scraper will be used as primary method"
                )
    except Exception as e:
        logger.warning("ArcGIS layer discovery failed at startup: %s", e)

    yield
    logger.info("Shutting down MCGM Property Lookup Service...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8008)
