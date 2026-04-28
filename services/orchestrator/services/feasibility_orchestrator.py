"""
Feasibility Analysis Orchestrator Service
Orchestrates all microservices for full feasibility analysis.
"""

import asyncio
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks

from dhara_shared.services.cache import redis_cache
from dhara_shared.services.http import AsyncHTTPClient

from ..core.config import settings
from ..db import async_session_factory
from ..models import FeasibilityReport, ReportStatus
from .cloudinary import upload_content
from .dossier_service import dossier_service

logger = logging.getLogger(__name__)

# In-memory store: job_id -> report file path (survives request lifecycle)
_REPORT_STORE: dict[str, str] = {}

# Where to write generated reports (inside the orchestrator's working dir)
_REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "./generated_reports"))
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MCGM_URL = settings.MCGM_PROPERTY_URL
SITE_ANALYSIS_URL = settings.SITE_ANALYSIS_URL
DP_REMARKS_URL = settings.DP_REPORT_URL
PR_CARD_URL = settings.PR_CARD_URL
AVIATION_HEIGHT_URL = settings.HEIGHT_URL
READY_RECKONER_URL = settings.READY_RECKONER_URL
REPORT_GENERATOR_URL = settings.REPORT_URL
OCR_URL = settings.OCR_URL


_RR_VILLAGE_MAP: dict[str, tuple[str, str]] = {
    # (village_lower_no_spaces): (rr_locality, taluka)
    "vileparle": ("vile-parle-west", "andheri"),
    "vileparlewest": ("vile-parle-west", "andheri"),
    "vileparleeast": ("vile-parle-east", "andheri"),
    "andheri": ("andheri", "andheri"),
    "andheriwest": ("andheri", "andheri"),
    "andherieast": ("andheri", "andheri"),
    "bandra": ("bandra-a", "andheri"),
    "bandrawest": ("bandra-a", "andheri"),
    "bandraeast": ("bandra-e", "andheri"),
    "kurla": ("kurla", "kurla"),
    "dharavi": ("dharavi", "kurla"),
    "borivali": ("borivali", "borivali"),
    "malad": ("malad", "borivali"),
    "kandivali": ("kandivali", "borivali"),
    "goregaon": ("goregaon", "borivali"),
    "jogeshwari": ("jogeshwari", "andheri"),
    "santacruz": ("santacruz", "andheri"),
    "khar": ("khar", "andheri"),
    "juhu": ("juhu", "andheri"),
}


def _rr_locality_from_req(req: dict) -> tuple[str, str]:
    """Derive (rr_locality, taluka) from req village + ward for Ready Reckoner lookup."""
    village = (req.get("village") or "").strip()
    ward = (req.get("ward") or "").upper()

    # Normalize: lowercase, remove spaces/hyphens/dots
    key = village.lower().replace(" ", "").replace("-", "").replace(".", "")

    # Disambiguate Vile Parle by ward: K/W = West, K/E = East
    if key == "vileparle":
        if "W" in ward:
            key = "vileparlewest"
        elif "E" in ward:
            key = "vileparleeast"

    if key in _RR_VILLAGE_MAP:
        return _RR_VILLAGE_MAP[key]

    # Generic slug fallback: use village as-is with andheri taluka for suburban areas
    slug = village.lower().replace(" ", "-").replace("/", "-")
    taluka = "andheri" if ward and ward[0] in ("H", "K", "P", "R", "S") else "mumbai-city"
    return slug or "bhuleshwar", taluka


