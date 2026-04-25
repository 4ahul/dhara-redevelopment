from dhara_shared.dhara_common.banner import print_banner
from dhara_shared.dhara_common.tracing import setup_tracing
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from services.mcgm_property_lookup.core import settings
from services.mcgm_property_lookup.routers import router

from dhara_shared.dhara_common.logging import setup_logging, setup_sentry
from dhara_shared.dhara_common.exceptions import setup_exception_handlers

print_banner(settings.APP_NAME)

setup_logging()
setup_sentry(settings.APP_NAME)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing MCGM Property Lookup (ArcGIS Layer Discovery)...")

    # Pre-discover the ArcGIS feature layer URL so the first request is fast.
    try:
        import httpx
        from services.mcgm_property_lookup.logic.arcgis_client import ArcGISClient

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
setup_tracing(app, settings.APP_NAME)
setup_exception_handlers(app)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "property_lookup"}

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)










