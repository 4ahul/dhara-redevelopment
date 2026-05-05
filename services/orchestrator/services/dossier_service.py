import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DossierService:
    """
    Centralized service to manage 'Dossiers' (the single source of truth for an analysis).
    Consolidates data from all microservices into one versioned document.
    """

    def __init__(self):
        self.storage_dir = Path("./dossiers")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def create_dossier(self, report_id: str, input_data: dict) -> dict:
        """Initialize a new dossier from request inputs."""
        dossier = {
            "dossier_id": report_id,
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "initialized",
            "input": input_data,
            "data": {},  # Results from microservices
            "metadata": {
                "trace_id": report_id  # Using report_id as trace_id correlation
            },
        }
        await self._save_to_disk(report_id, dossier)
        return dossier

    async def update_dossier(self, report_id: str, stage: str, result: dict):
        """Update a specific stage of the dossier with service results."""
        dossier = await self.get_dossier(report_id)
        if not dossier:
            # Create a minimal dossier if it doesn't exist yet (worker may have created it)
            dossier = {
                "dossier_id": report_id,
                "version": "1.0",
                "created_at": datetime.utcnow().isoformat(),
                "status": "processing",
                "data": {},
                "metadata": {"trace_id": report_id},
            }

        dossier["data"][stage] = result
        dossier["updated_at"] = datetime.utcnow().isoformat()

        # Auto-advance status based on stage
        if stage == "final_result":
            final = result if isinstance(result, dict) else {}
            job_status = final.get("status", "completed")
            dossier["status"] = "completed" if job_status == "completed" else "failed"
        elif stage in ("start", "round1", "round2") and dossier.get("status") == "initialized":
            dossier["status"] = "processing"

        await self._save_to_disk(report_id, dossier)

    async def get_dossier(self, report_id: str) -> dict | None:
        """Retrieve the dossier from disk."""
        path = self.storage_dir / f"{report_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.exception(f"Failed to read dossier {report_id}: {e}")
            return None

    async def get_dossier_status(self, report_id: str) -> dict | None:
        """Retrieve dossier and calculate progress percentage."""
        dossier = await self.get_dossier(report_id)
        if not dossier:
            return None

        # Calculate progress based on stages
        stages = [
            "round1_pr_card",
            "round1_mcgm",
            "round1_site_analysis",
            "round1_dp_remarks",
            "round1_ocr",
            "round2",
            "final_result",
        ]
        completed = [s for s in stages if s in dossier.get("data", {})]

        progress_pct = round((len(completed) / len(stages)) * 100, 2)
        if "final_result" in completed:
            progress_pct = 100.0
        status = dossier.get("status", "processing")

        return {
            "job_id": report_id,
            "status": status,
            "progress": progress_pct,
            "progress_pct": progress_pct,  # alias for frontend compat
            "current_stage": completed[-1] if completed else "initialized",
            "updated_at": dossier.get("updated_at"),
            "file_url": dossier.get("data", {}).get("final_result", {}).get("report_url"),
        }

    async def _save_to_disk(self, report_id: str, dossier: dict):
        path = self.storage_dir / f"{report_id}.json"
        try:
            path.write_text(json.dumps(dossier, indent=2, default=str))
        except Exception as e:
            logger.exception(f"Failed to save dossier {report_id}: {e}")


dossier_service = DossierService()
