"""
Site Analysis Service - Google Maps API Integration
Main entry point for FastAPI application.
"""

import logging

from dhara_shared.core.banner import print_banner
from dhara_shared.core.config import validate_config
from dhara_shared.core.exceptions import setup_exception_handlers
from dhara_shared.core.logging import setup_logging, setup_sentry
from dhara_shared.core.metrics import setup_metrics
from dhara_shared.core.tracing import setup_tracing
from fastapi import FastAPI

from .core import settings
from .routers.site_router import router

setup_logging()
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

validate_config(settings, ["GOOGLE_MAPS_API_KEY"])

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)

setup_exception_handlers(app)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "site_analysis"}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
