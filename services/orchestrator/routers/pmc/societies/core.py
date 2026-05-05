import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.dependencies import get_current_user, get_db
from ....schemas.common import PaginatedResponse
from ....schemas.society import (
    SocietyCreate,
    SocietyListItem,
    SocietyResponse,
    SocietyUpdate,
)
from ....services.society_service import SocietyService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Societies"])


def get_society_service(db: AsyncSession = Depends(get_db)) -> SocietyService:
    return SocietyService(db)


def _society_to_response(soc) -> dict:
    """Helper to convert ORM Society to Response dict with calculated counts."""
    data = SocietyResponse.model_validate(soc)
    # Calculate counts from relationships
    data.reports = len(soc.reports) if soc.reports else 0
    data.tenders = len(soc.tenders) if soc.tenders else 0
    return data.model_dump(by_alias=True, exclude_none=True)


def _society_to_list_item(soc) -> dict:
    """Helper to convert ORM Society to List Item dict with calculated counts."""
    data = SocietyListItem.model_validate(soc)
    data.reports = len(soc.reports) if soc.reports else 0
    data.tenders = len(soc.tenders) if soc.tenders else 0
    return data.model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_societies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    status: str = Query(None),
    ward: str = Query(None),
    search: str = Query(None, max_length=200),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """List Managed Societies (§4.4.1)."""
    result = await service.list_societies(user.id, page, page_size, status, ward, search)
    return PaginatedResponse(
        items=[_society_to_list_item(r) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("", status_code=201)
async def register_society(
    req: SocietyCreate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """Register Society (§4.4.3)."""
    soc = await service.create_society(user.id, req)
    return _society_to_response(soc)


@router.get("/{society_id}")
async def get_society_by_id(
    society_id: UUID,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """Get Society By ID (§4.4.2)."""
    soc = await service.get_society(user.id, society_id)
    if not soc:
        raise HTTPException(404, "Society not found")
    return _society_to_response(soc)


@router.patch("/{society_id}")
async def update_society(
    society_id: UUID,
    req: SocietyUpdate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """Update Society (§4.4.4)."""
    soc = await service.update_society(user.id, society_id, req)
    if not soc:
        raise HTTPException(404, "Society not found")
    return _society_to_response(soc)
