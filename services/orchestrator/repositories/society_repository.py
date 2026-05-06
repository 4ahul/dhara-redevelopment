"""
Society CRUD Operations — Repository for Societies, Reports, and Tenders.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.models.report import FeasibilityReport, SocietyReport
from services.orchestrator.models.society import Society
from services.orchestrator.models.team import SocietyTender


async def get_society_by_id(db: AsyncSession, society_id: UUID, user_id: UUID) -> Society | None:
    """Fetch a single society, ensuring user ownership."""
    return (
        await db.execute(
            select(Society).where(Society.id == society_id, Society.created_by == user_id)
        )
    ).scalar_one_or_none()


async def list_societies(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    search: str | None = None,
) -> tuple[Sequence[Society], int]:
    """List societies with owner, filters, search, and pagination."""
    base = select(Society).where(Society.created_by == user_id)
    if status:
        base = base.where(Society.status == status)
    if search:
        base = base.where(
            or_(
                Society.name.ilike(f"%{search}%"),
                Society.address.ilike(f"%{search}%"),
            )
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        (
            await db.execute(
                base.order_by(Society.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return rows, total


async def create_society(db: AsyncSession, user_id: UUID, data: dict) -> Society:
    """Create a new society record."""
    soc = Society(**data, created_by=user_id)
    db.add(soc)
    await db.flush()
    await db.refresh(soc)
    return soc


async def update_society_field(db: AsyncSession, society_id: UUID, updates: dict) -> Society | None:
    """Update specific fields of a society record."""
    from sqlalchemy import update

    if not updates:
        return None

    stmt = update(Society).where(Society.id == society_id).values(**updates)
    await db.execute(stmt)
    await db.flush()

    result = await db.execute(select(Society).where(Society.id == society_id))
    return result.scalar_one_or_none()


# ─── Society Reports ────────────────────────────────────────────────────────


async def list_society_reports(
    db: AsyncSession, society_id: UUID, page: int = 1, page_size: int = 20
) -> tuple[Sequence[SocietyReport], int]:
    base = select(SocietyReport).where(SocietyReport.society_id == society_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        (
            await db.execute(
                base.order_by(SocietyReport.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def create_society_report(db: AsyncSession, data: dict) -> SocietyReport:
    rpt = SocietyReport(**data)
    db.add(rpt)
    await db.flush()
    await db.refresh(rpt)
    return rpt


# ─── Society Tenders ────────────────────────────────────────────────────────


async def list_society_tenders(
    db: AsyncSession, society_id: UUID, page: int = 1, page_size: int = 20
) -> tuple[Sequence[SocietyTender], int]:
    base = select(SocietyTender).where(SocietyTender.society_id == society_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        (
            await db.execute(
                base.order_by(SocietyTender.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def create_society_tender(db: AsyncSession, data: dict) -> SocietyTender:
    t = SocietyTender(**data)
    db.add(t)
    await db.flush()
    await db.refresh(t)
    return t


# ─── Feasibility Reports (Orchestrator Specialized) ─────────────────────────


async def get_feasibility_report(
    db: AsyncSession, report_id: UUID, user_id: UUID
) -> FeasibilityReport | None:
    return (
        await db.execute(
            select(FeasibilityReport).where(
                FeasibilityReport.id == report_id, FeasibilityReport.user_id == user_id
            )
        )
    ).scalar_one_or_none()


async def list_feasibility_reports(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    society_id: UUID | None = None,
) -> tuple[Sequence[FeasibilityReport], int]:
    base = select(FeasibilityReport).where(FeasibilityReport.user_id == user_id)
    if status:
        base = base.where(FeasibilityReport.status == status)
    if society_id:
        base = base.where(FeasibilityReport.society_id == society_id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        (
            await db.execute(
                base.order_by(FeasibilityReport.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    return rows, total


async def create_feasibility_report(
    db: AsyncSession, user_id: UUID, data: dict
) -> FeasibilityReport:
    report = FeasibilityReport(**data, user_id=user_id)
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report
