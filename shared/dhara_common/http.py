import logging
import httpx
from typing import Any, Optional, Dict
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)

class AsyncHTTPClient:
    """Centralized Async HTTP Client with retry logic."""
    def __init__(self, timeout: float = 300.0, headers: Optional[Dict[str, str]] = None):
        self.timeout = timeout
        self.headers = headers or {}
        self._client = httpx.AsyncClient(timeout=timeout, headers=self.headers)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=True
    )
    async def request(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> httpx.Response:
        """Execute HTTP request with retries for transient errors."""
        req_headers = {**self.headers, **(headers or {})}
        try:
            response = await self._client.request(method, url, json=json, headers=req_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTPStatusError for {url}: {e.response.status_code} - {e.response.text}")
            raise e
        except Exception as e:
            logger.warning(f"Request failed to {url}: {e}. Retrying if eligible...")
            raise e

    async def get(self, url: str, **kwargs) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, json: Dict[str, Any], **kwargs) -> httpx.Response:
        return await self.request("POST", url, json=json, **kwargs)
