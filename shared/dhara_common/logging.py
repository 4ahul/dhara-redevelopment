import logging
import json
from datetime import datetime
from typing import Optional

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

def setup_logging(level=logging.INFO, loggers: Optional[list] = None):
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
    default_loggers = ["uvicorn.access", "uvicorn.error", "fastapi"]
    if loggers:
        default_loggers.extend(loggers)
        
    for name in default_loggers:
        l = logging.getLogger(name)
        l.handlers = [handler]
        l.propagate = False
