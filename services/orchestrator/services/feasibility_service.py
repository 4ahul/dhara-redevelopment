"""
Dhara AI — Feasibility Service
Business logic for generating and managing feasibility reports.
Refactored to use CRUD layer.
"""

import logging
import math
import asyncio
from uuid import UUID
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.report import FeasibilityReport
from models.enums import ReportStatus
from schemas.society import FeasibilityReportCreate, FeasibilityReportUpdate
from repositories import society_repository
from db import async_session_factory
from agent import run_agent

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
        society_id: UUID = None
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
            "total_pages": math.ceil(total / page_size) if total else 0
        }

    async def get_report(self, user_id: UUID, report_id: UUID) -> FeasibilityReport | None:
        """Fetch a specific report."""
        return await society_repository.get_feasibility_report(self.db, report_id, user_id)

    async def create_report(self, user_id: UUID, req: FeasibilityReportCreate, bg: BackgroundTasks) -> FeasibilityReport | None:
        """Initiate feasibility analysis."""
        soc = await society_repository.get_society_by_id(self.db, req.society_id, user_id)
        if not soc:
            return None
        
        # Prepare input data block for the AI Agent
        input_data = {
            "society_name": soc.name,
            "address": soc.address,
            "cts_no": soc.cts_no,
            "ward": soc.ward or "G/S",
            # Maharashtra land records — used by get_pr_card tool
            "district": soc.district,
            "taluka": soc.taluka,
            "village": soc.village,
            "survey_no": soc.cts_no,          # CTS number = survey number on Mahabhumi
            "plot_area_sqm": soc.plot_area_sqm or 0,
            "plot_area_with_tp": soc.plot_area_with_tp or soc.plot_area_sqm or 0,
            "road_width_m": soc.road_width_m or 27.45,
            "num_flats": soc.num_flats or 0,
            "num_commercial": soc.num_commercial or 0,
            "residential_area_sqft": soc.residential_area_sqft or 0,
            "commercial_area_sqft": soc.commercial_area_sqft or 0,
            "sale_rate": soc.sale_rate or 60000,
        }
        
        report_data = {
            "society_id": req.society_id,
            "title": req.title or "Feasibility Report",
            "status": ReportStatus.PENDING,
            "input_data": input_data
        }
        
        report = await society_repository.create_feasibility_report(self.db, user_id, report_data)
        
        # Queue the background task
        bg.add_task(self._run_agent_task, report.id, input_data)
        logger.info("Report %s queued for society %s", report.id, soc.name)
        return report

    async def update_report(self, user_id: UUID, report_id: UUID, req: FeasibilityReportUpdate) -> FeasibilityReport | None:
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
                    report_obj = (await db.execute(select(FeasibilityReport).where(FeasibilityReport.id == report_id))).scalar_one_or_none()
                    if report_obj:
                        report = report_obj
                        break
                logger.warning("Background task: Report %s not found yet (attempt %d/5). Retrying...", report_id, attempt + 1)
                await asyncio.sleep(1)
            
            if not report:
                logger.error("Background task: Report %s PERMANENTLY not found", report_id)
                return

            # 2. Run the agent and update status
            async with async_session_factory() as db:
                # We need to re-fetch to ensure we're on the latest state in THIS session
                report = (await db.execute(select(FeasibilityReport).where(FeasibilityReport.id == report_id))).scalar_one_or_none()
                
                report.status = ReportStatus.PROCESSING
                await db.commit()
                
                try:
                    # Trigger AI Agent Runner
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
            logger.error("Feasibility background task CRITICAL ERROR for %s: %s", report_id, e)
