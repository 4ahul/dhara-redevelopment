"""
PR Card Scraper Service
Main entry point for Mahabhumi Bhulekh PR Card automation.
"""

import sys
import os
import logging
from contextlib import asynccontextmanager

service_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(service_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

from fastapi import FastAPI

from core import settings
from routers import router

from core.banner import print_banner as _print_banner
_print_banner()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm expensive resources at startup to reduce first-request latency."""
    logger.info("Initializing PR Card Scraper Model...")

    # Pre-load the ddddocr model so the first CAPTCHA solve is fast
    try:
        import asyncio
        from services.captcha_solver import CaptchaSolver
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

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "pr_card_scraper"}

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
