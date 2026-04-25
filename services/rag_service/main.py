from dhara_shared.dhara_common.banner import print_banner
from dhara_shared.dhara_common.tracing import setup_tracing
import os
import logging
from contextlib import asynccontextmanager

# Load local .env before anything else to override global environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from services.rag_service.core.config import settings
from services.rag_service.db.session import init_db, engine
from services.rag_service.core.middleware import rate_limit_middleware, security_headers_middleware
from services.rag_service.routers import chat_router, doc_router, query_router, auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

print_banner(settings.APP_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[STARTUP] Initializing RAG Service...")
    init_db()
    yield
    logger.info("[SHUTDOWN] Disposing database connection pool...")
    engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Redevelopment Management System",
    version=settings.APP_VERSION,
    lifespan=lifespan
)
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
    response = await call_next(request)
    return response

# --- API Endpoints ---

@app.get("/api/health")
async def health_check():
    from datetime import datetime, timezone
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# --- Include Routers ---
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(doc_router.router)
app.include_router(query_router.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8006))
    uvicorn.run(app, host="0.0.0.0", port=port)





