"""Feasibility Report Routes — Refactored version using Service Layer"""

import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.dependencies import get_current_user, get_db
from ..repositories import society_repository
from ..schemas.common import PaginatedResponse
from ..schemas.feasibility import (
    FeasibilityAnalyzeRequest,
    FeasibilityAnalyzeResponse,
    FeasibilityReportCreate,
    FeasibilityReportResponse,
    FeasibilityReportUpdate,
)
from ..services.feasibility_orchestrator import (
    feasibility_orchestrator,
)
from ..services.feasibility_service import FeasibilityService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feasibility-reports", tags=["Feasibility Reports"])


def get_feasibility_service(db: AsyncSession = Depends(get_db)) -> FeasibilityService:
    return FeasibilityService(db)


def _report_to_response(report) -> dict:
    """Build a FeasibilityReportResponse dict, injecting society name."""
    data = FeasibilityReportResponse.model_validate(report)
    if hasattr(report, 'society') and report.society:
        data.society = report.society.name
    return data.model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias='pageSize'),
    status: str = Query(None),
    society_id: UUID = Query(None, alias='societyId'),
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    result = await service.list_reports(user.id, page, page_size, status, society_id)
    return PaginatedResponse(
        items=[_report_to_response(r) for r in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.post("", status_code=201)
async def create_report(
    req: FeasibilityReportCreate,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
    db: AsyncSession = Depends(get_db),
):
    report = await service.create_report(user.id, req, bg)
    if not report:
        raise HTTPException(404, "Society not found")

    # Force commit here to ensure background task sees the record
    await db.commit()

    return _report_to_response(report)


@router.get("/{report_id}")
async def get_report(
    report_id: UUID,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    report = await service.get_report(user.id, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return _report_to_response(report)


@router.patch("/{report_id}")
async def patch_report(
    report_id: UUID,
    req: FeasibilityReportUpdate,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    report = await service.update_report(user.id, report_id, req)
    if not report:
        raise HTTPException(404, "Report not found")
    return _report_to_response(report)


# ─── New Analyze Endpoint ────────────────────────────────────────────


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

    from services.orchestrator.services.redis import get_arq_or_init

    job_id = str(uuid4())
    arq = await get_arq_or_init()

    if arq:
        # Enqueue the job (Task 1)
        await arq.enqueue_job("run_feasibility_analysis", req.model_dump(), str(user.id), job_id)
        return FeasibilityAnalyzeResponse(
            job_id=job_id, status="processing", report_generated=False
        )
    else:
        # Synchronous fallback if Arq is unavailable
        result = await feasibility_orchestrator.analyze(
            req.model_dump(), background_tasks=bg, user_id=str(user.id), report_id=job_id
        )
        return FeasibilityAnalyzeResponse(**result)


@router.post("/analyze/by-society/{society_id}", response_model=FeasibilityAnalyzeResponse)
async def analyze_feasibility_by_society(
    society_id: UUID,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
):
    """Trigger full feasibility analysis from an existing society and store results."""
    from uuid import uuid4

    from services.orchestrator.services.redis import get_arq_or_init

    society = await society_repository.get_society_by_id(service.db, society_id, user.id)
    if not society:
        raise HTTPException(404, "Society not found")

    # Build request dict from society record
    req_data = {
        "society_id": society.id,
        "society_name": society.name,
        "address": society.address,
        "cts_no": society.cts_no,
        "fp_no": society.fp_no,
        "ward": society.ward,
        "village": society.village,
        "tps_name": society.tps_name,
        "num_flats": society.num_flats,
        "num_commercial": society.num_commercial,
        "plot_area_sqm": society.plot_area_sqm,
        "road_width_m": society.road_width_m,
    }

    job_id = str(uuid4())
    arq = await get_arq_or_init()

    if arq:
        await arq.enqueue_job("run_feasibility_analysis", req_data, str(user.id), job_id)
        return FeasibilityAnalyzeResponse(
            job_id=job_id, status="processing", report_generated=False
        )
    else:
        result = await feasibility_orchestrator.analyze(
            req_data, background_tasks=bg, user_id=str(user.id), report_id=job_id
        )
        return FeasibilityAnalyzeResponse(**result)


@router.post("/analyze/by-society/{society_id}/with-ocr", response_model=FeasibilityAnalyzeResponse)
async def analyze_feasibility_by_society_with_ocr(
    society_id: UUID,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
    ocr_pdf: UploadFile | None = File(None),
    dp_remark_pdf: UploadFile | None = File(None),
):
    """Trigger feasibility analysis.

    Optional file uploads:
    - ocr_pdf: Occupancy Certificate PDF → extracts carpet areas
    - dp_remark_pdf: DP Remarks PDF → extracts zone, road_width, NOC flags (bypasses Playwright)
    """
    import base64
    from uuid import uuid4

    from services.orchestrator.services.redis import get_arq_or_init

    society = await society_repository.get_society_by_id(service.db, society_id, user.id)
    if not society:
        raise HTTPException(404, "Society not found")

    req_data = {
        "society_id": society.id,
        "society_name": society.name,
        "address": society.address,
        "cts_no": society.cts_no,
        "fp_no": society.fp_no,
        "ward": society.ward,
        "village": society.village,
        "tps_name": society.tps_name,
        "num_flats": society.num_flats,
        "num_commercial": society.num_commercial,
        "plot_area_sqm": society.plot_area_sqm,
        "road_width_m": society.road_width_m,
    }

    if ocr_pdf:
        pdf_bytes = await ocr_pdf.read()
        req_data["ocr_pdf_b64"] = base64.b64encode(pdf_bytes).decode()

    if dp_remark_pdf:
        dp_bytes = await dp_remark_pdf.read()
        req_data["dp_remark_pdf_b64"] = base64.b64encode(dp_bytes).decode()

    job_id = str(uuid4())
    arq = await get_arq_or_init()

    if arq:
        await arq.enqueue_job("run_feasibility_analysis", req_data, str(user.id), job_id)
        return FeasibilityAnalyzeResponse(
            job_id=job_id, status="processing", report_generated=False
        )
    else:
        result = await feasibility_orchestrator.analyze(
            req_data, background_tasks=bg, user_id=str(user.id), report_id=job_id
        )
        return FeasibilityAnalyzeResponse(**result)


@router.post(
    "/analyze/by-society/{society_id}/submit",
    response_model=FeasibilityAnalyzeResponse,
    status_code=202,
)
async def submit_feasibility_form(
    society_id: UUID,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: FeasibilityService = Depends(get_feasibility_service),
    # Skip flag
    skipped: bool = Form(False, alias="skipped"),
    # Files
    old_plan: UploadFile | None = File(None, alias="oldPlan"),
    tenements_sheet: UploadFile | None = File(None, alias="tenementsSheet"),
    dp_remark_pdf: UploadFile | None = File(None, alias="dpRemarkPdf"),
    # Land identifier
    land_identifier_type: str | None = Form(None, alias="landIdentifierType"),
    land_identifier_value: str | None = Form(None, alias="landIdentifierValue"),
    tps_name: str | None = Form(None, alias="tpsScheme"),
    plot_area_sqm: float | None = Form(None, alias="plotAreaSqM"),
    # Tenement
    tenement_mode: str = Form("manual", alias="tenementMode"),
    number_of_tenements: int | None = Form(None, alias="numberOfTenements"),
    number_of_commercial_shops: int | None = Form(None, alias="numberOfCommercialShops"),
    # Basement
    basement_required: str | None = Form(None, alias="basementRequired"),
    # Corpus
    corpus_commercial: float | None = Form(None, alias="corpusCommercial"),
    corpus_residential: float | None = Form(None, alias="corpusResidential"),
    # Bank guarantee
    bank_guarantee_commercial: float | None = Form(None, alias="bankGuranteeCommercial"),
    bank_guarantee_residential: float | None = Form(None, alias="bankGuranteeResidential"),
    # Sale commercial MUN BUA
    sale_commercial_mun_bua_sqft: float | None = Form(None, alias="saleCommercialMunBuaSqFt"),
    # Construction costs
    commercial_area_cost_per_sqft: float | None = Form(None, alias="commercialAreaCostPerSqFt"),
    residential_area_cost_per_sqft: float | None = Form(None, alias="residentialAreaCostPerSqFt"),
    podium_parking_cost_per_sqft: float | None = Form(None, alias="podiumParkingCostPerSqFt"),
    basement_cost_per_sqft: float | None = Form(None, alias="basementCostPerSqFt"),
    # 79A
    cost_acquisition_79a: float | None = Form(None, alias="costAcquisition79a"),
    # Sale area breakup per commercial floor (JSON string)
    sale_area_breakup: str | None = Form(None, alias="saleAreaBreakup"),
    # Sale rates
    salable_residential_rate: float | None = Form(None, alias="salableResidentialRatePerSqFt"),
    cars_to_sell_rate: float | None = Form(None, alias="carsToSellRatePerCar"),
    # Zone/FSI manual overrides
    zone_code: str | None = Form(None, alias="zone_code"),
    fsi: float | None = Form(None, alias="fsi"),
):
    """Full feasibility form submission.

    - skipped=true: mark report as skipped, no analysis triggered
    - oldPlan: OCR starts immediately in background, also used in full analysis
    - tenementsSheet: OCR starts immediately in background (if tenementMode=upload)
    - dpRemarkPdf: optional DP Remark PDF (bypasses web scraper)
    """
    import base64
    import json
    from uuid import uuid4

    from services.orchestrator.services.redis import get_arq_or_init

    society = await society_repository.get_society_by_id(service.db, society_id, user.id)
    if not society:
        raise HTTPException(404, "Society not found")

    # ── skipped shortcut ─────────────────────────────────────────────────────
    if skipped:
        job_id = str(uuid4())
        return FeasibilityAnalyzeResponse(job_id=job_id, status="skipped", report_generated=False)

    # ── Read files once ───────────────────────────────────────────────────────
    old_plan_bytes: bytes | None = await old_plan.read() if old_plan else None
    tenements_bytes: bytes | None = (
        await tenements_sheet.read() if tenements_sheet and tenement_mode == "upload" else None
    )
    dp_bytes: bytes | None = await dp_remark_pdf.read() if dp_remark_pdf else None

    # ── Kick off OCR immediately in background ────────────────────────────────
    async def _run_ocr_now(
        soc_id: UUID,
        plan_bytes: bytes | None,
        t_bytes: bytes | None,
        t_filename: str,
        t_ctype: str,
        db_session,
    ):
        import httpx

        from services.orchestrator.services.feasibility_orchestrator import OCR_URL

        ocr_result: dict = {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as raw:
            if plan_bytes:
                try:
                    resp = await raw.post(
                        f"{OCR_URL}/extract",
                        files={"file": ("old_plan.pdf", plan_bytes, "application/pdf")},
                        data={"doc_type": "old_plan"},
                    )
                    resp.raise_for_status()
                    ocr_result = resp.json()
                except Exception as e:
                    logger.warning("Immediate OCR (old_plan) failed: %s", e)
            if t_bytes:
                try:
                    resp = await raw.post(
                        f"{OCR_URL}/extract",
                        files={"file": (t_filename, t_bytes, t_ctype)},
                        data={"doc_type": "tenements_sheet"},
                    )
                    resp.raise_for_status()
                    t_result = resp.json()
                    ocr_result.update({k: v for k, v in t_result.items() if v is not None})
                except Exception as e:
                    logger.warning("Immediate OCR (tenements) failed: %s", e)
        if ocr_result:
            try:
                await society_repository.update_society_field(
                    db_session,
                    soc_id,
                    {"ocr_data": {**(society.ocr_data or {}), **ocr_result}},
                )
                logger.info(
                    "Immediate OCR stored on society %s: %s", soc_id, list(ocr_result.keys())
                )
            except Exception as e:
                logger.warning("Failed to persist immediate OCR result: %s", e)

    if old_plan_bytes or tenements_bytes:
        bg.add_task(
            _run_ocr_now,
            society_id,
            old_plan_bytes,
            tenements_bytes,
            (tenements_sheet.filename if tenements_sheet else None) or "tenements.pdf",
            (tenements_sheet.content_type if tenements_sheet else None) or "application/pdf",
            service.db,
        )

    # ── Build req_data ────────────────────────────────────────────────────────
    req_data: dict = {
        "society_id": str(society.id),
        "society_name": society.name,
        "address": society.address,
        "cts_no": society.cts_no,
        "fp_no": society.fp_no,
        "ward": society.ward,
        "village": society.village,
        "tps_name": society.tps_name,
        "num_flats": society.num_flats,
        "num_commercial": society.num_commercial,
        "plot_area_sqm": society.plot_area_sqm,
        "road_width_m": society.road_width_m,
    }

    # Land identifier override
    if land_identifier_type and land_identifier_value:
        if land_identifier_type.upper() == "CTS":
            req_data["cts_no"] = land_identifier_value
            req_data["fp_no"] = ""
            req_data["use_fp_scheme"] = False
        elif land_identifier_type.upper() == "FP":
            req_data["fp_no"] = land_identifier_value
            req_data["cts_no"] = ""
            req_data["use_fp_scheme"] = True
    if tps_name:
        req_data["tps_name"] = tps_name

    # Tenement counts (manual mode)
    if tenement_mode == "manual":
        if number_of_tenements is not None:
            req_data["num_flats"] = number_of_tenements
        if number_of_commercial_shops is not None:
            req_data["num_commercial"] = number_of_commercial_shops

    # Plot area override (ensure it hits top-level for Ready Reckoner/etc)
    if plot_area_sqm is not None:
        req_data["plot_area_sqm"] = plot_area_sqm

    # Files → base64 for ARQ worker
    if old_plan_bytes:
        req_data["ocr_pdf_b64"] = base64.b64encode(old_plan_bytes).decode()
    if dp_bytes:
        req_data["dp_remark_pdf_b64"] = base64.b64encode(dp_bytes).decode()
    if tenements_bytes:
        req_data["tenements_sheet_b64"] = base64.b64encode(tenements_bytes).decode()
        req_data["tenements_sheet_filename"] = (
            (tenements_sheet.filename or "tenements.pdf") if tenements_sheet else "tenements.pdf"
        )
        req_data["tenements_sheet_content_type"] = (
            (tenements_sheet.content_type or "application/pdf")
            if tenements_sheet
            else "application/pdf"
        )

    # ── manual_inputs ─────────────────────────────────────────────────────────
    manual_inputs: dict = {}

    # basementRequired: pass as string for height/plot calcs + legacy basement_count
    if basement_required is not None:
        manual_inputs["basementRequired"] = basement_required
        manual_inputs["basement_count"] = 2 if basement_required == "yes" else 0

    if corpus_commercial is not None:
        manual_inputs["corpus_commercial"] = corpus_commercial
    if corpus_residential is not None:
        manual_inputs["corpus_residential"] = corpus_residential
    if bank_guarantee_commercial is not None:
        manual_inputs["bankGuranteeCommercial"] = bank_guarantee_commercial
    if bank_guarantee_residential is not None:
        manual_inputs["bankGuranteeResidential"] = bank_guarantee_residential
    if sale_commercial_mun_bua_sqft is not None:
        manual_inputs["commercial_bua_sqft"] = sale_commercial_mun_bua_sqft
    if commercial_area_cost_per_sqft is not None:
        manual_inputs["const_rate_commercial"] = commercial_area_cost_per_sqft
    if residential_area_cost_per_sqft is not None:
        manual_inputs["const_rate_residential"] = residential_area_cost_per_sqft
    if podium_parking_cost_per_sqft is not None:
        manual_inputs["const_rate_podium"] = podium_parking_cost_per_sqft
    if basement_cost_per_sqft is not None:
        manual_inputs["const_rate_basement"] = basement_cost_per_sqft
    if cost_acquisition_79a is not None:
        manual_inputs["costAcquisition79a"] = cost_acquisition_79a
        manual_inputs["cost_79a_acquisition"] = cost_acquisition_79a  # legacy key
    if salable_residential_rate is not None:
        manual_inputs["salableResidentialRatePerSqFt"] = salable_residential_rate
    if cars_to_sell_rate is not None:
        manual_inputs["carsToSellRatePerCar"] = cars_to_sell_rate
    if zone_code is not None:
        manual_inputs["zone_code"] = zone_code
    if fsi is not None:
        manual_inputs["fsi"] = fsi
    if plot_area_sqm is not None:
        manual_inputs["plot_area_sqm"] = plot_area_sqm

    # saleAreaBreakup: parse JSON string, store nested dict + unpack legacy keys
    if sale_area_breakup:
        try:
            breakup = json.loads(sale_area_breakup)
            manual_inputs["saleAreaBreakup"] = breakup  # nested path lookup in YAML
            # Legacy flat keys for backwards compat
            gf = breakup.get("groundFloor") or {}
            f1 = breakup.get("firstFloor") or {}
            f2 = breakup.get("secondFloor") or {}
            other = breakup.get("otherFloors") or {}
            if gf.get("area") is not None:
                manual_inputs["commercial_gf_area"] = float(gf["area"])
            if f1.get("area") is not None:
                manual_inputs["commercial_1f_area"] = float(f1["area"])
            if f2.get("area") is not None:
                manual_inputs["commercial_2f_area"] = float(f2["area"])
            if other.get("area") is not None:
                manual_inputs["commercial_other_area"] = float(other["area"])
        except (json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Could not parse saleAreaBreakup JSON: %s", sale_area_breakup[:100])

    req_data["manual_inputs"] = manual_inputs

    # financial: RR overrides (sale rates kept for backwards compat with orchestrator merger)
    financial: dict = {}
    if salable_residential_rate is not None:
        financial["sale_rate_residential"] = salable_residential_rate
    if cars_to_sell_rate is not None:
        financial["parking_price_per_unit"] = cars_to_sell_rate
    if sale_area_breakup:
        try:
            breakup = json.loads(sale_area_breakup)
            gf = breakup.get("groundFloor") or {}
            f1 = breakup.get("firstFloor") or {}
            f2 = breakup.get("secondFloor") or {}
            other = breakup.get("otherFloors") or {}
            if gf.get("rate") is not None:
                financial["sale_rate_commercial_gf"] = float(gf["rate"])
            if f1.get("rate") is not None:
                financial["sale_rate_commercial_1f"] = float(f1["rate"])
            if f2.get("rate") is not None:
                financial["sale_rate_commercial_2f"] = float(f2["rate"])
            if other.get("rate") is not None:
                financial["sale_rate_commercial_other"] = float(other["rate"])
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    req_data["financial"] = financial

    job_id = str(uuid4())
    arq = await get_arq_or_init()
    logger.error(f"DEBUG: arq is {arq}, type {type(arq)}, bool {bool(arq)}")
    if arq:
        logger.error("DEBUG: Enqueueing job in arq!")
        await arq.enqueue_job("run_feasibility_analysis", req_data, str(user.id), job_id)
        return FeasibilityAnalyzeResponse(
            job_id=job_id, status="processing", report_generated=False
        )
    else:
        result = await feasibility_orchestrator.analyze(
            req_data, background_tasks=bg, user_id=str(user.id), report_id=job_id
        )
        return FeasibilityAnalyzeResponse(**result)


@router.get("/analyze/status/{job_id}")
async def get_analyze_status(
    job_id: str,
    user=Depends(get_current_user),
):
    """Poll for progress of a feasibility analysis job."""
    from services.orchestrator.services.dossier_service import dossier_service

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
    import os

    from fastapi.responses import RedirectResponse

    from services.orchestrator.services.dossier_service import dossier_service
    from services.orchestrator.services.feasibility_orchestrator import _REPORT_STORE

    # 1. Try in-memory store (same-process generation)
    report_path = _REPORT_STORE.get(job_id)
    
    # 2. Try DB lookup (canonical source of truth for worker-generated reports)
    if not report_path:
        from ..db import async_session_factory
        from ..models import FeasibilityReport
        async with async_session_factory() as db:
            report = await db.get(FeasibilityReport, job_id)
            if report and report.report_path:
                report_path = report.report_path

    # 3. Final check on filesystem
    if not report_path:
        # Fallback to standard naming convention
        potential_path = f"generated_reports/feasibility_{job_id}.xlsx"
        if os.path.exists(potential_path):
            report_path = potential_path

    if report_path and os.path.exists(report_path):
        from fastapi.responses import FileResponse
        return FileResponse(
            path=report_path,
            filename=f"Feasibility_Report_{job_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # 4. Try Cloudinary URL from dossier
    dossier = await dossier_service.get_dossier(job_id)
    if dossier:
        file_url = dossier.get("data", {}).get("final_result", {}).get("report_url")
        if file_url:
            return RedirectResponse(url=file_url, status_code=302)

    raise HTTPException(404, f"No report found for job_id={job_id}. Run /analyze first.")
