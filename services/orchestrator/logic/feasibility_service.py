"""
Dhara AI — Feasibility Service
Business logic for generating and managing feasibility reports.
Refactored to use CRUD layer.
"""

import asyncio
import logging
import math
from uuid import UUID

from services.orchestrator.db import async_session_factory
from fastapi import BackgroundTasks
from services.orchestrator.models.enums import ReportStatus
from services.orchestrator.models.report import FeasibilityReport
from services.orchestrator.repositories import society_repository
from services.orchestrator.schemas.society import FeasibilityReportCreate, FeasibilityReportUpdate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class FeasibilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reports(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str = None,
        society_id: UUID = None,
    ) -> dict:
        """Fetch paginated feasibility reports via CRUD."""
        items, total = await society_repository.list_feasibility_reports(
            self.db, user_id, page, page_size, status, society_id
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    async def get_report(
        self, user_id: UUID, report_id: UUID
    ) -> FeasibilityReport | None:
        """Fetch a specific report."""
        return await society_repository.get_feasibility_report(
            self.db, report_id, user_id
        )

    async def create_report(
        self, user_id: UUID, req: FeasibilityReportCreate, bg: BackgroundTasks
    ) -> FeasibilityReport | None:
        """Initiate feasibility analysis."""
        soc = await society_repository.get_society_by_id(
            self.db, req.society_id, user_id
        )
        if not soc:
            return None

        # ── Resolve CTS/FP if provided in the feasibility request ────────────
        req_cts_no = getattr(req, "cts_no", None)
        req_fp_no = getattr(req, "fp_no", None)

        updates = {}
        if req_cts_no or req_fp_no:
            from services.orchestrator.logic.cts_fp_resolver import get_resolver
            resolver = get_resolver()

            res = await resolver.resolve(
                cts_no=req_cts_no,
                fp_no=req_fp_no,
                ward=soc.ward,
                village=soc.village,
                address=soc.address
            )

            if res:
                if res.cts_no:
                    updates["cts_no"] = res.cts_no
                if res.fp_no:
                    updates["fp_no"] = res.fp_no
                if res.tps_name:
                    updates["tps_name"] = res.tps_name
                updates["cts_validated"] = "true" if res.is_validated else "false"

                # If ArcGIS gave us better location details, save them
                if res.extra:
                    if res.extra.get("ward"):
                        updates["ward"] = res.extra["ward"]
                    if res.extra.get("village"):
                        updates["village"] = res.extra["village"]
                    if res.extra.get("taluka"):
                        updates["taluka"] = res.extra["taluka"]
                    if res.extra.get("district"):
                        updates["district"] = res.extra["district"]
                    if res.extra.get("area_sqm") and not soc.plot_area_sqm:
                        try:
                            updates["plot_area_sqm"] = float(res.extra["area_sqm"])
                        except (ValueError, TypeError):
                            pass

        if updates:
            soc = await society_repository.update_society_field(self.db, soc.id, updates)
            logger.info("Society %s updated with resolved CTS/FP details", soc.id)

        # Prepare input data block for the AI Agent
        input_data = {
            "society_name": soc.name,
            "address": soc.address,
            "cts_no": soc.cts_no,
            "fp_no": soc.fp_no,
            "ward": soc.ward,
            # Maharashtra land records — used by get_pr_card tool
            "district": soc.district,
            "taluka": soc.taluka,
            "village": soc.village,
            "tps_name": soc.tps_name,
            "survey_no": soc.cts_no,  # CTS number = survey number on Mahabhumi
            "plot_area_sqm": soc.plot_area_sqm or 0,
            "plot_area_with_tp": soc.plot_area_with_tp or soc.plot_area_sqm or 0,
            "road_width_m": soc.road_width_m or 27.45,
            "num_flats": getattr(req, "num_flats", None) or soc.num_flats or 0,
            "num_commercial": getattr(req, "num_commercial", None) or soc.num_commercial or 0,
            "residential_area_sqft": soc.residential_area_sqft or 0,
            "commercial_area_sqft": soc.commercial_area_sqft or 0,
            "sale_rate": soc.sale_rate or 60000,
            # ── Extracted manual UI fields ──────────────────────────────────
            "manual_inputs": {
                "basement_required": getattr(req, "basement_required", None),
                "corpus_commercial": getattr(req, "corpus_commercial", None),
                "corpus_residential": getattr(req, "corpus_residential", None),
                "sale_commercial_bua_sqft": getattr(req, "sale_commercial_bua_sqft", None),
                "const_rate_commercial": getattr(req, "const_rate_commercial", None),
                "const_rate_residential": getattr(req, "const_rate_residential", None),
                "const_rate_podium": getattr(req, "const_rate_podium", None),
                "const_rate_basement": getattr(req, "const_rate_basement", None),
                "cost_79a_acquisition": getattr(req, "cost_79a_acquisition", None),
            },
            "financial": {
                "commercial_gf_area": getattr(req, "commercial_gf_area", None),
                "sale_rate_commercial_gf": getattr(req, "sale_rate_commercial_gf", None),
                "commercial_1f_area": getattr(req, "commercial_1f_area", None),
                "sale_rate_commercial_1f": getattr(req, "sale_rate_commercial_1f", None),
                "commercial_2f_area": getattr(req, "commercial_2f_area", None),
                "sale_rate_commercial_2f": getattr(req, "sale_rate_commercial_2f", None),
                "commercial_other_area": getattr(req, "commercial_other_area", None),
                "sale_rate_commercial_other": getattr(req, "sale_rate_commercial_other", None),
                "sale_rate_residential": getattr(req, "sale_rate_residential", None),
                "parking_price_per_unit": getattr(req, "parking_price_per_unit", None),
            }
        }

        report_data = {
            "society_id": req.society_id,
            "title": req.title or "Feasibility Report",
            "status": ReportStatus.PENDING,
            "input_data": input_data,
        }

        report = await society_repository.create_feasibility_report(
            self.db, user_id, report_data
        )

        # Queue the background task
        bg.add_task(self._run_agent_task, report.id, input_data)
        logger.info("Report %s queued for society %s", report.id, soc.name)
        return report

    async def update_report(
        self, user_id: UUID, report_id: UUID, req: FeasibilityReportUpdate
    ) -> FeasibilityReport | None:
        """Update report metadata."""
        report = await self.get_report(user_id, report_id)
        if not report:
            return None

        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(report, k, v)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def _run_agent_task(self, report_id: UUID, society_data: dict):
        """Background worker thread for AI Agent orchestration."""
        try:
            # 1. Wait for report to be visible in DB across sessions
            report = None
            for attempt in range(5):
                async with async_session_factory() as db:
                    # Use a fresh session for background task
                    report_obj = (
                        await db.execute(
                            select(FeasibilityReport).where(
                                FeasibilityReport.id == report_id
                            )
                        )
                    ).scalar_one_or_none()
                    if report_obj:
                        report = report_obj
                        break
                logger.warning(
                    "Background task: Report %s not found yet (attempt %d/5). Retrying...",
                    report_id,
                    attempt + 1,
                )
                await asyncio.sleep(1)

            if not report:
                logger.error(
                    "Background task: Report %s PERMANENTLY not found", report_id
                )
                return

            # 2. Run the agent and update status
            async with async_session_factory() as db:
                # We need to re-fetch to ensure we're on the latest state in THIS session
                report = (
                    await db.execute(
                        select(FeasibilityReport).where(
                            FeasibilityReport.id == report_id
                        )
                    )
                ).scalar_one_or_none()

                report.status = ReportStatus.PROCESSING
                await db.commit()

                try:
                    # Trigger AI Agent Runner
                    from services.orchestrator.agent.runner import run_agent
                    result = await run_agent(society_data, str(report_id))

                    # Finalize results
                    report.status = ReportStatus.COMPLETED
                    report.report_path = result.get("report_path")
                    report.output_data = result
                    report.tool_log = result.get("tool_log", [])

                    if result.get("status") == "error":
                        report.status = ReportStatus.FAILED
                        report.error_message = result.get("error")

                except Exception as e:
                    report.status = ReportStatus.FAILED
                    report.error_message = str(e)
                    logger.error("AI Agent failed for report %s: %s", report_id, e)

                await db.commit()

        except Exception as e:
            logger.error(
                "Feasibility background task CRITICAL ERROR for %s: %s", report_id, e
            )




