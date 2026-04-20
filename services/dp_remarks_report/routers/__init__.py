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

from core import settings
from schemas import DPReportRequest, DPReportResponse, DPReportStatus
from services import DPArcGISClient, DPBrowserScraper
from services.dp_arcgis_client import parse_dp_attributes
from services.storage import AsyncStorageService as StorageService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_storage() -> StorageService:
    return StorageService(settings.DATABASE_URL)


# ── Core lookup helper ────────────────────────────────────────────────────────


# Path to the mock JSON that drives the response structure/values
_MOCK_PATH = Path(__file__).with_name("mock_response.json")


def _load_mock() -> dict:
    """Load mock response JSON if present; return {} on error/missing.

    We intentionally read on every request so edits are picked up live
    (useful during manual testing).
    """
    try:
        if _MOCK_PATH.exists():
            with _MOCK_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        logger.warning("Mock file load failed: %s", e)
    return {}


async def _do_fetch(
    report_id: Optional[str],
    ward: str,
    village: str,
    cts_no: str,
    lat: Optional[float],
    lng: Optional[float],
    storage: Optional[StorageService],
) -> dict:
    """
    [HARDCODED FOR TESTING] Returns data from a mock JSON file.
    """
    logger.info("HARDCODED: Returning DP data from mock_response.json (if present)")

    # Sensible defaults matching the response schema; these will be
    # overridden by the mock file if values are provided there.
    parsed = {
        "status": "completed",
        "ward": "",
        "village": "",
        "cts_no": "",
        "report_type": None,
        "reference_no": None,
        "report_date": None,
        "applicant_name": None,
        "cts_nos": None,
        "fp_no": None,
        "tps_name": None,
        "zone_code": None,
        "zone_name": None,
        "road_width_m": None,
        "fsi": None,
        "height_limit_m": None,
        "reservations": None,
        "reservations_affecting": None,
        "reservations_abutting": None,
        "designations_affecting": None,
        "designations_abutting": None,
        "existing_amenities_affecting": None,
        "existing_amenities_abutting": None,
        "dp_roads": None,
        "proposed_road": None,
        "proposed_road_widening": None,
        "rl_remarks_traffic": None,
        "rl_remarks_survey": None,
        "water_pipeline": None,
        "sewer_line": None,
        "drainage": None,
        "ground_level": None,
        "heritage_building": None,
        "heritage_precinct": None,
        "heritage_buffer_zone": None,
        "archaeological_site": None,
        "archaeological_buffer": None,
        "crz_zone_details": None,
        "high_voltage_line": None,
        "buffer_sgnp": None,
        "flamingo_esz": None,
        "corrections_dcpr": None,
        "modifications_sec37": None,
        "road_realignment": None,
        "ep_nos": None,
        "sm_nos": None,
        "crz_zone": None,
        "heritage_zone": None,
        "dp_remarks": None,
    }

    # Merge mock values over defaults
    mock_values = _load_mock()
    for k, v in mock_values.items():
        parsed[k] = v

    # Always reflect the incoming request for core identifiers and complete the job
    parsed["status"] = "completed"
    parsed["ward"] = ward
    parsed["village"] = village
    parsed["cts_no"] = cts_no

    if report_id and storage:
        await storage.update_report(
            report_id=report_id,
            status="completed",
            **{k: v for k, v in parsed.items() if k not in ("status", "ward", "village", "cts_no")}
        )

    return parsed


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


# ── PDF parse endpoint ────────────────────────────────────────────────────────


@router.post("/parse-pdf", response_model=DPReportResponse)
async def parse_dp_pdf_endpoint(file: UploadFile = File(...)):
    """[HARDCODED FOR TESTING] Returns Comprehensive Dhiraj Kunj DP data."""
    return DPReportResponse(
        status=DPReportStatus.COMPLETED,
        ward="K/W",
        village="VILE PARLE",
        cts_no="854",
        report_type="DP_2034",
        reference_no="Ch.E./DP34202211111425031",
        report_date="04/11/2022",
        applicant_name="Jinish N Soni",
        cts_nos=["852", "853", "854", "855"],
        fp_no="18",
        tps_name="TPS VILE PARLE No.VI",
        zone_code="R",
        zone_name="Residential(R)",
        road_width_m=13.42,
        fsi=1.0,
        reservations_affecting="NO",
        reservations_abutting="NO",
        existing_amenities_affecting="NO",
        existing_amenities_abutting="NO",
        dp_roads="Present (Existing Road)",
        proposed_road="NIL",
        proposed_road_widening="NIL",
        rl_remarks_traffic="Regular Line/Road Line at present along the plot F.P. No.(s) 18 is 13.42M. Bajaj Road is 12.20M.",
        rl_remarks_survey="Regular Line/Road Line at present along the plot F.P. No.(s) 18 is 13.42M. Bajaj Road is 12.20M.",
        water_pipeline={"distance_m": 3.44, "diameter_mm": 250},
        sewer_line={"node_no": "15240911", "distance_m": 6.82, "invert_level_m": 28.5},
        ground_level={"min_m": 32.4, "max_m": 33.0, "datum": "THD"},
        heritage_building="No",
        heritage_precinct="No",
        heritage_buffer_zone="No",
        archaeological_site="No",
        archaeological_buffer="No",
        crz_zone_details="NIL / Outside CRZ",
        high_voltage_line="NIL",
        buffer_sgnp="NIL",
        flamingo_esz="NIL",
        corrections_dcpr="NIL",
        modifications_sec37="NIL",
        road_realignment="NIL",
        ep_nos=["EP-T91"],
        sm_nos=["SM-KW12"],
        crz_zone=False,
        heritage_zone=False,
        dp_remarks="Since the land is under T.P. Scheme, remarks from Town Planning Section should be obtained separately.",
    )


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "dp_report_service",
        "arcgis_layer_cached": DPArcGISClient._zone_layer_url is not None,
    }
