"""
Global Reports Router — PMC-wide views and Job management.
Path: /api/pmc/reports
"""

import logging
import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user, get_db
from ...schemas.common import PaginatedResponse
from ...schemas.feasibility import (
    FeasibilityReportResponse,
    FeasibilityReportUpdate,
)
from ...services.dossier_service import dossier_service
from ...services.feasibility_service import FeasibilityService

logger = logging.getLogger(__name__)
# Prefix matched to §4.6.1: GET /api/pmc/reports
router = APIRouter(prefix="/reports", tags=["Reports Snapshot"])


def get_feasibility_service(db: AsyncSession = Depends(get_db)) -> FeasibilityService:
    return FeasibilityService(db)


def _report_to_response(report) -> dict:
    """Build a FeasibilityReportResponse dict, injecting society name."""
    data = FeasibilityReportResponse.model_validate(report)
    if hasattr(report, "society") and report.society:
        data.society = report.society.name
    return data.model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_all_reports_pmc_wide(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    status: str = Query(None),
    society_id: UUID = Query(None, alias="societyId"),
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    """
    List All Reports (PMC-wide) (§4.6.1).
    Shows reports list in the Dashboard Reports tab.
    """
    result = await service.list_reports(user.id, page, page_size, status, society_id)
    return PaginatedResponse(
        items=[_report_to_response(r) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/{report_id}")
async def get_report_by_id(
    report_id: UUID,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    """Get Report By ID (§4.6.4)."""
    report = await service.get_report(user.id, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return _report_to_response(report)


@router.patch("/{report_id}")
async def update_report_draft(
    report_id: UUID,
    req: FeasibilityReportUpdate,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    """Update / Save Report Draft (§4.6.5)."""
    report = await service.update_report(user.id, report_id, req)
    if not report:
        raise HTTPException(404, "Report not found")
    return _report_to_response(report)


# ─── Job Polling & Download ──────────────────────────────────────────────────


@router.get("/status/{job_id}")
async def get_job_status(
    job_id: str,
    user=Depends(get_current_user),
):
    """Poll for progress of an asynchronous feasibility job."""
    status = await dossier_service.get_dossier_status(job_id)
    if not status:
        raise HTTPException(404, f"Job {job_id} not found.")

    # If completed but no Cloudinary URL (local testing), provide Windows-formatted path
    if status.get("status") == "completed" and not status.get("file_url"):
        dossier = await dossier_service.get_dossier(job_id)
        if dossier:
            internal_path = dossier.get("data", {}).get("final_result", {}).get("report_path")
            if internal_path:
                filename = os.path.basename(internal_path)
                host_prefix = r"C:\Users\Admin\Documents\Projects\redevelopment-ai"
                status["file_url"] = (
                    f"@{host_prefix}\\services\\orchestrator\\generated_reports\\{filename}"
                )

    return status


@router.get("/download/{job_id}")
async def download_report_file(
    job_id: str,
    user=Depends(get_current_user),
):
    """Direct download of the generated Excel feasibility report."""
    dossier = await dossier_service.get_dossier(job_id)
    report_path = None

    if dossier:
        report_path = dossier.get("data", {}).get("final_result", {}).get("report_path")

    if not report_path or not os.path.exists(report_path):
        from ...db import async_session_factory
        from ...models.report import FeasibilityReport

        async with async_session_factory() as db:
            report = await db.get(FeasibilityReport, job_id)
            if report and report.report_path:
                report_path = report.report_path

    if not report_path or not os.path.exists(report_path):
        filename = f"feasibility_{job_id}.xlsx"
        fallbacks = [
            f"generated_reports/{filename}",
            f"services/orchestrator/generated_reports/{filename}",
            f"./generated_reports/{filename}",
            str(Path(__file__).parent.parent.parent / "generated_reports" / filename),
        ]
        for p in fallbacks:
            if os.path.exists(p):
                report_path = p
                break

    if report_path and os.path.exists(report_path):
        return FileResponse(
            path=report_path,
            filename=f"Feasibility_Report_{job_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if dossier:
        file_url = dossier.get("data", {}).get("final_result", {}).get("report_url")
        if file_url:
            return RedirectResponse(url=file_url, status_code=302)

    raise HTTPException(404, f"No report found for job_id={job_id}")
