"""Feasibility Report Routes — Refactored version using Service Layer"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db, get_current_user
from services.feasibility_service import FeasibilityService
from schemas.society import FeasibilityReportCreate, FeasibilityReportUpdate, FeasibilityReportResponse
from schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feasibility-reports", tags=["Feasibility Reports"])


def get_feasibility_service(db: AsyncSession = Depends(get_db)) -> FeasibilityService:
    return FeasibilityService(db)


@router.get("", response_model=PaginatedResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    society_id: UUID = Query(None),
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service)
):
    result = await service.list_reports(user.id, page, page_size, status, society_id)
    return PaginatedResponse(
        items=[FeasibilityReportResponse.model_validate(r).model_dump() for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"]
    )


@router.post("", response_model=FeasibilityReportResponse, status_code=201)
async def create_report(
    req: FeasibilityReportCreate, 
    bg: BackgroundTasks, 
    user=Depends(get_current_user), 
    service: FeasibilityService = Depends(get_feasibility_service),
    db: AsyncSession = Depends(get_db)
):
    report = await service.create_report(user.id, req, bg)
    if not report:
        raise HTTPException(404, "Society not found")
    
    # Force commit here to ensure background task sees the record
    await db.commit()
    
    return FeasibilityReportResponse.model_validate(report)



@router.get("/{report_id}", response_model=FeasibilityReportResponse)
async def get_report(
    report_id: UUID, 
    user=Depends(get_current_user), 
    service: FeasibilityService = Depends(get_feasibility_service)
):
    report = await service.get_report(user.id, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return FeasibilityReportResponse.model_validate(report)


@router.patch("/{report_id}", response_model=FeasibilityReportResponse)
async def patch_report(
    report_id: UUID, 
    req: FeasibilityReportUpdate, 
    user=Depends(get_current_user), 
    service: FeasibilityService = Depends(get_feasibility_service)
):
    report = await service.update_report(user.id, report_id, req)
    if not report:
        raise HTTPException(404, "Report not found")
    return FeasibilityReportResponse.model_validate(report)
