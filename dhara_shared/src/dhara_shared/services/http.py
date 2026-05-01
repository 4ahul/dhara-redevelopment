import logging
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple in-memory circuit breaker to prevent cascading failures."""

    _registry = {}  # host -> breaker instance

    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # OPEN, CLOSED, HALF-OPEN

    @classmethod
    def get_for_host(cls, host: str):
        if host not in cls._registry:
            cls._registry[host] = cls()
        return cls._registry[host]

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error("Circuit Breaker OPEN for host. Threshold reached.")

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def can_request(self) -> bool:
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
                return True
            return False

        if self.state == "HALF-OPEN":
            return True

        return True


class AsyncHTTPClient:
    """Centralized Async HTTP Client with retry logic, Trace ID propagation, and Circuit Breaker."""

    def __init__(
        self,
        timeout: float = 300.0,
        headers: dict[str, str] | None = None,
        request_id: str | None = None,
    ):
        self.timeout = timeout
        self.headers = headers or {}
        if request_id:
            self.headers["X-Request-ID"] = request_id
        # We don't pre-create self._client here because we want a clean client per 'async with' context
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True,
    )
    async def request(
        self,
        method: str,
        url: str,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        """Execute HTTP request with retries and circuit breaker."""
        from urllib.parse import urlparse

        host = urlparse(url).netloc
        breaker = CircuitBreaker.get_for_host(host)

        if not breaker.can_request():
            logger.warning(f"Circuit Breaker is OPEN for {host}. Skipping request to {url}.")
            raise httpx.RequestError(f"Circuit Breaker is OPEN for {host}")

        req_headers = {**self.headers, **(headers or {})}
        try:
            response = await self._client.request(
                method, url, json=json, headers=req_headers, timeout=timeout
            )

            # If server error, it counts as a failure for the breaker
            if response.status_code >= 500:
                breaker.record_failure()
            else:
                breaker.record_success()

            response.raise_for_status()
            return response
        except (httpx.RequestError, httpx.TimeoutException) as e:
            breaker.record_failure()
            logger.warning(f"Request failed to {url}: {e}. Retrying if eligible...")
            raise e from e
        except Exception as e:
            # Other errors don't necessarily trigger the breaker but we still log
            logger.error(f"Unexpected error for {url}: {e}")
            raise e from e

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, json: dict[str, Any], **kwargs) -> httpx.Response:
        return await self.request("POST", url, json=json, **kwargs)
