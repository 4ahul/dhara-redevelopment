import asyncio
import uuid
import os
import sys
import json as _json

service_dir = os.path.dirname(os.path.abspath(__file__))
if service_dir not in sys.path:
    sys.path.insert(0, service_dir)

# Root of the report_generator service (one level above routers/)
_svc_root = os.path.dirname(service_dir)

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from io import BytesIO

from services.report_generator.schemas.report import (
    ReportRequest,
    TemplateFieldSchema,
    TemplateFieldsResponse,
    TemplateApplyRequest,
    TemplateReportRequest,
)
from services.report_generator.logic.data_normalizer import normalize_report_data
from services.report_generator.logic.pdf_builder import build_feasibility_pdf
from services.report_generator.logic.template_service import template_service
from services.report_generator.logic.excel_to_pdf import generate_report_with_pdf
from services.report_generator.core.config import OUTPUT_DIR, settings, resolve_scheme_key
from feasibility.dispatcher import generate as feasibility_generate
from feasibility import calcs as _feasibility_calcs  # noqa: F401 — registers @register decorators

MAPPING_PATH = os.path.join(_svc_root, "mappings", "33_7_B.yaml")
TEMPLATE_PATH = os.path.join(_svc_root, "templates", "FINAL TEMPLATE _ 33 (7)(B) .xlsx")
DOSSIER_PATH = os.path.join(_svc_root, "dossiers", "33_7_B.dossier.json")

router = APIRouter()


def _build_all_data(req: TemplateReportRequest) -> dict:
    """Flatten TemplateReportRequest into the dict that cell_mapper expects.

    cell_mapper reads both nested keys (dp_report.road_width_m) and
    top-level keys (num_flats, existing_residential_carpet_sqft).
    This helper ensures ALL fields reach the mapper.
    """
    return {
        # ── Top-level scalars (cell_mapper reads these directly) ──
        "society_name": req.society_name,
        "scheme": req.scheme,
        "plot_area_sqm": req.plot_area_sqm,
        "road_width_m": req.road_width_m,
        "num_flats": req.num_flats,
        "num_commercial": req.num_commercial,
        "existing_commercial_carpet_sqft": req.existing_commercial_carpet_sqft,
        "existing_residential_carpet_sqft": req.existing_residential_carpet_sqft,
        "sale_rate_per_sqft": req.sale_rate_per_sqft,
        # ── Nested dicts from microservices ────────────────────────
        "site_analysis": req.site_analysis or {},
        "height": req.height or {},
        "premium": req.premium or {},
        "dp_report": req.dp_report or {},
        "mcgm_property": req.mcgm_property or {},
        "zone_regulations": req.zone_regulations or {},
        "ready_reckoner": req.ready_reckoner or {},
        "financial": req.financial or {},
        "fsi": req.fsi or {},
        "bua": req.bua or {},
        # ── Manual overrides (highest priority) ───────────────────
        "manual_inputs": req.manual_inputs or {},
    }


