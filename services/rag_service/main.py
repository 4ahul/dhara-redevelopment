"""
Dhara RAG Service
Main entry point for PMC, Builder, Society, DDR operations.
"""

import sys
import os
import secrets
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Add the service directory to sys.path to resolve internal imports
service_dir = os.path.dirname(os.path.abspath(__file__))
if service_dir not in sys.path:
    sys.path.append(service_dir)

from core.middleware import rate_limit_middleware, security_headers_middleware
from db.session import init_db, engine
from routers import auth_router, chat_router, utility_router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing RAG Service...")
    try:
        init_db()
    except Exception as e:
        logger.error(f"Database init failed: {e}")
    
    yield
    # Shutdown
    logger.info("Disposing database connection pool...")
    engine.dispose()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="Dhara AI RAG API",
    description="Dhara AI — Backend API for Redevelopment Management System",
    version="2.0.0",
    lifespan=lifespan
)

# Authentication & Sessions
session_secret = os.environ.get("SESSION_SECRET", secrets.token_hex(32))
app.add_middleware(SessionMiddleware, secret_key=session_secret)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Expand as needed for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "rag_service"}

# Routers
app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(utility_router.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
