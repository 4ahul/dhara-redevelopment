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

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="Dhara AI Master Gateway",
    version=settings.APP_VERSION,
    description="Unified API Gateway for Dhara AI Microservice Mesh",
    lifespan=lifespan,
    openapi_url="/openapi.json",
    docs_url=None,  # Disable default /docs
    redoc_url="/redoc",
)

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """
    Custom Swagger UI that supports multiple OpenAPI specs via a dropdown.
    Requires StandaloneLayout and StandalonePreset.
    """
    import json
    
    urls = [
        {"url": "/openapi.json", "name": "Orchestrator (Master)"},
        {"url": "/api-docs/site-analysis/openapi.json", "name": "Site Analysis"},
        {"url": "/api-docs/height/openapi.json", "name": "Aviation Height"},
        {"url": "/api-docs/ready-reckoner/openapi.json", "name": "Ready Reckoner"},
        {"url": "/api-docs/report/openapi.json", "name": "Report Generator"},
        {"url": "/api-docs/pr-card/openapi.json", "name": "PR Card Scraper"},
        {"url": "/api-docs/rag/openapi.json", "name": "RAG Service"},
        {"url": "/api-docs/mcgm/openapi.json", "name": "MCGM Lookup"},
        {"url": "/api-docs/dp-remarks/openapi.json", "name": "DP Remarks"},
        {"url": "/api-docs/ocr/openapi.json", "name": "OCR Service"},
    ]
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>{app.title}</title>
      <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css" >
      <link rel="icon" type="image/png" href="https://fastapi.tiangolo.com/img/favicon.png">
      <style>
        html {{ box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }}
        *, *:before, *:after {{ box-sizing: inherit; }}
        body {{ margin:0; background: #fafafa; }}
        .swagger-ui .topbar {{ background-color: #1b1b1b; padding: 10px 0; }}
        .swagger-ui .topbar-wrapper {{ max-width: 1460px; margin: 0 auto; padding: 0 20px; }}
        .swagger-ui .topbar .link {{ display: none; }}
      </style>
    </head>
    <body>
      <div id="swagger-ui"></div>
      <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"> </script>
      <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"> </script>
      <script>
        window.onload = function() {{
          window.ui = SwaggerUIBundle({{
            urls: {json.dumps(urls)},
            dom_id: '#swagger-ui',
            deepLinking: true,
            presets: [
              SwaggerUIBundle.presets.apis,
              SwaggerUIStandalonePreset
            ],
            plugins: [
              SwaggerUIBundle.plugins.DownloadUrl
            ],
            layout: "StandaloneLayout",
            persistAuthorization: true,
            displayRequestDuration: true,
            filter: true
          }})
        }}
      </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

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


# ─── Service Proxy for OpenAPI Endpoints ──────────────────────────────────────

SERVICE_MAP = {
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

@app.get("/api-docs/{service}/openapi.json")
async def proxy_service_openapi(service: str, request: Request):
    """Proxy OpenAPI specs from downstream services and rewrite servers for gateway routing."""
    import httpx
    from fastapi import HTTPException

    target_base = SERVICE_MAP.get(service)
    if not target_base:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{target_base}/openapi.json")
            response.raise_for_status()
            spec = response.json()
            
            # Rewrite "servers" so Swagger UI calls go through the gateway
            spec["servers"] = [{"url": f"/{service}", "description": f"Proxied {service}"}]
            
            return spec
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=f"Failed to fetch {service} OpenAPI")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Service unavailable: {service}")


# ─── Catch-all Proxy Routes for Interactive Swagger "Try It Out" ───────────────

@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all_proxy(service: str, path: str, request: Request):
    """Generic catch-all proxy that routes /{service}/* to the correct microservice."""
    from fastapi import HTTPException
    
    target_base = SERVICE_MAP.get(service)
    if not target_base:
        # If it's not a proxied service, FastAPI will fall back to other routes
        # Raise 404 only if it's clearly intended for a microservice but not found
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
        
    return await proxy_service(path, service, target_base, request)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
