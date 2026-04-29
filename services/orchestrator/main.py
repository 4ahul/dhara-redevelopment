"""
Dhara AI — Orchestrator Service
Entry point: thin FastAPI app with lifespan, CORS, and router registration.
All business logic lives in dedicated packages (agent/, routers/, services/).
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from dhara_shared.core.banner import print_banner
from dhara_shared.core.config import validate_config
from dhara_shared.core.exceptions import setup_exception_handlers
from dhara_shared.core.logging import setup_logging, setup_sentry
from dhara_shared.core.metrics import setup_metrics
from dhara_shared.core.tracing import setup_tracing

from .core.config import settings
from .core.middleware import (
    logging_middleware,
    rate_limit_middleware,
    request_id_middleware,
    response_cache_middleware,
)
from .routers import api_router, ws_router

print_banner(settings.APP_NAME)

setup_logging(loggers=["gateway", "agent", "services"])
logger = logging.getLogger("gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Orchestrator | DB: %s", settings.DATABASE_URL)
    try:
        # 1. PostgreSQL
        from .db import init_db
        await init_db()

        # 2. Redis
        from .services.redis import init_redis
        await init_redis()

        # 3. LLM Client → inject into agent runner
        from .agent.llm_client import get_llm_client
        from .agent.runner import set_llm_client

        client = get_llm_client()
        set_llm_client(client)
        logger.info("LLM: %s (%s)", type(client).__name__, client.get_model_name())

        # 4. Seed defaults (admin user + roles)
        from .db.seed import seed_defaults
        await seed_defaults()
    except Exception as e:
        logger.error("Error during Orchestrator initialization: %s", e)
        # We continue to allow the health check to pass so we can debug live
    
    yield

    # Shutdown
    try:
        from .db import close_db
        from .services.redis import close_redis
        await close_db()
        await close_redis()
    except Exception:
        pass
    logger.info("Shutdown complete")


# ─── App ─────────────────────────────────────────────────────────────────────

validate_config(settings, ["GEMINI_API_KEY", "DATABASE_URL", "REDIS_URL", "CLOUDINARY_API_KEY"])

app = FastAPI(
    title="Dhara AI Master Gateway",
    version=settings.APP_VERSION,
    description="Unified API Gateway for Dhara AI Microservice Mesh",
    lifespan=lifespan,
    # Configure the Master Swagger with dropdown for other services
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    swagger_ui_parameters={
        "urls": [
            {"url": "/openapi.json", "name": "Orchestrator (Master)"},
            {"url": "/site-analysis/openapi.json", "name": "Site Analysis"},
            {"url": "/height/openapi.json", "name": "Aviation Height"},
            {"url": "/ready-reckoner/openapi.json", "name": "Ready Reckoner"},
            {"url": "/report/openapi.json", "name": "Report Generator"},
            {"url": "/pr-card/openapi.json", "name": "PR Card Scraper"},
            {"url": "/rag/openapi.json", "name": "RAG Service"},
            {"url": "/mcgm/openapi.json", "name": "MCGM Lookup"},
            {"url": "/dp-remarks/openapi.json", "name": "DP Remarks"},
        ]
    },
)

@app.get("/")
async def root():
    """Root endpoint for basic connectivity check."""
    return {
        "status": "online",
        "service": "orchestrator",
        "message": "Dhara AI Master Gateway is reachable"
    }

setup_sentry(settings.APP_NAME)
setup_metrics(app, settings.APP_NAME)
setup_tracing(app, settings.APP_NAME)

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

app.include_router(api_router)
app.include_router(ws_router)


# ─── Health & Info ───────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Deep Health Check verifying connectivity to critical dependencies and microservices."""
    import httpx

    from .services.redis import get_redis

    health_status = {
        "status": "healthy",
        "service": "orchestrator",
        "version": settings.APP_VERSION,
        "timestamp": time.time(),
        "checks": {},
        "microservices": {},
    }

    # 1. Check PostgreSQL
    try:
        from sqlalchemy import text

        from .db import engine

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
        "pr_card_scraper": settings.PR_CARD_URL,
        "mcgm_property_lookup": settings.MCGM_PROPERTY_URL,
        "dp_remarks_report": settings.DP_REPORT_URL,
    }

    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in services.items():
            try:
                # Most services have a /health or /api/health
                check_url = f"{url}/health" if "rag" not in name else f"{url}/api/health"
                resp = await client.get(check_url)
                health_status["microservices"][name] = (
                    "UP" if resp.status_code == 200 else f"DOWN ({resp.status_code})"
                )
                if resp.status_code != 200:
                    health_status["status"] = "degraded"
            except Exception:
                health_status["microservices"][name] = "UNREACHABLE"
                health_status["status"] = "degraded"

    return health_status


