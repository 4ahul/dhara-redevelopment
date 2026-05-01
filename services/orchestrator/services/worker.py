import logging
import os

from arq.connections import RedisSettings

from services.orchestrator.services.dossier_service import dossier_service
from services.orchestrator.services.feasibility_orchestrator import feasibility_orchestrator

logger = logging.getLogger(__name__)


async def run_feasibility_analysis(ctx, req: dict, user_id: str, report_id: str):
    """
    Background job to run the full feasibility analysis.
    This is called by the Arq worker.
    """
    logger.info(f"Worker starting analysis for report: {report_id}")

    # 1. Initialize Dossier
    await dossier_service.create_dossier(report_id, req)

    # 2. Run the actual analysis
    # Note: We pass None for background_tasks as we are already in a background worker
    result = await feasibility_orchestrator.analyze(
        req=req, background_tasks=None, user_id=user_id, report_id=report_id
    )

    # 3. Finalize Dossier
    await dossier_service.update_dossier(report_id, "final_result", result)

    logger.info(f"Worker completed analysis for report: {report_id}")
    return result


async def run_ai_agent(ctx, society_data: dict, report_id: str):
    """
    Background job to run the AI Agent flow.
    Also updates FeasibilityReport status and output to reflect progress.
    """
    from uuid import UUID

    from sqlalchemy import select

    from services.orchestrator.agent.runner import run_agent
    from services.orchestrator.db import async_session_factory
    from services.orchestrator.models.enums import ReportStatus
    from services.orchestrator.models.report import FeasibilityReport

    logger.info(f"Worker starting AI Agent for report: {report_id}")

    # Initialize Dossier (for audit trail)
    await dossier_service.create_dossier(report_id, society_data)

    # Transition to PROCESSING
    try:
        async with async_session_factory() as db:
            rpt = (
                await db.execute(
                    select(FeasibilityReport).where(FeasibilityReport.id == UUID(report_id))
                )
            ).scalar_one_or_none()
            if rpt:
                rpt.status = ReportStatus.PROCESSING
                await db.commit()
    except Exception as e:
        logger.warning(f"Failed to mark report {report_id} as PROCESSING: {e}")

    # Run agent and persist results
    try:
        result = await run_agent(society_data, report_id)
        # Update Dossier
        await dossier_service.update_dossier(report_id, "agent_result", result)

        async with async_session_factory() as db:
            rpt = (
                await db.execute(
                    select(FeasibilityReport).where(FeasibilityReport.id == UUID(report_id))
                )
            ).scalar_one_or_none()
            if rpt:
                if result.get("status") == "error":
                    rpt.status = ReportStatus.FAILED
                    rpt.error_message = result.get("error") or "Agent returned error"
                else:
                    rpt.status = ReportStatus.COMPLETED
                    rpt.error_message = None
                rpt.report_path = result.get("report_path")
                rpt.output_data = result
                # Some runs attach a tool log
                if hasattr(rpt, "tool_log"):
                    try:
                        rpt.tool_log = result.get("tool_log", [])
                    except Exception:
                        pass
                await db.commit()

        logger.info(f"Worker completed AI Agent for report: {report_id}")
        return result
    except Exception as e:
        logger.exception(f"AI Agent job failed for report {report_id}: {e}")
        # Persist failure state
        try:
            async with async_session_factory() as db:
                rpt = (
                    await db.execute(
                        select(FeasibilityReport).where(FeasibilityReport.id == UUID(report_id))
                    )
                ).scalar_one_or_none()
                if rpt:
                    rpt.status = ReportStatus.FAILED
                    rpt.error_message = str(e)
                    await db.commit()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


# --- Worker Configuration ---


class WorkerSettings:
    functions = [run_feasibility_analysis, run_ai_agent]
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://redis:6379"))
    job_timeout = 1800  # 30 minutes — Playwright browser scrapes can take a while
    on_startup = None
    on_shutdown = None
