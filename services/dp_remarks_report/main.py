"""
DP Report Service
FastAPI entry point - attempts to discover MCGM DP zone layer at startup.
"""

import logging
from contextlib import asynccontextmanager

from dhara_shared.core.banner import print_banner
from dhara_shared.core.config import validate_config
from dhara_shared.core.logging import setup_logging, setup_sentry
from dhara_shared.core.metrics import setup_metrics
from dhara_shared.core.tracing import setup_tracing
from fastapi import FastAPI

from .core import settings
from .routers import router

setup_logging()
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)
validate_config(settings, [])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing DP Remarks Report (ArcGIS Layer Discovery)...")

    try:
        import httpx

        from .services.dp_arcgis_client import DevelopmentPlanArcGISClient

        async with httpx.AsyncClient() as http:
            client = DevelopmentPlanArcGISClient()
            url = await client.get_active_zone_layer_url(http)
            if url:
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

setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "dp_remarks_report"}


app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8008)
