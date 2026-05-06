import logging
import os
from contextlib import asynccontextmanager

from dhara_shared.core.banner import print_banner
from dhara_shared.core.config import validate_config
from dhara_shared.core.tracing import setup_tracing

# Load local .env before anything else to override global environment variables
from dotenv import load_dotenv

load_dotenv(override=True)

from datetime import UTC

from dhara_shared.core.logging import setup_logging, setup_sentry
from dhara_shared.core.metrics import setup_metrics
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .core.config import settings
from .core.middleware import rate_limit_middleware, security_headers_middleware
from .db.session import engine, init_db
from .routers import auth_router, chat_router, doc_router, query_router

setup_logging()
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[STARTUP] Initializing RAG Service...")
    init_db()
    yield
    logger.info("[SHUTDOWN] Disposing database connection pool...")
    engine.dispose()


validate_config(settings, ["DATABASE_URL"])

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Redevelopment Management System",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)

# --- Middleware ---

# 1. Standard Middlewares
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Client-Source"],
)

# 2. Functional Middlewares
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)


@app.middleware("http")
async def client_source_middleware(request: Request, call_next):
    """Identifies if the request came from 'rag-ui' or 'orchestrator'."""
    source = request.headers.get("X-Client-Source", "unknown")
    if source != "unknown":
        logger.info(f"Source: {source} | Request: {request.method} {request.url.path}")
    return await call_next(request)


# --- API Endpoints ---


@app.get("/api/health")
async def health_check():
    from datetime import datetime

    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


# --- Include Routers ---
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(doc_router.router)
app.include_router(query_router.router)

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8006"))
    uvicorn.run(app, host="0.0.0.0", port=port)
# ruff: noqa: E402
