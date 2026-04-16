"""
DP Report Service — FastAPI Router
Endpoints:
  POST /fetch        — async (background job), returns job_id immediately
  POST /fetch/sync   — waits for result, returns full data
  GET  /status/{id}  — poll job status
  GET  /health
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, Response, UploadFile

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
    Full DP remarks fetch flow:
      1. Try ArcGIS REST API — point query if lat/lng given, else attribute query
      2. Fall back to browser scraper (Playwright)
      3. Persist to DB
      4. Return structured result dict
    """
    attributes: Optional[dict] = None

    # ── Step 1: Direct ArcGIS REST ────────────────────────────────────────
    try:
        async with httpx.AsyncClient() as http:
            client = DPArcGISClient()
            if lat is not None and lng is not None:
                attributes = await client.query_by_point(lat, lng, http)
            if attributes is None:
                attributes = await client.query_by_cts(ward, village, cts_no, http)
    except Exception as e:
        logger.warning("Direct ArcGIS DP query failed: %s", e)

    # ── Step 2: Browser fallback ──────────────────────────────────────────
    screenshot_b64: Optional[str] = None
    if attributes is None:
        logger.info("ArcGIS returned no DP data — launching browser scraper")
        try:
            scraper = DPBrowserScraper(headless=settings.BROWSER_HEADLESS)
            result = await scraper.scrape(ward, village, cts_no, lat, lng)
            attributes = result.get("attributes")
            screenshot_b64 = result.get("screenshot_b64")

            if result.get("error") and attributes is None:
                err = result["error"]
                if report_id and storage:
                    await storage.update_report(
                        report_id=report_id,
                        status="failed",
                        error_message=err,
                    )
                return {"status": "failed", "error": err}
        except Exception as e:
            logger.error("DP browser scraper error: %s", e, exc_info=True)
            if report_id and storage:
                await storage.update_report(
                    report_id=report_id,
                    status="failed",
                    error_message=str(e),
                )
            return {"status": "failed", "error": str(e)}

    # ── Step 3: Parse attributes ──────────────────────────────────────────
    parsed = parse_dp_attributes(attributes or {})

    # ── Step 4: Persist ───────────────────────────────────────────────────
    screenshot_bytes: Optional[bytes] = None
    if screenshot_b64:
        try:
            screenshot_bytes = base64.b64decode(screenshot_b64)
        except Exception:
            pass

    if report_id and storage:
        await storage.update_report(
            report_id=report_id,
            status="completed",
            zone_code=parsed.get("zone_code"),
            zone_name=parsed.get("zone_name"),
            road_width_m=parsed.get("road_width_m"),
            fsi=parsed.get("fsi"),
            height_limit_m=parsed.get("height_limit_m"),
            reservations=parsed.get("reservations"),
            crz_zone=parsed.get("crz_zone"),
            heritage_zone=parsed.get("heritage_zone"),
            dp_remarks=parsed.get("dp_remarks"),
            raw_attributes=attributes,
            map_screenshot=screenshot_bytes,
        )

    return {
        "status": "completed",
        "ward": ward,
        "village": village,
        "cts_no": cts_no,
        **parsed,
    }


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
    """Parse a DP Remark PDF and return extracted data. No browser automation needed."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    pdf_bytes = await file.read()
    if len(pdf_bytes) < 100:
        raise HTTPException(status_code=400, detail="PDF file is too small or empty")

    from services.dp_pdf_parser import parse_dp_pdf
    parsed = parse_dp_pdf(pdf_bytes)

    if "error" in parsed and parsed.get("report_type") is None:
        raise HTTPException(status_code=422, detail=parsed["error"])

    return DPReportResponse(
        status=DPReportStatus.COMPLETED,
        ward=parsed.get("ward"),
        village=parsed.get("village"),
        report_type=parsed.get("report_type"),
        reference_no=parsed.get("reference_no"),
        report_date=parsed.get("report_date"),
        applicant_name=parsed.get("applicant_name"),
        cts_nos=parsed.get("cts_nos"),
        fp_no=parsed.get("fp_no"),
        tps_name=parsed.get("tps_name"),
        zone_code=parsed.get("zone_code"),
        zone_name=parsed.get("zone_name"),
        reservations_affecting=parsed.get("reservations_affecting"),
        reservations_abutting=parsed.get("reservations_abutting"),
        designations_affecting=parsed.get("designations_affecting"),
        designations_abutting=parsed.get("designations_abutting"),
        existing_amenities_affecting=parsed.get("existing_amenities_affecting"),
        existing_amenities_abutting=parsed.get("existing_amenities_abutting"),
        dp_roads=parsed.get("dp_roads"),
        proposed_road=parsed.get("proposed_road"),
        proposed_road_widening=parsed.get("proposed_road_widening"),
        rl_remarks_traffic=parsed.get("rl_remarks_traffic"),
        rl_remarks_survey=parsed.get("rl_remarks_survey"),
        water_pipeline=parsed.get("water_pipeline"),
        sewer_line=parsed.get("sewer_line"),
        drainage=parsed.get("drainage"),
        ground_level=parsed.get("ground_level"),
        heritage_building=parsed.get("heritage_building"),
        heritage_precinct=parsed.get("heritage_precinct"),
        heritage_buffer_zone=parsed.get("heritage_buffer_zone"),
        archaeological_site=parsed.get("archaeological_site"),
        archaeological_buffer=parsed.get("archaeological_buffer"),
        crz_zone_details=parsed.get("crz_zone_details"),
        high_voltage_line=parsed.get("high_voltage_line"),
        buffer_sgnp=parsed.get("buffer_sgnp"),
        flamingo_esz=parsed.get("flamingo_esz"),
        corrections_dcpr=parsed.get("corrections_dcpr"),
        modifications_sec37=parsed.get("modifications_sec37"),
        road_realignment=parsed.get("road_realignment"),
        ep_nos=parsed.get("ep_nos"),
        sm_nos=parsed.get("sm_nos"),
        pdf_text=parsed.get("pdf_text"),
    )


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "dp_report_service",
        "arcgis_layer_cached": DPArcGISClient._zone_layer_url is not None,
    }
