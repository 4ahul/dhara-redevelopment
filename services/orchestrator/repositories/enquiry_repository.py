"""
Enquiry CRUD Operations — Repository for Contact forms and Get Started requests.
"""

from collections.abc import Sequence
from uuid import UUID

from services.orchestrator.models.enquiry import Enquiry, GetStartedRequest
from services.orchestrator.models.enums import EnquiryStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_enquiries(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: EnquiryStatus = None,
    source: str = None
) -> tuple[Sequence[Enquiry], int]:
    """Fetch paginated enquiries with filters."""
    base = select(Enquiry)
    if status:
        base = base.where(Enquiry.status == status)
    if source:
        base = base.where(Enquiry.source == source)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (await db.execute(
        base.order_by(Enquiry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    return rows, total

async def get_enquiry_by_id(db: AsyncSession, enquiry_id: UUID) -> Enquiry | None:
    """Fetch a single enquiry by ID."""
    return (await db.execute(select(Enquiry).where(Enquiry.id == enquiry_id))).scalar_one_or_none()

async def create_enquiry(db: AsyncSession, data: dict) -> Enquiry:
    """Create a new contact enquiry."""
    enquiry = Enquiry(**data)
    db.add(enquiry)
    await db.flush()
    await db.refresh(enquiry)
    return enquiry

async def create_get_started_request(db: AsyncSession, data: dict) -> GetStartedRequest:
    """Create a new 'Get Started' request."""
    entry = GetStartedRequest(**data)
    db.add(entry)
    await db.flush()
    await db.refresh(entry)
    return entry



