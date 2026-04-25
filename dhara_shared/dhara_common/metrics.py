import logging
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

logger = logging.getLogger(__name__)

def setup_metrics(app: FastAPI, service_name: str):
    """
    Setup Prometheus metrics for a FastAPI service.
    Exposes /metrics endpoint for scraping.
    """
    try:
        # 1. Initialize the instrumentator
        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=True,
            should_instrument_requests_inprogress=True,
            excluded_handlers=[".*admin.*", "/metrics", "/health"],
            env_var_name="ENABLE_METRICS",
        )
        
        # 2. Add default metrics
        instrumentator.instrument(app)
        
        # 3. Expose the /metrics endpoint
        instrumentator.expose(app, endpoint="/metrics", tags=["System"])
        
        logger.info(f"Prometheus Metrics enabled for {service_name} at /metrics")
    except Exception as e:
        logger.warning(f"Failed to initialize metrics: {e}")
