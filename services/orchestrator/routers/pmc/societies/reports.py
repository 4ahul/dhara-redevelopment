"""
Society Reports Router — Report history and feasibility submission.
Path: /api/pmc/societies/{society_id}/reports
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
from ....schemas.feasibility import (
    FeasibilityAnalyzeResponse,
    FeasibilityForm,
)
from ....schemas.society import ReportResponse
from ....services.feasibility_service import FeasibilityService
from ....services.society_service import SocietyService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Societies"])


def get_society_service(db: AsyncSession = Depends(get_db)) -> SocietyService:
    return SocietyService(db)


def get_feasibility_service(db: AsyncSession = Depends(get_db)) -> FeasibilityService:
    return FeasibilityService(db)


@router.get("/{society_id}/reports", response_model=PaginatedResponse)
async def list_reports_for_society(
    society_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SocietyService = Depends(get_society_service),
):
    """List Report History for a Society (§4.6.2)."""
    result = await service.list_reports(user.id, society_id, page, page_size)
    if result is None:
        raise HTTPException(404, "Society not found")
    return PaginatedResponse(
        items=[ReportResponse.model_validate(r).model_dump(by_alias=True) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("/{society_id}/reports", response_model=FeasibilityAnalyzeResponse, status_code=202)
async def create_feasibility_report(
    user=Depends(get_current_user),
    f_service: FeasibilityService = Depends(get_feasibility_service),
    form: FeasibilityForm = Depends(),
):
    """Create Feasibility Report (§4.6.3)."""
    try:
        result = await f_service.submit_feasibility_analysis(user.id, form)
        return FeasibilityAnalyzeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
