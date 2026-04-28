import logging

from fastapi import FastAPI

from dhara_shared.core.banner import print_banner
from dhara_shared.core.config import validate_config
from dhara_shared.core.logging import setup_logging, setup_sentry
from dhara_shared.core.metrics import setup_metrics
from dhara_shared.core.tracing import setup_tracing

from .core.config import settings
from .routers.ocr_router import router as ocr_router
from .routers.report_router import router

setup_logging()
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

validate_config(settings, [])

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)
setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "report_generator"}


app.include_router(router)
app.include_router(ocr_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8004)
