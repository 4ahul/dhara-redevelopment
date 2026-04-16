"""Society Routes — Clean refactored version using Service Layer"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db, get_current_user
from services.society_service import SocietyService
from schemas.society import SocietyCreate, SocietyUpdate, SocietyResponse, SocietyListItem, ReportCreate, ReportResponse, TenderCreate, TenderResponse
from schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/societies", tags=["Societies"])


def get_society_service(db: AsyncSession = Depends(get_db)) -> SocietyService:
    return SocietyService(db)


@router.get("", response_model=PaginatedResponse)
async def list_societies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    ward: str = Query(None),
    search: str = Query(None, max_length=200),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service)
):
    result = await service.list_societies(user.id, page, page_size, status, ward, search)
    return PaginatedResponse(
        items=[SocietyListItem.model_validate(r).model_dump() for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"]
    )


@router.post("", response_model=SocietyResponse, status_code=201)
async def create_society(
    req: SocietyCreate, 
    user=Depends(get_current_user), 
    service: SocietyService = Depends(get_society_service)
):
    soc = await service.create_society(user.id, req)
    return SocietyResponse.model_validate(soc)


@router.get("/{society_id}", response_model=SocietyResponse)
async def get_society(
    society_id: UUID, 
    user=Depends(get_current_user), 
    service: SocietyService = Depends(get_society_service)
):
    soc = await service.get_society(user.id, society_id)
    if not soc:
        raise HTTPException(404, "Society not found")
    return SocietyResponse.model_validate(soc)


@router.patch("/{society_id}", response_model=SocietyResponse)
async def patch_society(
    society_id: UUID, 
    req: SocietyUpdate, 
    user=Depends(get_current_user), 
    service: SocietyService = Depends(get_society_service)
):
    soc = await service.update_society(user.id, society_id, req)
    if not soc:
        raise HTTPException(404, "Society not found")
    return SocietyResponse.model_validate(soc)


@router.get("/{society_id}/reports", response_model=PaginatedResponse)
async def list_reports(
    society_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service)
):
    result = await service.list_reports(user.id, society_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Society not found")
    return PaginatedResponse(
        items=[ReportResponse.model_validate(r).model_dump() for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"]
    )


@router.post("/{society_id}/reports", response_model=ReportResponse, status_code=201)
async def create_report(
    society_id: UUID, 
    req: ReportCreate, 
    user=Depends(get_current_user), 
    service: SocietyService = Depends(get_society_service)
):
    rpt = await service.create_report(user.id, society_id, req)
    if not rpt:
        raise HTTPException(404, "Society not found")
    return ReportResponse.model_validate(rpt)


@router.get("/{society_id}/tenders", response_model=PaginatedResponse)
async def list_tenders(
    society_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service)
):
    result = await service.list_tenders(user.id, society_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Society not found")
    return PaginatedResponse(
        items=[TenderResponse.model_validate(r).model_dump() for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"]
    )


@router.post("/{society_id}/tenders", response_model=TenderResponse, status_code=201)
async def create_tender(
    society_id: UUID, 
    req: TenderCreate, 
    user=Depends(get_current_user), 
    service: SocietyService = Depends(get_society_service)
):
    t = await service.create_tender(user.id, society_id, req)
    if not t:
        raise HTTPException(404, "Society not found")
    return TenderResponse.model_validate(t)
