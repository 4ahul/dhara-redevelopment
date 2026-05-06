"""
Dhara AI — Database Package
Async SQLAlchemy engine, session factory, and lifecycle hooks.
"""

import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from orchestrator.core.config import settings
from orchestrator.db.base import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.db_url,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=3600,
    echo=settings.DB_ECHO,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Create all tables on first run. Use Alembic in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")


async def close_db():
    """Dispose engine pool on shutdown."""
    await engine.dispose()
    logger.info("Database pool closed")
