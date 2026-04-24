import json
import logging
from datetime import datetime


class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings for production log aggregation.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "request_id": getattr(record, "request_id", "N/A"),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logging():
    """Sets up root logging with JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove existing handlers to avoid double logging
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)

    # Standardize libraries
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]
    logging.getLogger("gateway").handlers = [handler]


