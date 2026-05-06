"""
Landing Page CRUD Operations — Repository for CMS-style content.
"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models.landing import LandingPageContent


async def list_active_landing_content(db: AsyncSession) -> Sequence[LandingPageContent]:
    """Fetch all active landing page sections ordered by display_order."""
    stmt = (
        select(LandingPageContent)
        .where(LandingPageContent.is_active)
        .order_by(LandingPageContent.display_order.asc())
    )
    return (await db.execute(stmt)).scalars().all()


async def create_landing_content(db: AsyncSession, data: dict) -> LandingPageContent:
    """Initialize a new landing page section."""
    entry = LandingPageContent(**data)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry
