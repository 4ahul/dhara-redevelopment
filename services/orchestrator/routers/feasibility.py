"""Feasibility Report Routes — Refactored version using Service Layer"""

import logging
from uuid import UUID

from services.orchestrator.core.dependencies import get_current_user, get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from services.orchestrator.repositories import society_repository
from services.orchestrator.schemas.common import PaginatedResponse
from services.orchestrator.schemas.society import (
    FeasibilityReportCreate,
    FeasibilityReportResponse,
    FeasibilityReportUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.logic.feasibility_orchestrator import (
    feasibility_orchestrator,
)
from services.orchestrator.logic.feasibility_service import FeasibilityService

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


# ─── New Analyze Endpoint ────────────────────────────────────────────

from services.orchestrator.schemas.feasibility import FeasibilityAnalyzeRequest, FeasibilityAnalyzeResponse


@router.post("/analyze", response_model=FeasibilityAnalyzeResponse)
async def analyze_feasibility(
    req: FeasibilityAnalyzeRequest,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
):
    """Full feasibility analysis — orchestrates all microservices synchronously.

    Round 1 (parallel): PR Card, MCGM, Site Analysis, DP Remarks
    Round 2 (dependent): Aviation Height, Ready Reckoner
    Round 3: Generate Excel report from template
    Returns job_id + all results. Use GET /analyze/download/{job_id} for the Excel.
    """
    from uuid import uuid4
    from services.orchestrator.logic.redis import get_arq
    
    job_id = str(uuid4())
    arq = get_arq()
    
    if arq:
        # Enqueue the job (Task 1)
        await arq.enqueue_job("run_feasibility_analysis", req.model_dump(), str(user.id), job_id)
        return FeasibilityAnalyzeResponse(
            job_id=job_id,
            status="processing",
            report_generated=False
        )
    else:
        # Synchronous fallback if Arq is unavailable
        result = await feasibility_orchestrator.analyze(
            req.model_dump(),
            background_tasks=bg,
            user_id=str(user.id),
            report_id=job_id
        )
        return FeasibilityAnalyzeResponse(**result)


@router.post("/analyze/by-society/{society_id}", response_model=FeasibilityAnalyzeResponse)
async def analyze_feasibility_by_society(
    society_id: UUID,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service)
):
    """Trigger full feasibility analysis from an existing society and store results."""
    from uuid import uuid4
    from services.orchestrator.logic.redis import get_arq

    society = await society_repository.get_society_by_id(
        service.db, society_id, user.id
    )
    if not society:
        raise HTTPException(404, "Society not found")

    # Build request dict from society record
    req_data = {
        "society_id":    society.id,
        "society_name":  society.name,
        "address":       society.address,
        "cts_no":        society.cts_no,
        "fp_no":         society.fp_no,
        "ward":          society.ward,
        "village":       society.village,
        "tps_name":      society.tps_name,
        "num_flats":     society.num_flats,
        "num_commercial": society.num_commercial,
        "plot_area_sqm": society.plot_area_sqm,
        "road_width_m":  society.road_width_m,
    }

    job_id = str(uuid4())
    arq = get_arq()

    if arq:
        await arq.enqueue_job("run_feasibility_analysis", req_data, str(user.id), job_id)
        return FeasibilityAnalyzeResponse(
            job_id=job_id,
            status="processing",
            report_generated=False
        )
    else:
        result = await feasibility_orchestrator.analyze(
            req_data,
            background_tasks=bg,
            user_id=str(user.id),
            report_id=job_id
        )
        return FeasibilityAnalyzeResponse(**result)


@router.get("/analyze/status/{job_id}")
async def get_analyze_status(
    job_id: str,
    user=Depends(get_current_user),
):
    """Poll for progress of a feasibility analysis job."""
    from services.orchestrator.logic.dossier_service import dossier_service
    status = await dossier_service.get_dossier_status(job_id)
    if not status:
        raise HTTPException(404, f"Job {job_id} not found.")
    return status


@router.get("/analyze/download/{job_id}")
async def download_feasibility_report(
    job_id: str,
    user=Depends(get_current_user),
):
    """Download the generated Excel feasibility report for a completed job."""
    from services.orchestrator.logic.feasibility_orchestrator import _REPORT_STORE
    report_path = _REPORT_STORE.get(job_id)
    if not report_path:
        raise HTTPException(404, f"No report found for job_id={job_id}. Run /analyze first.")
    import os
    if not os.path.exists(report_path):
        raise HTTPException(410, "Report file has been removed from server.")
    return FileResponse(
        path=report_path,
        filename=f"Feasibility_Report_{job_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )




