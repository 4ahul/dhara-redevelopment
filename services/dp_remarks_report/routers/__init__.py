import sys, os
_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _dir not in sys.path: sys.path.insert(0, _dir)
"""
DP Report Service — FastAPI Router
Endpoints:
  POST /fetch        — async (background job), returns job_id immediately
  POST /fetch/sync   — waits for result, returns full data
  GET  /status/{id}  — poll job status
  GET  /health

For testing, the service returns mock data loaded from a JSON file
(`routers/mock_response.json`). Edit that file to change the response
without touching orchestrator or other services. Ward/Village/CTS are
always echoed from the request to keep inputs consistent.
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile
import json
from pathlib import Path

from services.dp_remarks_report.core import settings
from services.dp_remarks_report.schemas import DPReportRequest, DPReportResponse, DPReportStatus
from services.dp_remarks_report.services import DPArcGISClient, DPBrowserScraper
from services.dp_remarks_report.services.dp_arcgis_client import parse_dp_attributes
from services.dp_remarks_report.services.storage import AsyncStorageService as StorageService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_storage() -> StorageService:
    return StorageService(settings.DATABASE_URL)


# ── Async endpoint ────────────────────────────────────────────────────────────


@router.post("/fetch", response_model=DPReportResponse)
async def fetch_dp_report(req: DPReportRequest, background_tasks: BackgroundTasks):
    """Submit a DP remarks fetch (processed in background). Poll GET /status/{id}."""
    storage = get_storage()
    report_id = await storage.create_report(
        ward=req.ward,
        village=req.village,
        cts_no=req.cts_no,
        lat=req.lat,
        lng=req.lng,
    )

    background_tasks.add_task(
        _do_fetch,
        report_id,
        req.ward,
        req.village,
        req.cts_no,
        req.use_fp_scheme,
        req.lat,
        req.lng,
        storage,
    )

    row = await storage.get_report(report_id)
    created_at = row["created_at"] if row else datetime.utcnow()

    return DPReportResponse(
        id=report_id,
        status=DPReportStatus.PROCESSING,
        ward=req.ward,
        village=req.village,
        cts_no=req.cts_no,
        created_at=created_at,
    )


# ── Sync endpoint ─────────────────────────────────────────────────────────────


@router.post("/fetch/sync", response_model=DPReportResponse)
async def fetch_dp_report_sync(req: DPReportRequest, request: Request):
    """Synchronous fetch — waits for full result. Suited for orchestrator calls."""
    storage = get_storage()
    report_id = await storage.create_report(
        ward=req.ward,
        village=req.village,
        cts_no=req.cts_no,
        lat=req.lat,
        lng=req.lng,
    )

    result = await _do_fetch(
        report_id,
        req.ward,
        req.village,
        req.cts_no,
        req.use_fp_scheme,
        req.lat,
        req.lng,
        storage,
    )

    row = await storage.get_report(report_id)
    created_at = row["created_at"] if row else datetime.utcnow()

    return DPReportResponse(
        id=report_id,
        status=DPReportStatus(result.get("status", "failed")),
        ward=result.get("ward", req.ward),
        village=result.get("village", req.village),
        cts_no=result.get("cts_no", req.cts_no),
        zone_code=result.get("zone_code"),
        zone_name=result.get("zone_name"),
        road_width_m=result.get("road_width_m"),
        fsi=result.get("fsi"),
        height_limit_m=result.get("height_limit_m"),
        reservations=result.get("reservations"),
        crz_zone=result.get("crz_zone"),
        heritage_zone=result.get("heritage_zone"),
        dp_remarks=result.get("dp_remarks"),
        download_url=f"{str(request.base_url).rstrip('/')}/download/{report_id}/screenshot",
        error_message=result.get("error"),
        created_at=created_at,
    )


# ── Status endpoint ───────────────────────────────────────────────────────────


@router.get("/status/{report_id}", response_model=DPReportResponse)
async def get_dp_report_status(report_id: str, request: Request):
    """Poll status of an async DP report fetch."""
    storage = get_storage()
    row = await storage.get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="DP report not found")

    reservations = row.get("reservations")
    if isinstance(reservations, str):
        import json as _json
        try:
            reservations = _json.loads(reservations)
        except Exception:
            reservations = None

    return DPReportResponse(
        id=str(row["id"]),
        status=DPReportStatus(row["status"]),
        ward=row.get("ward"),
        village=row.get("village"),
        cts_no=row.get("cts_no"),
        zone_code=row.get("zone_code"),
        zone_name=row.get("zone_name"),
        road_width_m=row.get("road_width_m"),
        fsi=row.get("fsi"),
        height_limit_m=row.get("height_limit_m"),
        reservations=reservations,
        crz_zone=row.get("crz_zone"),
        heritage_zone=row.get("heritage_zone"),
        dp_remarks=row.get("dp_remarks"),
        download_url=f"{str(request.base_url).rstrip('/')}/download/{str(row['id'])}/screenshot",
        error_message=row.get("error_message"),
        created_at=row.get("created_at"),
    )


# ── Screenshot download endpoint ──────────────────────────────────────────────


@router.get("/download/{report_id}/screenshot")
async def download_screenshot(report_id: str, storage: StorageService = Depends(get_storage)):
    screenshot = await storage.get_screenshot(report_id)
    if not screenshot:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return Response(content=screenshot, media_type="image/png", headers={
        "Content-Disposition": f'inline; filename="{report_id}_screenshot.png"'
    })


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "dp_report_service",
        "arcgis_layer_cached": DPArcGISClient._zone_layer_url is not None,
    }