class FeasibilityOrchestrator:
    """Orchestrates all microservices for feasibility analysis."""

    async def analyze(
        self,
        req: dict,
        background_tasks: BackgroundTasks | None = None,
        user_id: str | None = None,
        report_id: str | None = None,
    ) -> dict:
        """
        Main orchestration method. Now supports persistence via user_id and report_id.
        """
        job_id = report_id or str(uuid4())
        logger.info(f"[{job_id}] Starting feasibility analysis")

        # Step 0: Ensure a DB record exists if we have a user_id
        if user_id and not report_id:
            try:
                async with async_session_factory() as db:
                    new_report = FeasibilityReport(
                        id=job_id,
                        user_id=user_id,
                        society_id=req.get("society_id"),
                        title=req.get("title", f"Analysis: {req.get('society_name', 'Unnamed')}"),
                        status=ReportStatus.PROCESSING,
                        input_data=req,
                    )
                    db.add(new_report)
                    await db.commit()
            except Exception as e:
                logger.warning(f"[{job_id}] Could not create initial report record: {e}")

        # Step 0: Resolve CTS/FP
        cts_no = req.get("cts_no")
        fp_no = req.get("fp_no")
        if cts_no or fp_no:
            from .cts_fp_resolver import get_resolver

            resolver = get_resolver()
            res = await resolver.resolve(
                cts_no=cts_no,
                fp_no=fp_no,
                village=req.get("village"),
                ward=req.get("ward"),
                address=req.get("address"),
            )
            if res:
                if res.cts_no:
                    req["cts_no"] = res.cts_no
                if res.fp_no:
                    req["fp_no"] = res.fp_no
                if res.tps_name:
                    req["tps_name"] = res.tps_name
                # ArcGIS location data is authoritative
                if res.extra:
                    ext = res.extra
                    if not req.get("ward"):
                        req["ward"] = ext.get("ward")
                    if not req.get("village"):
                        req["village"] = ext.get("village")
                    if not req.get("taluka"):
                        req["taluka"] = ext.get("taluka")
                    if not req.get("district"):
                        req["district"] = ext.get("district")
                    if not req.get("plot_area_sqm") and ext.get("area_sqm"):
                        req["plot_area_sqm"] = float(ext["area_sqm"])
                logger.info(f"[{job_id}] CTS/FP resolved: {req.get('cts_no')} / {req.get('fp_no')}")
                # Persist resolved CTS/FP/TPS back to society DB record
                society_id = req.get("society_id")
                if society_id:
                    try:
                        from ..models.society import Society

                        async with async_session_factory() as db:
                            soc = await db.get(Society, society_id)
                            if soc:
                                if res.cts_no and not soc.cts_no:
                                    soc.cts_no = res.cts_no
                                if res.fp_no and not soc.fp_no:
                                    soc.fp_no = res.fp_no
                                if res.tps_name and not soc.tps_name:
                                    soc.tps_name = res.tps_name
                                if res.extra:
                                    ext = res.extra
                                    if ext.get("ward") and not soc.ward:
                                        soc.ward = ext["ward"]
                                    if ext.get("village") and not soc.village:
                                        soc.village = ext["village"]
                                    if ext.get("taluka") and not soc.taluka:
                                        soc.taluka = ext["taluka"]
                                    if ext.get("district") and not soc.district:
                                        soc.district = ext["district"]
                                    if ext.get("area_sqm") and not soc.plot_area_sqm:
                                        soc.plot_area_sqm = float(ext["area_sqm"])
                                await db.commit()
                                logger.info(
                                    f"[{job_id}] Saved resolved CTS/FP to society {society_id}"
                                )
                    except Exception as db_err:
                        logger.warning(f"[{job_id}] Could not save CTS/FP to DB: {db_err}")

        # Round 1: parallel calls to 4 services
        round1_results = await self.run_round1(req, job_id=job_id)
        await dossier_service.update_dossier(job_id, "round1", round1_results)
        logger.info(f"[{job_id}] Round 1 completed and saved to dossier")

        # Extract dependencies for Round 2
        # Try multiple sources for lat/lng (MCGM, site_analysis)
        mc_result = round1_results.get("mcgm", {})
        sa_result = round1_results.get("site_analysis", {})

        # Prioritize explicit lat/lng from request, fallback to MCGM or Site Analysis
        lat = req.get("lat") or mc_result.get("centroid_lat") or mc_result.get("lat") or sa_result.get("lat")
        lng = req.get("lng") or mc_result.get("centroid_lng") or mc_result.get("lng") or sa_result.get("lng")

        # DP Remarks may return zone_code or zone
        zone = round1_results.get("dp_remarks", {}).get("zone_code") or round1_results.get(
            "dp_remarks", {}
        ).get("zone")

        logger.info(f"[{job_id}] Round 1 extracted: lat={lat}, lng={lng}, zone={zone}")

        # Round 2: dependent services — pass req for locality context
        round2_results = await self.run_round2(lat, lng, zone, req, job_id=job_id)
        await dossier_service.update_dossier(job_id, "round2", round2_results)
        logger.info(f"[{job_id}] Round 2 completed and saved to dossier")

        # Round 3: forward aggregated data to report generator
        report_path = None
        report_url = None
        report_error = None
        try:
            async with AsyncHTTPClient(timeout=300.0, request_id=job_id) as client:
                report_bytes = await self.call_report_generator(
                    client, round1_results, round2_results, req
                )
            # 1. Save locally as fallback/cache
            report_filename = f"feasibility_{job_id}.xlsx"
            report_path = str(_REPORTS_DIR / report_filename)
            Path(report_path).write_bytes(report_bytes)
            _REPORT_STORE[job_id] = report_path

            # 2. Upload to Cloudinary only when SAVE_REPORTS_LOCALLY is False
            if not getattr(settings, "SAVE_REPORTS_LOCALLY", True):
                try:
                    upload_res = await upload_content(
                        content=report_bytes,
                        filename=report_filename,
                        folder="dhara/reports",
                        resource_type="raw",
                    )
                    report_url = upload_res.get("secure_url")
                    logger.info(f"[{job_id}] Report uploaded to Cloudinary: {report_url}")
                except Exception as ue:
                    logger.warning(
                        f"[{job_id}] Cloudinary upload failed (falling back to local): {ue}"
                    )
            else:
                logger.info(
                    f"[{job_id}] SAVE_REPORTS_LOCALLY=True — skipping Cloudinary, report at {report_path}"
                )

            logger.info(f"[{job_id}] Round 3 done — generated report for {job_id}")

            if background_tasks:
                background_tasks.add_task(self._check_expiries, job_id, req)
        except Exception as e:
            report_error = str(e)
            logger.error(f"[{job_id}] Round 3 (report generation) failed: {e}")

        final_result = {
            "job_id": job_id,
            "status": "completed" if not report_error else "failed",
            "round1_results": round1_results,
            "round2_results": round2_results,
            "report_generated": report_path is not None,
            "report_url": report_url,
            "report_error": report_error,
        }

        await dossier_service.update_dossier(job_id, "final_result", final_result)

        # Update DB with final results if we have a job_id record
        try:
            async with async_session_factory() as db:
                report = await db.get(FeasibilityReport, job_id)
                if report:
                    report.status = (
                        ReportStatus.COMPLETED if not report_error else ReportStatus.FAILED
                    )
                    report.report_path = report_path
                    report.file_url = report_url  # Cloudinary URL
                    report.output_data = {
                        "round1": round1_results,
                        "round2": round2_results,
                        "report_generated": report_path is not None,
                        "report_url": report_url,
                        "report_error": report_error,
                    }
                    if report_error:
                        report.error_message = report_error
                    await db.commit()
        except Exception as e:
            logger.warning(f"[{job_id}] Could not finalize report record: {e}")

        return {
            "job_id": job_id,
            "status": "completed" if not report_error else "failed",
            "round1_results": round1_results,
            "round2_results": round2_results,
            "report_generated": report_path is not None,
            "report_url": report_url,
            "report_error": report_error,
        }

    async def run_round1(self, req: dict, job_id: str | None = None) -> dict:
        """Call all Round 1 services in parallel (4 core + optional OCR)."""

        async with AsyncHTTPClient(timeout=300.0, request_id=job_id) as client:
            tasks = [
                self.call_pr_card(client, req),
                self.call_mcgm(client, req),
                self.call_site_analysis(client, req),
                self.call_dp_remarks(client, req),
            ]
            # OCR service: old building plan / occupancy certificate
            import base64

            ocr_pdf_bytes = req.get("ocr_pdf_bytes")
            if not ocr_pdf_bytes and req.get("ocr_pdf_b64"):
                ocr_pdf_bytes = base64.b64decode(req["ocr_pdf_b64"])
            if ocr_pdf_bytes:
                tasks.append(
                    self.call_ocr_service(
                        client,
                        ocr_pdf_bytes,
                        doc_type="old_plan",
                        filename="old_plan.pdf",
                        content_type="application/pdf",
                    )
                )

            # Tenements sheet: CSV/XLSX/PDF listing units for flat/commercial counts
            tenements_pdf_bytes = None
            tenements_filename = req.get("tenements_sheet_filename", "tenements.pdf")
            tenements_content_type = req.get("tenements_sheet_content_type", "application/pdf")
            if req.get("tenements_sheet_b64"):
                tenements_pdf_bytes = base64.b64decode(req["tenements_sheet_b64"])
                tasks.append(
                    self.call_ocr_service(
                        client,
                        tenements_pdf_bytes,
                        doc_type="tenements_sheet",
                        filename=tenements_filename,
                        content_type=tenements_content_type,
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

            out = {
                "pr_card": results[0]
                if not isinstance(results[0], Exception)
                else {"error": str(results[0])},
                "mcgm": results[1]
                if not isinstance(results[1], Exception)
                else {"error": str(results[1])},
                "site_analysis": results[2]
                if not isinstance(results[2], Exception)
                else {"error": str(results[2])},
                "dp_remarks": results[3]
                if not isinstance(results[3], Exception)
                else {"error": str(results[3])},
            }
            idx = 4
            if ocr_pdf_bytes:
                out["ocr"] = (
                    results[idx]
                    if not isinstance(results[idx], Exception)
                    else {"error": str(results[idx])}
                )
                idx += 1
            if tenements_pdf_bytes:
                out["tenements_ocr"] = (
                    results[idx]
                    if not isinstance(results[idx], Exception)
                    else {"error": str(results[idx])}
                )
            return out

    async def run_round2(
        self,
        lat: float | None,
        lng: float | None,
        zone: str | None,
        req: dict = None,
        job_id: str | None = None,
    ) -> dict:
        """Call Round 2 dependent services."""
        req = req or {}
        async with AsyncHTTPClient(timeout=300.0, request_id=job_id) as client:
            tasks = []

            # Aviation Height needs lat/lng
            if lat and lng:
                tasks.append(self.call_aviation_height(client, lat, lng))
            else:

                async def no_lat_lng():
                    return {"error": "No lat/lng available"}

                tasks.append(no_lat_lng())

            # Ready Reckoner needs zone + req context
            if zone:
                tasks.append(self.call_ready_reckoner(client, zone, req))
            else:

                async def no_zone():
                    return {"error": "No zone available"}

                tasks.append(no_zone())

            results = await asyncio.gather(*tasks, return_exceptions=True)

            return {
                "aviation_height": results[0]
                if not isinstance(results[0], Exception)
                else {"error": str(results[0])},
                "ready_reckoner": results[1]
                if not isinstance(results[1], Exception)
                else {"error": str(results[1])},
            }

    # ─── Individual service calls ─────────────────────────────────────

    @redis_cache(prefix="pr_card", ttl=86400)
    async def call_pr_card(self, client: AsyncHTTPClient, req: dict) -> dict:
        """Call PR Card Scraper service."""
        try:
            resp = await client.post(
                f"{PR_CARD_URL}/scrape/sync",
                json={
                    # Ensure required fields are non-null strings; fall back sensibly
                    "district": (req.get("district") or "Mumbai").strip(),
                    "taluka": (req.get("taluka") or "Mumbai").strip(),
                    "village": (req.get("village") or "")
                    .replace("-WEST", "")
                    .replace("-EAST", "")
                    .strip(),
                    # PR Card accepts Survey/CTS/Gat — prefer CTS if present, then survey_no, then FP
                    "survey_no": (req.get("cts_no") or req.get("survey_no") or req.get("fp_no") or "").strip(),
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"PR Card call failed: {e}")
            return {"error": str(e)}

    @redis_cache(prefix="mcgm", ttl=86400)
    async def call_mcgm(self, client: AsyncHTTPClient, req: dict) -> dict:
        """Call MCGM Property Lookup service."""
        try:
            cts_no = req.get("cts_no") or req.get("fp_no", "")
            resp = await client.post(
                f"{MCGM_URL}/lookup/sync",
                json={
                    "ward": req.get("ward", "M/E"),
                    "village": req.get("village", "")
                    .replace("-WEST", "")
                    .replace("-EAST", "")
                    .strip(),
                    "cts_no": cts_no,
                    "use_fp": req.get("use_fp_scheme", False),
                    "tps_name": req.get("tps_name"),
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"MCGM call failed: {e}")
            return {"error": str(e)}

    async def call_site_analysis(self, client: AsyncHTTPClient, req: dict) -> dict:
        """Call Site Analysis service."""
        try:
            resp = await client.post(
                f"{SITE_ANALYSIS_URL}/analyse",
                json={
                    "address": req.get("address", ""),
                    "ward": req.get("ward"),
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Site Analysis call failed: {e}")
            return {"error": str(e)}

    async def call_dp_remarks(self, client: AsyncHTTPClient, req: dict) -> dict:
        """Call DP Remarks service.

        Strategy (in priority order):
        1. If dp_remark_pdf_b64 present → POST PDF to /fetch/from-pdf (no Playwright needed).
        2. Try /fetch/sync with CTS number (1991 scheme, web scraper).
        3. Retry /fetch/sync with FP number + TPS (2034 scheme fallback).
        """
        import base64

        import httpx

        # ── Strategy 1: PDF upload (preferred for testing) ─────────────────
        dp_pdf_b64 = req.get("dp_remark_pdf_b64")
        if dp_pdf_b64:
            try:
                pdf_bytes = base64.b64decode(dp_pdf_b64)
                async with httpx.AsyncClient(timeout=120.0) as raw_client:
                    resp = await raw_client.post(
                        f"{DP_REMARKS_URL}/fetch/from-pdf",
                        files={"file": ("dp_remark.pdf", pdf_bytes, "application/pdf")},
                        data={
                            "ward": req.get("ward", ""),
                            "village": req.get("village", ""),
                            "cts_no": req.get("cts_no", ""),
                        },
                    )
                resp.raise_for_status()
                result = resp.json()
                logger.info(
                    f"DP Remarks: parsed from PDF — zone={result.get('zone_code')}, village={result.get('village')}"
                )
                return result
            except Exception as e_pdf:
                logger.warning(f"DP Remarks PDF parse failed ({e_pdf}); trying web fallback")

        # ── Strategy 2 & 3: Web scraper ────────────────────────────────────
        cts_no = req.get("cts_no")
        fp_no = req.get("fp_no", "")
        base_payload = {
            "ward": req.get("ward", "M/E"),
            "village": req.get("village", ""),
            "lat": req.get("lat"),
            "lng": req.get("lng"),
        }
        try:
            resp = await client.post(
                f"{DP_REMARKS_URL}/fetch/sync",
                json={**base_payload, "cts_no": cts_no or fp_no, "use_fp_scheme": False},
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("cts_not_found") and fp_no:
                raise ValueError("CTS not in dropdown — retrying with FP")
            return result
        except Exception as e_cts:
            logger.warning(f"DP Remarks CTS attempt failed ({e_cts}); trying FP fallback")
            try:
                resp = await client.post(
                    f"{DP_REMARKS_URL}/fetch/sync",
                    json={
                        **base_payload,
                        "cts_no": fp_no,
                        "use_fp_scheme": True,
                        "tps_name": req.get("tps_name"),
                    },
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e_fp:
                logger.warning(f"DP Remarks FP fallback also failed: {e_fp}")
                return {"error": str(e_fp)}

    async def call_aviation_height(self, client: AsyncHTTPClient, lat: float, lng: float) -> dict:
        """Call Aviation Height service."""
        try:
            resp = await client.post(
                f"{AVIATION_HEIGHT_URL}/check-height", json={"lat": lat, "lng": lng}
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Aviation Height call failed: {e}")
            return {"error": str(e)}

    async def call_ready_reckoner(
        self, client: AsyncHTTPClient, zone: str, req: dict = None
    ) -> dict:
        """Call Ready Reckoner service with proper locality + zone + plot_area inputs.

        Returns normalized dict with rr_open_land_sqm and sale rates extracted
        from rr_rates[] for direct use in the template.
        """
        req = req or {}
        try:
            locality, taluka = _rr_locality_from_req(req)
            payload = {
                "zone": str(zone),
                "locality": locality,
                "district": "mumbai",
                "taluka": taluka,
                "plot_area_sqm": req.get("plot_area_sqm") or 0.0,
                "property_type": "residential",
                "property_area_sqm": req.get("plot_area_sqm") or 0.0,
            }
            resp = await client.post(
                f"{READY_RECKONER_URL}/calculate",
                json=payload,
            )
            resp.raise_for_status()
            raw = resp.json()

            # The response is wrapped in InternalServiceResponse {status, data, error}
            data = raw.get("data") or {}
            rr_rates = data.get("rr_rates", [])

            # Normalize: extract per-category rates from rr_rates[]
            rates = {r["category"].lower(): r["value"] for r in rr_rates}
            rr_open = rates.get("land") or rates.get("open land") or 0
            rr_res = rates.get("residential") or rr_open
            rr_shop = rates.get("shop") or rates.get("office") or rr_open * 1.5

            return {
                # Preserve the extracted data block
                "rr_data": data,
                # Flat keys that template YAML reads via ready_reckoner.*
                "rr_open_land_sqm": rr_open,
                "rr_residential_sqm": rr_res,
                "rr_shop_sqm": rr_shop,
                # Sale rates (per sqft) derived from RR land rate for the zone
                # Typical Mumbai market: ~35–45% premium over RR
                "sale_rate_residential": round(rr_res / 10.764 * 1.4) if rr_res else 50000,
                "sale_rate_commercial_gf": round(rr_shop / 10.764 * 1.4) if rr_shop else 75000,
                "parking_price_per_unit": 1_200_000,
            }
        except Exception as e:
            logger.warning(f"Ready Reckoner call failed: {e}")
            return {"error": str(e)}

    async def call_ocr_service(
        self,
        client: AsyncHTTPClient,
        file_bytes: bytes,
        doc_type: str = "old_plan",
        filename: str = "document.pdf",
        content_type: str = "application/pdf",
    ) -> dict:
        """Call OCR service to extract fields from a document.

        doc_type="old_plan"        → Occupancy/Completion Certificate (carpet areas, BUA, age)
        doc_type="tenements_sheet" → CSV/XLSX/PDF list of units (num_flats, num_commercial)
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as raw_client:
                resp = await raw_client.post(
                    f"{OCR_URL}/extract",
                    files={"file": (filename, file_bytes, content_type)},
                    data={"doc_type": doc_type},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"OCR service call failed ({doc_type}): {type(e).__name__}: {e}")
            return {"error": f"{type(e).__name__}: {e}"}

    async def call_report_generator(
        self,
        client: AsyncHTTPClient,
        round1: dict,
        round2: dict,
        req: dict,
    ) -> bytes:
        """
        Map orchestrator results to TemplateReportRequest and call
        the report generator service.

        Key remapping (orchestrator → report_generator YAML paths):
          round1["mcgm"]       → mcgm_property
          round1["dp_remarks"] → dp_report
          round2["aviation_height"] → height
          round2["ready_reckoner"]  → ready_reckoner  (same name)
          round1["site_analysis"]   → site_analysis   (same name)
        """
        mcgm = round1.get("mcgm", {}) or {}
        dp = round1.get("dp_remarks", {}) or {}
        pr_card = round1.get("pr_card", {}) or {}
        site = round1.get("site_analysis", {}) or {}
        aviation = round2.get("aviation_height", {}) or {}
        rr = round2.get("ready_reckoner", {}) or {}
        ocr = round1.get("ocr", {}) or {}
        tenements_ocr = round1.get("tenements_ocr", {}) or {}

        # MCGM building_data: scraped from property popup (floors, usage, etc.)
        building_data = mcgm.get("building_data") or {}
        pr_card_extracted = pr_card.get("extracted_data") or {}

        # ── Scalar fields: best-source priority ──────────────────────────────
        society_name = (
            pr_card.get("society_name")
            or mcgm.get("society_name")
            or req.get("address", "Unknown Society")
        )
        # Plot area: PR Card > MCGM area_sqm > ArcGIS area > req override
        plot_area_sqm = (
            pr_card.get("area_sqm")
            or pr_card_extracted.get("area_sqm")
            or mcgm.get("area_sqm")
            or mcgm.get("plot_area_sqm")
            or req.get("plot_area_sqm")
        )
        road_width_m = dp.get("road_width_m") or site.get("road_width_m") or req.get("road_width_m")
        # num_flats: tenements sheet OCR (highest) > req (manual entry) > PR Card > MCGM > OCR old plan
        num_flats = int(
            tenements_ocr.get("num_flats")
            or req.get("num_flats")
            or pr_card.get("num_flats")
            or building_data.get("num_flats")
            or mcgm.get("num_flats")
            or ocr.get("num_flats")
            or 0
        )
        num_commercial = int(
            tenements_ocr.get("num_commercial")
            or req.get("num_commercial")
            or pr_card.get("num_commercial")
            or building_data.get("num_commercial")
            or mcgm.get("num_commercial")
            or ocr.get("num_commercial")
            or 0
        )
        # OCR-sourced carpet areas (sqft): OCR service > pr_card > req
        residential_area_sqft = (
            ocr.get("existing_residential_carpet_sqft")
            or pr_card.get("residential_area_sqft")
            or pr_card.get("existing_residential_carpet_sqft")
            or req.get("residential_area_sqft")
            or req.get("existing_residential_carpet_sqft")
        )
        commercial_area_sqft = (
            ocr.get("existing_commercial_carpet_sqft")
            or pr_card.get("commercial_area_sqft")
            or pr_card.get("existing_commercial_carpet_sqft")
            or req.get("commercial_area_sqft")
            or req.get("existing_commercial_carpet_sqft")
        )

        # society_age and existing_bua: OCR service > building_data > req
        society_age = (
            ocr.get("society_age") or building_data.get("society_age") or req.get("society_age")
        )
        existing_bua_sqft = (
            ocr.get("existing_total_bua_sqft")
            or building_data.get("existing_bua_sqft")
            or req.get("existing_bua_sqft")
            # Fallback to carpet sum * 1.2 if missing
            or ((float(residential_area_sqft or 0) + float(commercial_area_sqft or 0)) * 1.2)
        )
        # Old setback from old plan OCR (N20)
        old_setback_sqm = ocr.get("setback_area_sqm") or req.get("old_setback_sqm")

        # ── Financial rates: RR service > manual override > defaults ─────────
        # rr dict already has flat keys injected by _call_ready_reckoner()
        caller_financial = req.get("financial") or {}
        financial = {
            # RR-derived sale rates (per sqft)
            "sale_rate_residential": rr.get("sale_rate_residential")
            or caller_financial.get("sale_rate_residential")
            or 50000,
            "sale_rate_commercial_gf": rr.get("sale_rate_commercial_gf")
            or caller_financial.get("sale_rate_commercial_gf")
            or 75000,
            "sale_rate_commercial_1f": caller_financial.get("sale_rate_commercial_1f") or 60000,
            "sale_rate_commercial_2f": caller_financial.get("sale_rate_commercial_2f") or 0,
            "sale_rate_commercial_other": caller_financial.get("sale_rate_commercial_other") or 0,
            "parking_price_per_unit": rr.get("parking_price_per_unit")
            or caller_financial.get("parking_price_per_unit")
            or 1_200_000,
            # Merge any other caller overrides
            **{
                k: v
                for k, v in caller_financial.items()
                if k
                not in (
                    "sale_rate_residential",
                    "sale_rate_commercial_gf",
                    "parking_price_per_unit",
                )
            },
        }

        # Enrich mcgm_property blob with village and resolved identifiers
        mcgm_enriched = {
            **mcgm,
            "cts_no": mcgm.get("cts_no") or req.get("cts_no"),
            "fp_no": mcgm.get("fp_no") or req.get("fp_no"),
            "tps_name": mcgm.get("tps_name") or req.get("tps_name"),
            "village": mcgm.get("village") or req.get("village", ""),
            "area_sqm": plot_area_sqm or mcgm.get("area_sqm"),
        }

        # Derive noc_civil_aviation from aviation height result if not already in manual_inputs
        manual_inputs = dict(req.get("manual_inputs") or {})

        # Propagate old_setback_sqm from OCR into manual_inputs for N20
        if old_setback_sqm and "old_setback_sqm" not in manual_inputs:
            manual_inputs["old_setback_sqm"] = old_setback_sqm

        # Propagate top-level user fields into manual_inputs
        for _field in (
            "bankGuranteeCommercial",
            "bankGuranteeResidential",
            "costAcquisition79a",
            "salableResidentialRatePerSqFt",
            "carsToSellRatePerCar",
            "saleAreaBreakup",
        ):
            if _field not in manual_inputs and req.get(_field) is not None:
                manual_inputs[_field] = req[_field]

        if "noc_civil_aviation" not in manual_inputs:
            # aviation may be {"status":..., "data":{...}} — unwrap if needed
            _avi = aviation.get("data", aviation) if isinstance(aviation.get("data"), dict) else aviation
            restriction = (_avi.get("restriction_reason") or "").lower()
            noc_required = bool(_avi.get("max_height_m")) or bool(
                restriction and restriction != "no restriction"
            )
            manual_inputs["noc_civil_aviation"] = 1 if noc_required else 0

        # M1: populate CTS/FP label from user-supplied identifier
        if "cts_fp_no_label" not in manual_inputs:
            cts_val = req.get("cts_no") or req.get("fp_no") or ""
            manual_inputs["cts_fp_no_label"] = f"Cts No. /FP No.:- {cts_val}".strip()

        # J45: saleCommercialMunBuaSqFt is a PERCENTAGE — compute actual commercial BUA sqft
        # commercial_bua_sqft = (pct / 100) × existing_total_bua_sqft
        commercial_bua_pct = manual_inputs.get("commercial_bua_sqft")  # stored as pct from /submit
        if commercial_bua_pct is not None and existing_bua_sqft:
            try:
                computed_bua = (float(commercial_bua_pct) / 100.0) * float(existing_bua_sqft)
                manual_inputs["commercial_bua_sqft"] = computed_bua
            except (TypeError, ValueError):
                pass

        payload = {
            # Meta
            "society_name": society_name,
            "scheme": req.get("scheme", "33(7)(B)"),
            "redevelopment_type": req.get("redevelopment_type", "CLUBBING"),
            "ward": req.get("ward"),
            # Scalar fields (top-level, read directly by cell_mapper)
            "plot_area_sqm": plot_area_sqm,
            "road_width_m": road_width_m,
            "num_flats": num_flats,
            "num_commercial": num_commercial,
            "society_age": society_age,
            "existing_bua_sqft": existing_bua_sqft,
            # OCR-derived carpet areas and setback
            "existing_residential_carpet_sqft": residential_area_sqft,
            "existing_commercial_carpet_sqft": commercial_area_sqft,
            "old_setback_sqm": old_setback_sqm,
            # Microservice blobs — key names must match YAML `from:` paths
            "mcgm_property": mcgm_enriched,
            "dp_report": dp,
            "site_analysis": site,
            "height": aviation,
            "ready_reckoner": rr,
            # Financial rates (RR-derived + caller overrides)
            "financial": financial,
            "manual_inputs": manual_inputs,
            "premium": {},
            "zone_regulations": {},
            "fsi": {},
            "bua": {},
        }

        resp = await client.post(
            f"{REPORT_GENERATOR_URL}/generate/feasibility-report",
            json=payload,
        )
        resp.raise_for_status()
        return resp.content

    async def _check_expiries(self, job_id: str, req: dict):
        """Check for red cells in the generated report and send notifications if close to expiry."""
        try:
            import openpyxl

            from .email import send_email

            report_path = _REPORT_STORE.get(job_id)
            if not report_path or not os.path.exists(report_path):
                return

            wb = openpyxl.load_workbook(report_path)
            red_found = []

            # Scan Details sheet for red cells (FFFF0000)
            if "Details" in wb.sheetnames:
                ws = wb["Details"]
                for row in ws.iter_rows(min_row=1, max_row=100, min_col=1, max_col=20):
                    for cell in row:
                        if (
                            getattr(cell, "fill", None)
                            and getattr(cell.fill, "fgColor", None)
                            and cell.fill.fgColor.rgb == "FFFF0000"
                        ):
                            val = str(cell.value or "")
                            red_found.append(f"{cell.coordinate}: {val}")

            if red_found:
                soc_name = req.get("society_name") or "Unknown Society"
                subject = f"⚠️ Expiry Warning: {soc_name} Feasibility Report"

                items_html = "".join([f"<li><strong>{item}</strong></li>" for item in red_found])
                body = f"""
                <html>
                <body style="font-family: sans-serif;">
                    <h2 style="color: #c62828;">Critical Expiry Warning</h2>
                    <p>The feasibility report for <strong>{soc_name}</strong> (Job: {job_id}) contains fields marked for expiry:</p>
                    <ul style="background: #ffebee; padding: 20px; border-radius: 8px; list-style: none;">
                        {items_html}
                    </ul>
                    <p>These values need to be updated as their validity period is ending soon.</p>
                    <hr>
                    <p style="font-size: 12px; color: #666;">This is an automated notification from Dhara AI.</p>
                </body>
                </html>
                """
                # Send to admin email as configured in settings
                await send_email(settings.SMTP_FROM_EMAIL, subject, body)
                logger.info(f"[{job_id}] Sent expiry notification for {len(red_found)} red cells")

        except Exception as e:
            logger.error(f"[{job_id}] Expiry check failed: {e}")


# Singleton instance
feasibility_orchestrator = FeasibilityOrchestrator()
