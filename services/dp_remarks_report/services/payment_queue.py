"""Redis distributed lock for serializing CCAvenue payments."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_LOCK_KEY = "dp_remarks:payment_lock"
_LOCK_TTL = 360  # seconds — covers 5 min UPI timeout + buffer


class PaymentQueue:
    """
    Async Redis lock. Only one payment runs at a time across all instances.

    Usage:
        q = PaymentQueue(redis_url=settings.REDIS_URL)
        acquired = await q.acquire("job-id", wait_seconds=600)
        if not acquired:
            raise RuntimeError("payment queue timeout")
        try:
            ... do payment ...
        finally:
            await q.release("job-id")

    Or via context manager:
        async with q.session("job-id"):
            ... do payment ...
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
                logger.info("Payment lock acquired for job %s", job_id)
                return True
            await asyncio.sleep(self._poll_interval)
            elapsed += self._poll_interval
        logger.warning("Payment lock timeout for job %s after %ss", job_id, wait_seconds)
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
        await self._client.eval(self._RELEASE_SCRIPT, 1, _LOCK_KEY, job_id)
        logger.info("Payment lock released for job %s", job_id)

    @asynccontextmanager
    async def session(self, job_id: str, wait_seconds: int = 600):
        """Context manager — always releases lock even on exception."""
        acquired = await self.acquire(job_id, wait_seconds)
        if not acquired:
            raise RuntimeError(f"Payment queue wait exceeded {wait_seconds}s for job {job_id}")
        try:
            yield
        finally:
            await self.release(job_id)

    async def close(self) -> None:
        await self._client.aclose()
