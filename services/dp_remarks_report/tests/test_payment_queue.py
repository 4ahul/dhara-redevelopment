"""Tests for payment queue and storage payment fields."""
# noqa: E402

import pytest


def test_payment_fields_in_all_fields():
    """StorageService._ALL_FIELDS must include all 4 payment columns."""
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    from services.dp_remarks_report.services.storage import StorageService

    assert "payment_status" in StorageService._ALL_FIELDS
    assert "payment_transaction_id" in StorageService._ALL_FIELDS
    assert "payment_amount" in StorageService._ALL_FIELDS
    assert "payment_paid_at" in StorageService._ALL_FIELDS


from unittest.mock import AsyncMock, patch  # noqa: E402


@pytest.fixture
def mock_redis():
    """Fake redis client that simulates lock acquire/release."""
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)  # lock acquired
    client.delete = AsyncMock(return_value=1)
    client.eval = AsyncMock(return_value=1)
    client.aclose = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_acquire_lock_success(mock_redis):
    """acquire() returns True when Redis SET NX EX succeeds."""
    from services.dp_remarks_report.services.payment_queue import PaymentQueue

    with patch(
        "services.dp_remarks_report.services.payment_queue.redis.from_url", return_value=mock_redis
    ):
        q = PaymentQueue(redis_url="redis://fake:6379/0")
        result = await q.acquire("job-123")
    assert result is True
    mock_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_acquire_lock_timeout(mock_redis):
    """acquire() returns False when lock is held for longer than wait_seconds."""
    mock_redis.set = AsyncMock(return_value=None)  # lock NOT acquired
    from services.dp_remarks_report.services.payment_queue import PaymentQueue

    with patch(
        "services.dp_remarks_report.services.payment_queue.redis.from_url", return_value=mock_redis
    ):
        q = PaymentQueue(redis_url="redis://fake:6379/0", poll_interval=0.01)
        result = await q.acquire("job-123", wait_seconds=0.05)
    assert result is False


@pytest.mark.asyncio
async def test_release_deletes_key(mock_redis):
    """release() calls Redis DELETE on the lock key."""
    from services.dp_remarks_report.services.payment_queue import PaymentQueue

    with patch(
        "services.dp_remarks_report.services.payment_queue.redis.from_url", return_value=mock_redis
    ):
        q = PaymentQueue(redis_url="redis://fake:6379/0")
        await q.acquire("job-abc")
        await q.release("job-abc")
    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_manager_releases_on_exception(mock_redis):
    """Lock is released even when body raises."""
    from services.dp_remarks_report.services.payment_queue import PaymentQueue

    with patch(
        "services.dp_remarks_report.services.payment_queue.redis.from_url", return_value=mock_redis
    ):
        q = PaymentQueue(redis_url="redis://fake:6379/0")
        with pytest.raises(RuntimeError):
            async with q.session("job-xyz"):
                raise RuntimeError("boom")
    mock_redis.eval.assert_awaited()
