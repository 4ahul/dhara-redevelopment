import asyncio
import logging
from arq import create_pool
from arq.connections import RedisSettings

from services.orchestrator.core.config import settings
from services.orchestrator.logic.feasibility_orchestrator import feasibility_orchestrator
from services.orchestrator.logic.dossier_service import dossier_service

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
        req=req,
        background_tasks=None,
        user_id=user_id,
        report_id=report_id
    )
    
    # 3. Finalize Dossier
    await dossier_service.update_dossier(report_id, "final_result", result)
    
    logger.info(f"Worker completed analysis for report: {report_id}")
    return result

async def run_ai_agent(ctx, society_data: dict, report_id: str):
    """
    Background job to run the AI Agent flow.
    """
    from services.orchestrator.agent.runner import run_agent
    logger.info(f"Worker starting AI Agent for report: {report_id}")
    
    # Initialize Dossier
    await dossier_service.create_dossier(report_id, society_data)
    
    result = await run_agent(society_data, report_id)
    
    # Update Dossier
    await dossier_service.update_dossier(report_id, "agent_result", result)
    
    logger.info(f"Worker completed AI Agent for report: {report_id}")
    return result

# --- Worker Configuration ---

class WorkerSettings:
    functions = [run_feasibility_analysis, run_ai_agent]
    redis_settings = RedisSettings.from_dsn(os.getenv("REDIS_URL", "redis://redis:6379"))
    on_startup = None
    on_shutdown = None

# For running via CLI: arq services.orchestrator.logic.worker.WorkerSettings
import os
