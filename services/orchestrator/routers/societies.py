"""Society Routes -- Clean refactored version using Service Layer

FE-aligned: responses use camelCase aliases (by_alias=True),
computed reports/tenders counts are injected.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_db
from ..schemas.common import PaginatedResponse
from ..schemas.society import (
    ReportCreate,
    ReportResponse,
    SocietyCreate,
    SocietyListItem,
    SocietyResponse,
    SocietyUpdate,
    TenderCreate,
    TenderResponse,
)
from ..services.society_service import SocietyService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/societies", tags=["Societies"])


def get_society_service(db: AsyncSession = Depends(get_db)) -> SocietyService:
    return SocietyService(db)


def _society_to_response(soc) -> dict:
    """Build a SocietyResponse dict from an ORM Society, injecting computed counts."""
    data = SocietyResponse.model_validate(soc)
    data.reports = len(soc.reports) if soc.reports else 0
    data.tenders = len(soc.tenders) if soc.tenders else 0
    return data.model_dump(by_alias=True)


def _society_to_list_item(soc) -> dict:
    """Build a SocietyListItem dict from an ORM Society, injecting computed counts."""
    data = SocietyListItem.model_validate(soc)
    data.reports = len(soc.reports) if soc.reports else 0
    data.tenders = len(soc.tenders) if soc.tenders else 0
    return data.model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_societies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias='pageSize'),
    status: str = Query(None),
    ward: str = Query(None),
    search: str = Query(None, max_length=200),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    result = await service.list_societies(user.id, page, page_size, status, ward, search)
    return PaginatedResponse(
        items=[_society_to_list_item(r) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("", status_code=201)
async def create_society(
    req: SocietyCreate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    soc = await service.create_society(user.id, req)
    return _society_to_response(soc)


@router.get("/{society_id}")
async def get_society(
    society_id: UUID,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    soc = await service.get_society(user.id, society_id)
    if not soc:
        raise HTTPException(404, "Society not found")
    return _society_to_response(soc)


@router.patch("/{society_id}")
async def patch_society(
    society_id: UUID,
    req: SocietyUpdate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    soc = await service.update_society(user.id, society_id, req)
    if not soc:
        raise HTTPException(404, "Society not found")
    return _society_to_response(soc)


@router.get("/{society_id}/reports", response_model=PaginatedResponse)
async def list_reports(
    society_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    result = await service.list_reports(user.id, society_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Society not found")
    return PaginatedResponse(
        items=[ReportResponse.model_validate(r).model_dump() for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("/{society_id}/reports", response_model=ReportResponse, status_code=201)
async def create_report(
    society_id: UUID,
    req: ReportCreate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    rpt = await service.create_report(user.id, society_id, req)
    if not rpt:
        raise HTTPException(404, "Society not found")
    return ReportResponse.model_validate(rpt)


def _tender_to_response(tender) -> dict:
    """Build camelCase tender response, injecting responses_count placeholder."""
    data = TenderResponse.model_validate(tender)
    # TODO: once tender_proposals table exists, compute actual count here
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
    result = await service.list_tenders(user.id, society_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Society not found")
    return PaginatedResponse(
        items=[_tender_to_response(r) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("/{society_id}/tenders", status_code=201)
async def create_tender(
    society_id: UUID,
    req: TenderCreate,
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    t = await service.create_tender(user.id, society_id, req)
    if not t:
        raise HTTPException(404, "Society not found")
    return _tender_to_response(t)
