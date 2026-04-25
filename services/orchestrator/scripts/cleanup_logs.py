"""
Dhara AI — Database Cleanup Script
Purges audit logs and stale report data to maintain performance.
Usage: uv run python services/orchestrator/scripts/cleanup_logs.py --days 30
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta

from services.orchestrator.db import async_session_factory
from services.orchestrator.models import AuditLog
from sqlalchemy import delete

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cleanup")

async def cleanup_logs(days: int):
    """Delete audit logs older than N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    logger.info(f"Cleaning up logs older than {days} days (cutoff: {cutoff})")

    try:
        async with async_session_factory() as db:
            stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
            result = await db.execute(stmt)
            await db.commit()
            logger.info(f"Successfully purged {result.rowcount} logs from audit_logs table.")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup old audit logs.")
    parser.add_argument("--days", type=int, default=30, help="Number of days of logs to retain.")
    args = parser.parse_args()

    asyncio.run(cleanup_logs(args.days))
