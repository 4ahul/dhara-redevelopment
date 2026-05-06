"""
Society Tenders Router.
Path: /api/pmc/societies/{society_id}/tenders
"""

import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.dependencies import get_current_user, get_db
from ....schemas.common import PaginatedResponse
from ....schemas.society import (
    TenderCreate,
    TenderResponse,
)
from ....services.society_service import SocietyService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Societies"])


def get_society_service(db: AsyncSession = Depends(get_db)) -> SocietyService:
    return SocietyService(db)


async def _tender_to_response(tender, db: AsyncSession) -> dict:
    """Build camelCase tender response with actual proposals_count."""
    from sqlalchemy import select, func
    from ....models.team import TenderProposal

    data = TenderResponse.model_validate(tender)

    # Get actual proposal count from database
    try:
        stmt = select(func.count(TenderProposal.id)).where(TenderProposal.tender_id == tender.id)
        result = await db.execute(stmt)
        data.responses_count = result.scalar() or 0
    except Exception:
        data.responses_count = 0

    return data.model_dump(by_alias=True)


@router.get("/{society_id}/tenders", response_model=PaginatedResponse)
async def list_tenders(
    society_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """List Tenders for a Society (§4.8.1)."""
    result = await service.list_tenders(user.id, society_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Society not found")

    return PaginatedResponse(
        items=[await _tender_to_response(r, db) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("/{society_id}/tenders", status_code=201)
async def create_society_tender(
    society_id: UUID,
    req: TenderCreate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """Create Society Tender (§4.8.2)."""
    t = await service.create_tender(user.id, society_id, req)
    if not t:
        raise HTTPException(404, "Society not found")

    return TenderResponse.model_validate(t).model_dump(by_alias=True)
