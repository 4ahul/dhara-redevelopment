import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from dhara_shared.dhara_shared.dhara_common.schemas import InternalServiceResponse

logger = logging.getLogger(__name__)

def setup_exception_handlers(app: FastAPI):
    """Register global exception handlers for standardized JSON responses."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception occurred")
        response = InternalServiceResponse(
            status="error",
            error=str(exc),
            metadata={"path": str(request.url.path), "type": exc.__class__.__name__}
        )
        return JSONResponse(status_code=500, content=response.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error: {exc.errors()}")
        response = InternalServiceResponse(
            status="error",
            error="Validation failed",
            data={"details": exc.errors()}
        )
        return JSONResponse(status_code=422, content=response.model_dump())
