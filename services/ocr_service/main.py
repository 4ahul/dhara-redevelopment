"""
OCR Service - Municipal Document Extraction via MuniScan
Main entry point for FastAPI application.
"""

import logging

from fastapi import FastAPI

from dhara_shared.core.logging import setup_logging, setup_sentry
from dhara_shared.core.metrics import setup_metrics
from dhara_shared.core.tracing import setup_tracing

from .core import settings
from .routers import router

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "ocr_service"}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8009)
