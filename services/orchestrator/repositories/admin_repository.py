"""
Admin CRUD Operations — Specialized queries for the Admin dashboard and user management.
Optimized to avoid N+2 query problems.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models.enquiry import Enquiry, GetStartedRequest
from orchestrator.models.enums import EnquiryStatus, UserRole
from orchestrator.models.report import FeasibilityReport
from orchestrator.models.society import Society
from orchestrator.models.team import TeamMember
from orchestrator.models.user import User


async def list_pmc_users_with_stats(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[dict], int]:
    """
    Fetch PMC users along with their society and report counts in a single query.
    Fixes the N+2 query problem.
    """

    # Subqueries for counts
    soc_count_sub = (
        select(func.count(Society.id))
        .where(Society.created_by == User.id)
        .correlate(User)
        .as_scalar()
    )

    rep_count_sub = (
        select(func.count(FeasibilityReport.id))
        .where(FeasibilityReport.user_id == User.id)
        .correlate(User)
        .as_scalar()
    )

    # Base query for users
    query = select(
        User, soc_count_sub.label("societies_count"), rep_count_sub.label("reports_count")
    ).where(User.role == UserRole.PMC)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        query = query.where(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.organization.ilike(f"%{search}%"),
            )
        )

    # Get total count (for pagination)
    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar() or 0

    # Execute paginated query
    stmt = query.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    items = []
    for row in result:
        user, soc_count, rep_count = row
        user_dict = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "organization": user.organization,
            "role": user.role.value,
            "is_active": user.is_active,
            "societies_count": soc_count,
            "reports_count": rep_count,
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
        }
        items.append(user_dict)

    return items, total


async def get_dashboard_counts(db: AsyncSession) -> dict[str, int]:
    """Fetch various aggregate stats for the admin dashboard in concurrent-friendly queries."""

    return {
        "total_pmc_users": (
            await db.execute(select(func.count(User.id)).where(User.role == UserRole.PMC))
        ).scalar()
        or 0,
        "total_societies": (await db.execute(select(func.count(Society.id)))).scalar() or 0,
        "total_reports": (await db.execute(select(func.count(FeasibilityReport.id)))).scalar() or 0,
        "total_enquiries": (await db.execute(select(func.count(Enquiry.id)))).scalar() or 0,
        "open_enquiries": (
            await db.execute(
                select(func.count(Enquiry.id)).where(
                    Enquiry.status.in_([EnquiryStatus.NEW, EnquiryStatus.IN_PROGRESS])
                )
            )
        ).scalar()
        or 0,
        "total_get_started": (await db.execute(select(func.count(GetStartedRequest.id)))).scalar()
        or 0,
        "total_team_members": (await db.execute(select(func.count(TeamMember.id)))).scalar() or 0,
    }
