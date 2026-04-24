"""
Dhara AI — Orchestrator Service
Entry point: thin FastAPI app with lifespan, CORS, and router registration.
All business logic lives in dedicated packages (agent/, routers/, services/).
"""

import logging
import os
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

service_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(service_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

from core.banner import print_banner as _print_banner
from core.config import settings
from core.middleware import (
    logging_middleware,
    rate_limit_middleware,
    request_id_middleware,
    response_cache_middleware,
)

from shared.dhara_common.exceptions import setup_exception_handlers
from shared.dhara_common.logging import setup_logging

_print_banner()

setup_logging(loggers=["gateway", "agent", "services"])
logger = logging.getLogger("gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Orchestrator | DB: %s", settings.DATABASE_URL)

    # 1. PostgreSQL
    from db import init_db
    await init_db()

    # 2. Redis
    from services.redis import init_redis
    await init_redis()

    # 3. LLM Client → inject into agent runner
    from agent.llm_client import get_llm_client
    from agent.runner import set_llm_client
    client = get_llm_client()
    set_llm_client(client)
    logger.info("LLM: %s (%s)", type(client).__name__, client.get_model_name())

    # 4. Seed defaults (admin user + roles)
    from db.seed import seed_defaults
    await seed_defaults()

    yield

    # Shutdown
    from db import close_db
    await close_db()
    logger.info("Shutdown complete")


# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Dhara AI",
    version=settings.APP_VERSION,
    description="Dhara AI — Mumbai housing society redevelopment feasibility analysis",
    lifespan=lifespan,
)

# --- Global Exception Handling (using shared lib) ---
setup_exception_handlers(app)

origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Gateway Middlewares ---
app.middleware("http")(request_id_middleware)
app.middleware("http")(logging_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(response_cache_middleware)


# ─── Register Routers ───────────────────────────────────────────────────────

from routers import api_router, ws_router

app.include_router(api_router)
app.include_router(ws_router)


# ─── Health & Info ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Deep Health Check verifying connectivity to critical dependencies and microservices."""
    import httpx

    from services.redis import get_redis

    health_status = {
        "status": "healthy",
        "service": "orchestrator",
        "version": settings.APP_VERSION,
        "timestamp": time.time(),
        "checks": {},
        "microservices": {}
    }

    # 1. Check PostgreSQL
    try:
        from db import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        health_status["checks"]["postgres"] = "UP"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["postgres"] = f"DOWN: {str(e)}"

    # 2. Check Redis
    try:
        redis = get_redis()
        if redis and redis.ping():
            health_status["checks"]["redis"] = "UP"
        else:
            health_status["status"] = "degraded"
            health_status["checks"]["redis"] = "DOWN: Connection failed"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["redis"] = f"DOWN: {str(e)}"

    # 3. Check Downstream Microservices
    services = {
        "site_analysis": settings.SITE_ANALYSIS_URL,
        "aviation_height": settings.HEIGHT_URL,
        "ready_reckoner": settings.READY_RECKONER_URL,
        "report_generator": settings.REPORT_URL,
        "rag_service": settings.RAG_URL,
    }

    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in services.items():
            try:
                # Most services have a /health or /api/health
                check_url = f"{url}/health" if "rag" not in name else f"{url}/api/health"
                resp = await client.get(check_url)
                health_status["microservices"][name] = "UP" if resp.status_code == 200 else f"DOWN ({resp.status_code})"
                if resp.status_code != 200:
                    health_status["status"] = "degraded"
            except Exception:
                health_status["microservices"][name] = "UNREACHABLE"
                health_status["status"] = "degraded"

    return health_status


# ─── Run ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)


