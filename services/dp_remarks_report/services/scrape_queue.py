"""Redis distributed lock for serializing DPRMarks portal scraping."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_LOCK_KEY = "dp_remarks:scrape_lock"
_LOCK_TTL = 900  # seconds — covers 15 min max browser timeout


class ScrapeQueue:
    """
    Async Redis lock. Only one scrape runs at a time across all instances
    to avoid portal "Already logged in" errors.

    Usage:
        q = ScrapeQueue(redis_url=settings.REDIS_URL)
        async with q.session("job-id"):
            ... do scrape ...
    """

    def __init__(
        self,
        redis_url: str,
        poll_interval: float = 2.0,
    ):
        self._client: redis.Redis = redis.from_url(redis_url, decode_responses=True)
        self._poll_interval = poll_interval

    async def acquire(self, job_id: str, wait_seconds: int = 600) -> bool:
        """
        Block until lock acquired or wait_seconds exceeded.
        Returns True if acquired, False on timeout.
        """
        elapsed = 0.0
        while elapsed < wait_seconds:
            ok = await self._client.set(
                _LOCK_KEY,
                job_id,
                nx=True,  # only set if key does NOT exist
                ex=_LOCK_TTL,  # auto-expire so crashes don't deadlock
            )
            if ok:
                logger.info("Scrape lock acquired for job %s", job_id)
                return True
            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval
        logger.warning("Scrape lock timeout for job %s after %ss", job_id, wait_seconds)
        return False

    _RELEASE_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

    async def release(self, job_id: str) -> None:
        """Release the lock — only deletes if we still own it."""
        try:
            await self._client.eval(self._RELEASE_SCRIPT, 1, _LOCK_KEY, job_id)
            logger.info("Scrape lock released for job %s", job_id)
        except Exception as e:
            logger.warning("Failed to release scrape lock: %s", e)

    @asynccontextmanager
    async def session(self, job_id: str, wait_seconds: int = 600):
        """Context manager — always releases lock even on exception."""
        acquired = await self.acquire(job_id, wait_seconds)
        if not acquired:
            raise RuntimeError(f"Scrape queue wait exceeded {wait_seconds}s for job {job_id}")
        try:
            yield
        finally:
            await self.release(job_id)

    async def close(self) -> None:
        await self._client.aclose()
