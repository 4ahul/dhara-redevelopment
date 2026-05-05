import json
import logging
import os
from datetime import UTC, datetime
from typing import Any


class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for production log aggregation.
    """

    def format(self, record):
        log_record: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": os.getenv("APP_NAME", "unknown"),
            "version": os.getenv("APP_VERSION", "unknown"),
            "environment": os.getenv("ENV", "development"),
        }

        # Request context
        for field in ["request_id", "correlation_id", "user_id", "job_id"]:
            val = getattr(record, field, None)
            if val:
                log_record[field] = val

        # Trace context
        if hasattr(record, "trace_id"):
            log_record["trace_id"] = record.trace_id
        if hasattr(record, "span_id"):
            log_record["span_id"] = record.span_id

        # Exception handling
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            log_record["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"

        # Performance metrics
        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms

        return json.dumps(log_record, default=str)


def setup_sentry(service_name: str, dsn: str | None = None):
    """Initializes Sentry for error tracking."""
    import os

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_dsn = dsn or os.getenv("SENTRY_DSN")
    if not sentry_dsn:
        return

    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        environment=os.getenv("ENV", "development"),
        release=f"{service_name}@{os.getenv('APP_VERSION', '1.0.0')}",
    )
    logging.info(f"Sentry Error Tracking enabled for {service_name}")


def setup_logging(level=logging.INFO, loggers: list | None = None):
    """Sets up root logging with JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid double logging
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)

    # Standardize libraries
    default_loggers = ["uvicorn.access", "uvicorn.error", "fastapi", "sqlalchemy.engine", "httpx"]
    if loggers:
        default_loggers.extend(loggers)

    for name in default_loggers:
        named_logger = logging.getLogger(name)
        named_logger.handlers = [handler]
        named_logger.propagate = False


class LogContext:
    """Context manager for adding fields to log records."""

    def __init__(self, **kwargs):
        self.fields = kwargs
        self._old_factory = None

    def __enter__(self):
        self._old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **factory_kwargs):
            record = self._old_factory(*args, **factory_kwargs)
            for key, value in self.fields.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args):
        logging.setLogRecordFactory(self._old_factory)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with context support."""
    return logging.getLogger(name)
