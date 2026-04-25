from dhara_shared.dhara_common.banner import print_banner
from dhara_shared.dhara_common.tracing import setup_tracing
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.pr_card_scraper.core import settings
from services.pr_card_scraper.routers import router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

async def lifespan(app: FastAPI):
    """Pre-warm expensive resources at startup to reduce first-request latency."""
    logger.info("Initializing PR Card Scraper Model...")

    # Pre-load the ddddocr model so the first CAPTCHA solve is fast
    try:
        import asyncio
        from services.pr_card_scraper.logic.captcha_solver import CaptchaSolver
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


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
setup_tracing(app, settings.APP_NAME)

print_banner(settings.APP_NAME)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pr_card_scraper"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)






