import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dhara_shared.schemas import InternalServiceResponse

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI):
    """Register global exception handlers for standardized JSON responses."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception occurred")
        response = InternalServiceResponse(
            status="error",
            error=str(exc),
            metadata={"path": str(request.url.path), "type": exc.__class__.__name__},
        )
        return JSONResponse(status_code=500, content=response.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(f"Validation error: {exc.errors()}")
        # Convert errors to JSON-serializable format
        details = []
        for err in exc.errors():
            err_dict = dict(err)
            if "ctx" in err_dict and "error" in err_dict["ctx"]:
                err_dict["ctx"]["error"] = str(err_dict["ctx"]["error"])
            details.append(err_dict)
        response = InternalServiceResponse(
            status="error", error="Validation failed", data={"details": details}
        )
        return JSONResponse(status_code=422, content=response.model_dump())
