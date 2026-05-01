
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

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)

from ..core import settings
from ..schemas import DPReportRequest, DPReportResponse, DPReportStatus
from ..services import DPArcGISClient, DPBrowserScraper
from ..services.dp_arcgis_client import (
    parse_dp_attributes as parse_dp_attributes,
)
from ..services.storage import AsyncStorageService as StorageService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_storage() -> StorageService:
    return StorageService(settings.DATABASE_URL)


# ── Core lookup helper ────────────────────────────────────────────────────────


# Path to the mock JSON that drives the response structure/values
_MOCK_PATH = Path(__file__).with_name("mock_response.json")


def _load_mock() -> dict:
    """Load mock response JSON if present; return {} on error/missing."""
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
    report_id: str | None,
    ward: str,
    village: str,
    cts_no: str,
    use_fp_scheme: bool,
    tps_scheme: str | None,
    fp_no: str | None,
    lat: float | None,
    lng: float | None,
    storage: StorageService | None,
) -> dict:
    """Run the full DP remarks scrape via DPBrowserScraper."""
    logger.info("Scraping DP remarks for CTS %s in %s/%s", cts_no, ward, village)

    scraper = DPBrowserScraper(headless=settings.BROWSER_HEADLESS)
    result = await scraper.scrape(ward, village, cts_no, lat, lng, use_fp_scheme=use_fp_scheme, tps_scheme=tps_scheme, fp_no=fp_no)

    attrs = result.get("attributes") or {}
    error = result.get("error")
    status = "failed" if (error and not attrs) else "completed"

    # Derive boolean flags from PDF-parsed text fields
    def _is_yes(text) -> bool:
        if not text:
            return False
        clean = str(text).strip().lower()
        return "/" not in clean and clean in {"yes", "true", "1"}

    crz_zone = bool(attrs.get("crz_zone_details") or attrs.get("crz_zone"))
    heritage_zone = _is_yes(attrs.get("heritage_building")) or _is_yes(attrs.get("heritage_precinct"))

    parsed = {
        "status": status,
        "ward": ward,
        "village": village,
        "cts_no": cts_no,
        "error_message": error,
        # Core zone
        "zone_code": attrs.get("zone_code"),
        "zone_name": attrs.get("zone_name"),
        "road_width_m": attrs.get("road_width_m"),
        "fsi": attrs.get("fsi"),
        "height_limit_m": attrs.get("height_limit_m"),
        "crz_zone": crz_zone,
        "heritage_zone": heritage_zone,
        "dp_remarks": attrs.get("dp_remarks"),
        # PDF parsed fields
        "report_type": attrs.get("report_type"),
        "reference_no": attrs.get("reference_no"),
        "report_date": attrs.get("report_date"),
        "applicant_name": attrs.get("applicant_name"),
        "cts_nos": attrs.get("cts_nos"),
        "fp_no": attrs.get("fp_no"),
        "tps_name": attrs.get("tps_name"),
        "reservations_affecting": attrs.get("reservations_affecting"),
        "reservations_abutting": attrs.get("reservations_abutting"),
        "designations_affecting": attrs.get("designations_affecting"),
        "designations_abutting": attrs.get("designations_abutting"),
        "dp_roads": attrs.get("dp_roads"),
        "proposed_road": attrs.get("proposed_road"),
        "proposed_road_widening": attrs.get("proposed_road_widening"),
        "rl_remarks_traffic": attrs.get("rl_remarks_traffic"),
        "rl_remarks_survey": attrs.get("rl_remarks_survey"),
        "water_pipeline": attrs.get("water_pipeline"),
        "sewer_line": attrs.get("sewer_line"),
        "drainage": attrs.get("drainage"),
        "ground_level": attrs.get("ground_level"),
        "heritage_building": attrs.get("heritage_building"),
        "heritage_precinct": attrs.get("heritage_precinct"),
        "archaeological_site": attrs.get("archaeological_site"),
        "crz_zone_details": attrs.get("crz_zone_details"),
        "high_voltage_line": attrs.get("high_voltage_line"),
        "buffer_sgnp": attrs.get("buffer_sgnp"),
        "flamingo_esz": attrs.get("flamingo_esz"),
        "corrections_dcpr": attrs.get("corrections_dcpr"),
        "modifications_sec37": attrs.get("modifications_sec37"),
        "road_realignment": attrs.get("road_realignment"),
        "ep_nos": attrs.get("ep_nos"),
        "sm_nos": attrs.get("sm_nos"),
        "pdf_text": attrs.get("pdf_text"),
        # Payment
        "payment_status": result.get("payment_status"),
        "payment_transaction_id": result.get("payment_transaction_id"),
        "payment_amount": result.get("payment_amount"),
        "payment_paid_at": result.get("payment_paid_at"),
        "pdf_bytes": result.get("pdf_bytes"),
    }

    if report_id and storage:
        update_kwargs = {
            k: v for k, v in parsed.items()
            if k not in ("status", "ward", "village", "cts_no", "error_message", "pdf_bytes")
        }
        update_kwargs["error_message"] = error
        update_kwargs["pdf_bytes"] = result.get("pdf_bytes")
        await storage.update_report(
            report_id=report_id,
            status=status,
            **update_kwargs,
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
        req.tps_scheme,
        req.fp_no,
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
    return Response(
        content=screenshot,
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{report_id}_screenshot.png"'},
    )


# ── PDF upload endpoint ───────────────────────────────────────────────────────


@router.post("/fetch/from-pdf", response_model=DPReportResponse)
async def fetch_dp_report_from_pdf(
    request: Request,
    file: UploadFile = File(..., description="DP Remarks PDF file"),
    ward: str | None = Form(None),
    village: str | None = Form(None),
    cts_no: str | None = Form(None),
):
    """Parse a DP Remarks PDF directly. Use when portal automation is unavailable.

    Accepts multipart/form-data with the PDF file plus optional ward/village/cts_no
    context fields. Returns the same DPReportResponse schema as /fetch/sync.
    """
    from ..services.dp_pdf_parser import parse_dp_pdf

    pdf_bytes = await file.read()
    parsed = parse_dp_pdf(pdf_bytes)

    if "error" in parsed:
        return DPReportResponse(
            status=DPReportStatus.FAILED,
            ward=ward,
            village=village,
            cts_no=cts_no,
            error_message=parsed["error"],
            created_at=datetime.utcnow(),
        )

    def _is_yes_answer(text: str | None) -> bool:
        """PDF prints 'Yes / No' with both options; if slash present format is ambiguous.
        Only trust unambiguous single-word answers (no slash)."""
        if not text:
            return False
        clean = text.strip().lower()
        if "/" in clean:
            return False  # Both options printed — cannot determine selected value
        return clean in {"yes", "true", "1"}

    # Derive boolean flags from parsed text fields
    crz_zone = bool(parsed.get("crz_zone_details"))
    heritage_zone = _is_yes_answer(parsed.get("heritage_building")) or _is_yes_answer(
        parsed.get("heritage_precinct")
    )

    # Prefer parsed values; fall back to request-provided context
    cts_nos = parsed.get("cts_nos")
    resolved_cts = cts_no or (cts_nos[0] if cts_nos else None)

    return DPReportResponse(
        status=DPReportStatus.COMPLETED,
        ward=parsed.get("ward") or ward,
        village=parsed.get("village") or village,
        cts_no=resolved_cts,
        report_type=parsed.get("report_type"),
        reference_no=parsed.get("reference_no"),
        report_date=parsed.get("report_date"),
        applicant_name=parsed.get("applicant_name"),
        cts_nos=cts_nos,
        fp_no=parsed.get("fp_no"),
        tps_name=parsed.get("tps_name"),
        zone_code=parsed.get("zone_code"),
        zone_name=parsed.get("zone_name"),
        road_width_m=parsed.get("road_width_m"),
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
        heritage_buffer_zone=parsed.get("heritage_buffer"),
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
        crz_zone=crz_zone,
        heritage_zone=heritage_zone,
        pdf_text=None,  # omit raw text from response to keep payload small
        created_at=datetime.utcnow(),
    )


# ── Health ────────────────────────────────────────────────────────────────────


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "dp_report_service",
        "arcgis_layer_cached": DPArcGISClient._zone_layer_url is not None,
    }
