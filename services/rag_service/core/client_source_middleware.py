import logging
from fastapi import Request
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

async def client_source_middleware(request: Request, call_next):
    """
    Middleware to extract and log the X-Client-Source header.
    """
    client_source = request.headers.get("X-Client-Source")
    if client_source:
        logger.info(f"X-Client-Source: {client_source}")
    else:
        logger.debug("X-Client-Source header not present.")
    
    response = await call_next(request)
    return response