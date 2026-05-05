import logging

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


async def lifespan(app: FastAPI):
    """Pre-warm expensive resources at startup to reduce first-request latency."""
    import asyncio

    logger.info("Initializing PR Card Scraper...")

    # Ensure DB tables exist before any request arrives
    try:
        from .services.storage import StorageService

        storage = StorageService(settings.DATABASE_URL)
        await asyncio.to_thread(storage._init_db)
        logger.info("PR Card DB tables initialized")
    except Exception as e:
        logger.warning(f"DB init failed (will retry on first request): {e}")

    # Pre-load the ddddocr model so the first CAPTCHA solve is fast
    try:
        from .services.captcha_solver import CaptchaSolver

        solver = CaptchaSolver()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, solver._reader_instance)
        logger.info("ddddocr model pre-loaded successfully")
        # Attach solver to app state so the router can reuse it
        app.state.captcha_solver = solver
    except Exception as e:
        logger.warning(f"ddddocr pre-load failed (will load on first request): {e}")

    yield
    logger.info("Shutting down PR Card Scraper Service...")


validate_config(settings, ["DATABASE_URL"])

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pr_card_scraper"}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