@router.post("/generate")
async def generate_report(req: ReportRequest):
    """
    Generate the feasibility report PDF.
    """
    report_id = str(uuid.uuid4())[:8].upper()
    safe_name = req.society_name.replace(" ", "_")
    pdf_filename = f"Feasibility_Report_{safe_name}_{report_id}.pdf"
    xlsx_filename = f"Feasibility_Report_{safe_name}_{report_id}.xlsx"
    pdf_path = str(OUTPUT_DIR / pdf_filename)
    xlsx_path = str(OUTPUT_DIR / xlsx_filename)

    target_scheme = req.scheme or "33(7)(B)"
    target_rd_type = req.redevelopment_type or "CLUBBING"

    all_data = {
        "society_name": req.society_name,
        "scheme": target_scheme,
        "plot_area_sqm": req.plot_area_sqm,
        "road_width_m": req.road_width_m,
        "num_flats": req.num_flats,
        "num_commercial": req.num_commercial,
        "site_analysis": req.site_analysis or {},
        "height": req.height or {},
        "premium": req.premium or {},
        "dp_report": req.dp_report or {},
        "mcgm_property": req.mcgm_property or {},
        "zone_regulations": req.zone_regulations or {},
        "ready_reckoner": req.ready_reckoner or {},
        "financial": req.financial or {},
        "fsi": req.fsi or {},
        "bua": req.bua or {},
        "manual_inputs": req.manual_inputs or {},
    }

    try:
        normalized = normalize_report_data(req.model_dump())

        await asyncio.to_thread(build_feasibility_pdf, normalized, pdf_path)

        await asyncio.to_thread(
            template_service.generate_full_report,
            scheme=target_scheme,
            all_data=all_data,
            output_path=xlsx_path,
            redevelopment_type=target_rd_type,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    return FileResponse(
        path=pdf_path,
        filename=pdf_filename,
        media_type="application/pdf",
    )


@router.get("/health")
async def health():
    return {"status": "ok", "service": "report_generator"}


@router.get("/templates/list")
async def list_available_templates():
    """List all available scheme + redevelopment_type combinations.

    Use this to discover which (scheme, redevelopment_type) pairs are valid
    before calling /generate/template.
    """
    available = []
    for key, tpl in settings.SCHEME_TEMPLATE_MAP.items():
        if key.endswith("_INSITU"):
            scheme = key.removesuffix("_INSITU")
            rd_type = "INSITU"
        else:
            scheme = key
            rd_type = "CLUBBING"
        available.append({
            "scheme": scheme,
            "redevelopment_type": rd_type,
            "template_key": key,
            "template_file": tpl,
        })
    return {"templates": available}


@router.get("/templates/fields")
async def get_template_fields(
    scheme: str = Query(..., description="Scheme like 30(A), 33(20)(B)"),
    redevelopment_type: str = Query("CLUBBING", description="CLUBBING or INSITU"),
):
    """
    Get all yellow input fields for a given scheme + redevelopment type.
    Use this to see what inputs are available in the template.
    """
    try:
        fields = template_service.get_yellow_fields(scheme, redevelopment_type)
        template_path = template_service.get_template_for_scheme(scheme, redevelopment_type)
        sheets = template_service.get_template_sheets(scheme, redevelopment_type)

        return TemplateFieldsResponse(
            scheme=scheme,
            template_file=str(template_path.name),
            sheets=sheets,
            fields=[
                TemplateFieldSchema(
                    sheet=f.sheet,
                    cell=f.cell,
                    label=f.label,
                    current_value=f.current_value,
                )
                for f in fields
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.post("/templates/apply")
async def apply_template_values(req: TemplateApplyRequest):
    """
    Apply values to yellow cells in template and return the modified Excel file.
    Use this to test dynamic value changes - provide cell coordinates and new values.
    """
    try:
        rd_type = getattr(req, "redevelopment_type", "CLUBBING") or "CLUBBING"
        excel_bytes = template_service.apply_values(req.scheme, req.values, rd_type)

        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=feasibility_{req.scheme}.xlsx"
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@router.post("/generate/template")
async def generate_template_report(req: TemplateReportRequest):
    """
    Generate feasibility report using Excel templates.
    """
    try:
        report_id = str(uuid.uuid4())[:8].upper()
        safe_name = req.society_name.replace(" ", "_")
        
        target_scheme = req.scheme
        target_rd_type = req.redevelopment_type.value if hasattr(req.redevelopment_type, "value") else str(req.redevelopment_type)

        all_data = _build_all_data(req)

        xlsx_filename = f"Feasibility_{target_scheme}_{target_rd_type}_{safe_name}_{report_id}.xlsx"
        xlsx_path = str(OUTPUT_DIR / xlsx_filename)

        excel_bytes, saved_path = template_service.generate_full_report(
            scheme=target_scheme,
            all_data=all_data,
            output_path=xlsx_path,
            redevelopment_type=target_rd_type,
        )

        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={xlsx_filename}"},
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Template report generation failed: {e}"
        )


@router.post("/generate/template-with-pdf")
async def generate_template_report_with_pdf(req: TemplateReportRequest):
    """
    Generate feasibility report using Excel templates AND create PDF. (Hardcoded to 33(20)(B) CLUBBING for testing)
    """
    try:
        report_id = str(uuid.uuid4())[:8].upper()
        safe_name = req.society_name.replace(" ", "_")
        
        # HARDCODED FOR TESTING
        test_scheme = "33(20)(B)"
        test_rd_type = "CLUBBING"

        target_scheme = req.scheme
        target_rd_type = req.redevelopment_type.value if hasattr(req.redevelopment_type, "value") else str(req.redevelopment_type)

        all_data = _build_all_data(req)

        excel_path, pdf_path = generate_report_with_pdf(
            scheme=target_scheme,
            all_data=all_data,
            output_dir=OUTPUT_DIR,
            society_name=req.society_name,
            redevelopment_type=target_rd_type,
        )

        # Return Excel for now (can add PDF return later)
        with open(excel_path, "rb") as f:
            excel_bytes = f.read()

        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=Feasibility_{target_scheme}_{target_rd_type}_{safe_name}_{report_id}.xlsx"
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Template report with PDF generation failed: {e}"
        )


@router.post("/generate/feasibility-report")
async def generate_feasibility_report(req: TemplateReportRequest):
    """Fill the 33(7)(B) template with microservice + user-input data."""
    try:
        safe_name = req.society_name.replace(" ", "_")
        report_id = str(uuid.uuid4())[:8].upper()
        xlsx_filename = f"Feasibility_33_7_B_{safe_name}_{report_id}.xlsx"
        xlsx_path = str(OUTPUT_DIR / xlsx_filename)

        resp = await asyncio.to_thread(
            feasibility_generate,
            request=_build_all_data(req),
            mapping_path=MAPPING_PATH,
            template_path=TEMPLATE_PATH,
            output_path=xlsx_path,
        )

        return StreamingResponse(
            BytesIO(resp.excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={xlsx_filename}",
                "X-Report-Missing-Fields": str(len(resp.missing_fields)),
                "X-Report-Calc-Errors": str(len(resp.calculation_errors)),
                "X-Report-Skipped-Formulas": str(len(resp.skipped_formula_cells)),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Feasibility report generation failed: {e}"
        )


@router.get("/feasibility/dossier")
async def get_feasibility_dossier(scheme: str = Query("33(7)(B)")):
    if scheme != "33(7)(B)":
        raise HTTPException(status_code=404, detail=f"No dossier for scheme {scheme}")
    try:
        with open(DOSSIER_PATH, "r", encoding="utf-8") as f:
            return _json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Dossier not generated yet")


