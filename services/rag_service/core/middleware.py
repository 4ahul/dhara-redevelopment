import logging
import time as _time

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# --- Rate limiting (in-memory, per-IP) ---
_rate_store: dict[str, list] = {}
_RATE_WINDOW = 60  # seconds
_RATE_LIMITS = {
    "/api/auth/login": 10,
    "/api/auth/register": 5,
    "/api/chat": 30,
    "/api/chat/stream": 30,
}


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    limit = _RATE_LIMITS.get(path)
    if limit and request.client:
        key = f"{request.client.host}:{path}"
        now = _time.time()
        window_start = now - _RATE_WINDOW
        hits = _rate_store.get(key, [])
        hits = [t for t in hits if t > window_start]
        if len(hits) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )
        hits.append(now)
        _rate_store[key] = hits
    return await call_next(request)


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response
