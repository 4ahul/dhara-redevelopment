import json
import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from services.redis import get_redis

logger = logging.getLogger("gateway")

async def request_id_middleware(request: Request, call_next):
    """Assigns a unique ID to every request for cross-service tracking."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

async def logging_middleware(request: Request, call_next):
    """Logs request details, duration, and status codes."""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    request_id = getattr(request.state, "request_id", "N/A")

    logger.info(
        f"{request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration:.4f}s",
        extra={"request_id": request_id}
    )

    return response

# --- Redis-Powered Rate Limiting & Caching ---
_RATE_WINDOW = 60 # seconds
_DEFAULT_LIMIT = 100 # requests per window
_CACHE_TTL = 300 # 5 minutes

async def rate_limit_middleware(request: Request, call_next):
    """Prevents abuse by limiting requests per IP using Redis."""
    redis = get_redis()
    if not redis or not request.client:
        return await call_next(request)

    client_ip = request.client.host
    now = int(time.time())
    key = f"rl:{client_ip}:{now // _RATE_WINDOW}"

    try:
        # Atomic increment and expire
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, _RATE_WINDOW)
        hits, _ = pipe.execute()

        if hits > _DEFAULT_LIMIT:
            request_id = getattr(request.state, "request_id", "N/A")
            logger.warning(f"RID: {request_id} | Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later.", "request_id": request_id}
            )
    except Exception as e:
        logger.error(f"Rate limiter error: {e}")
        # Fallback to allow request if Redis fails

    return await call_next(request)

async def response_cache_middleware(request: Request, call_next):
    """Caches idempotent GET requests in the Gateway for high performance."""
    redis = get_redis()
    # Cache only GET requests to public API paths that are often repeated
    cacheable_paths = ["/api/v1/ready-reckoner", "/api/v1/premium"]

    is_cacheable = (
        request.method == "GET" and
        any(request.url.path.startswith(p) for p in cacheable_paths) and
        redis is not None
    )

    if not is_cacheable:
        return await call_next(request)

    # Generate cache key based on full URL (including query params)
    cache_key = f"cache:{request.url.path}:{hash(str(request.query_params))}"

    try:
        cached_res = redis.get(cache_key)
        if cached_res:
            data = json.loads(cached_res)
            request_id = getattr(request.state, "request_id", "gateway-cached")
            logger.info(f"RID: {request_id} | Cache HIT | {request.url.path}")
            return Response(
                content=data["content"],
                status_code=data["status"],
                media_type=data["media_type"],
                headers={"X-Cache": "HIT", "X-Request-ID": request_id}
            )
    except Exception as e:
        logger.error(f"Cache retrieval error: {e}")

    # Process request normally
    response = await call_next(request)

    # Store in cache if successful (200 OK)
    if response.status_code == 200:
        try:
            # We can only cache responses with body
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            cache_data = {
                "content": body.decode("utf-8") if isinstance(body, bytes) else body,
                "status": response.status_code,
                "media_type": response.media_type
            }
            redis.setex(cache_key, _CACHE_TTL, json.dumps(cache_data))

            # Re-create response for the caller since we consumed the stream
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        except Exception as e:
            logger.error(f"Cache storage error: {e}")

    return response