@app.get("/docs/mesh", tags=["System"])
async def get_mesh_docs():
    """Aggregate links to all downstream microservice documentation."""
    return {
        "master": "/docs",
        "services": {
            "site_analysis": f"{settings.SITE_ANALYSIS_URL}/docs",
            "aviation_height": f"{settings.HEIGHT_URL}/docs",
            "ready_reckoner": f"{settings.READY_RECKONER_URL}/docs",
            "report_generator": f"{settings.REPORT_URL}/docs",
            "rag_service": f"{settings.RAG_URL}/docs",
            "pr_card_scraper": f"{settings.PR_CARD_URL}/docs",
            "mcgm_property_lookup": f"{settings.MCGM_PROPERTY_URL}/docs",
            "dp_remarks_report": f"{settings.DP_REPORT_URL}/docs",
        },
        "topology": "Traefik Gateway (experimental) -> Port 80",
    }


# ─── Service Proxy for OpenAPI Endpoints ──────────────────────────────────────

# Add routes that match swagger_ui_parameters expectations
@app.get("/site-analysis/openapi.json")
async def site_analysis_openapi():
    return await proxy_service_openapi("site-analysis")

@app.get("/height/openapi.json")
async def height_openapi():
    return await proxy_service_openapi("height")

@app.get("/ready-reckoner/openapi.json")
async def ready_reckoner_openapi():
    return await proxy_service_openapi("ready-reckoner")

@app.get("/report/openapi.json")
async def report_openapi():
    return await proxy_service_openapi("report")

@app.get("/pr-card/openapi.json")
async def pr_card_openapi():
    return await proxy_service_openapi("pr-card")

@app.get("/mcgm/openapi.json")
async def mcgm_openapi():
    return await proxy_service_openapi("mcgm")

@app.get("/dp-remarks/openapi.json")
async def dp_remarks_openapi():
    return await proxy_service_openapi("dp-remarks")

@app.get("/rag/openapi.json")
async def rag_openapi():
    return await proxy_service_openapi("rag")


# ─── Catch-all Proxy Routes for Interactive Swagger "Try It Out" ───────────────

@app.api_route("/site-analysis/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_site_analysis(path: str, request: Request):
    return await proxy_service(path, "site-analysis", settings.SITE_ANALYSIS_URL, request)

@app.api_route("/height/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_height(path: str, request: Request):
    return await proxy_service(path, "height", settings.HEIGHT_URL, request)

@app.api_route("/ready-reckoner/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_ready_reckoner(path: str, request: Request):
    return await proxy_service(path, "ready-reckoner", settings.READY_RECKONER_URL, request)

@app.api_route("/report/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_report(path: str, request: Request):
    return await proxy_service(path, "report", settings.REPORT_URL, request)

@app.api_route("/pr-card/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_pr_card(path: str, request: Request):
    return await proxy_service(path, "pr-card", settings.PR_CARD_URL, request)

@app.api_route("/mcgm/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_mcgm(path: str, request: Request):
    return await proxy_service(path, "mcgm", settings.MCGM_PROPERTY_URL, request)

@app.api_route("/dp-remarks/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_dp_remarks(path: str, request: Request):
    return await proxy_service(path, "dp-remarks", settings.DP_REPORT_URL, request)

@app.api_route("/rag/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_rag(path: str, request: Request):
    return await proxy_service(path, "rag", settings.RAG_URL, request)


async def proxy_service(path: str, service: str, target_base: str, request: Request):
    """Proxy actual API calls to downstream services."""
    import httpx
    from fastapi import HTTPException
    from starlette.responses import StreamingResponse

    target_url = f"{target_base}/{path}"
    
    # Get request body for POST/PUT/PATCH
    body = await request.body()
    
    # Forward headers (excluding host)
    headers = dict(request.headers)
    headers.pop("host", None)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            proxied = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            
            # Return streaming response to preserve content type
            return StreamingResponse(
                content=proxied.aiter_bytes(),
                status_code=proxied.status_code,
                headers=dict(proxied.headers),
                media_type=proxied.headers.get("content-type"),
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"{service} returned error")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Cannot reach {service}: {str(e)}")


@app.get("/api-docs/{service}/openapi.json")
async def proxy_service_openapi(service: str):
    """Proxy OpenAPI specs from downstream services."""
    import httpx

    service_map = {
        "site-analysis": settings.SITE_ANALYSIS_URL,
        "height": settings.HEIGHT_URL,
        "ready-reckoner": settings.READY_RECKONER_URL,
        "report": settings.REPORT_URL,
        "pr-card": settings.PR_CARD_URL,
        "mcgm": settings.MCGM_PROPERTY_URL,
        "dp-remarks": settings.DP_REPORT_URL,
        "rag": settings.RAG_URL,
        "ocr": settings.OCR_URL,
    }

    target_base = service_map.get(service)
    if not target_base:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{target_base}/openapi.json")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch {service} OpenAPI")
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=502, detail=f"Service unavailable: {service}")


# ─── Run ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
