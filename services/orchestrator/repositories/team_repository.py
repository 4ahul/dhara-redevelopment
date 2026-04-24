"""
Team CRUD Operations — Repository for organization members and invites.
"""

from collections.abc import Sequence
from uuid import UUID

from models.enums import InviteStatus
from models.team import TeamMember
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_team_members(
    db: AsyncSession,
    organization: str,
    page: int = 1,
    page_size: int = 20,
    status: InviteStatus = None
) -> tuple[Sequence[TeamMember], int]:
    """Fetch paginated team members for an organization."""
    base = select(TeamMember).where(TeamMember.organization == organization)
    if status:
        base = base.where(TeamMember.status == status)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(TeamMember.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return rows, total

async def get_team_member_by_id(db: AsyncSession, member_id: UUID, organization: str) -> TeamMember | None:
    """Fetch a specific team member, scoped to organization."""
    return (await db.execute(
        select(TeamMember).where(TeamMember.id == member_id, TeamMember.organization == organization)
    )).scalar_one_or_none()

async def create_team_member(db: AsyncSession, data: dict) -> TeamMember:
    """Register a new team member or invite."""
    member = TeamMember(**data)
    db.add(member)
    await db.flush()
    await db.refresh(member)
    return member

async def get_member_by_email_and_org(db: AsyncSession, email: str, organization: str) -> TeamMember | None:
    """Check for existing member in an organization."""
    return (await db.execute(
        select(TeamMember).where(TeamMember.email == email, TeamMember.organization == organization)
    )).scalar_one_or_none()


