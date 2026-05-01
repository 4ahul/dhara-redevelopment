"""Shared utilities and models for Dhara AI microservices.

Structured modules:
- dhara_shared.core: config, logging, metrics, tracing, exceptions, banner
- dhara_shared.services: http client, caching, etc.
- dhara_shared.schemas: pydantic models and internal response wrappers
"""

from . import schemas as schemas
from .core import (
    BaseServiceSettings,
    print_banner,
    setup_exception_handlers,
    setup_logging,
    setup_metrics,
    setup_sentry,
    setup_tracing,
    validate_config,
)
from .services import AsyncHTTPClient, redis_cache

__all__ = [
    "BaseServiceSettings",
    "setup_logging",
    "setup_sentry",
    "setup_metrics",
    "setup_tracing",
    "print_banner",
    "setup_exception_handlers",
    "AsyncHTTPClient",
    "redis_cache",
    "validate_config",
    "schemas",
]
