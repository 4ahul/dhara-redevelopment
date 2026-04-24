import logging
import time
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("gateway.exceptions")

async def global_exception_handler(request: Request, exc: Exception):
    """
    Standardizes all errors in the Orchestrator (Gateway).
    Returns a consistent JSON schema for UI and monitoring.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    if isinstance(exc, HTTPException):
        status_code = exc.status_code
        message = exc.detail
        error_type = "HTTP_EXCEPTION"
    else:
        status_code = 500
        message = "Internal Server Error"
        error_type = "INTERNAL_ERROR"
        # Log unexpected errors with full stack trace for debugging
        logger.exception(f"RID: {request_id} | Unhandled error: {exc}")

    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_type,
            "message": message,
            "status_code": status_code,
            "request_id": request_id,
            "timestamp": time.time(),
        }
    )

def setup_exception_handlers(app):
    """Registers the global handler to a FastAPI app."""
    @app.exception_handler(Exception)
    async def universal_handler(request: Request, exc: Exception):
        return await global_exception_handler(request, exc)

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException):
        return await global_exception_handler(request, exc)


