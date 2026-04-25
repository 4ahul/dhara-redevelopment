import logging
import json
from pathlib import Path
from uuid import UUID
from datetime import datetime
from typing import Any, Dict, Optional

from services.orchestrator.db import async_session_factory
from services.orchestrator.models import FeasibilityReport

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
            "data": {}, # Results from microservices
            "metadata": {
                "trace_id": report_id # Using report_id as trace_id correlation
            }
        }
        await self._save_to_disk(report_id, dossier)
        return dossier

    async def update_dossier(self, report_id: str, stage: str, result: dict):
        """Update a specific stage of the dossier with service results."""
        dossier = await self.get_dossier(report_id)
        if not dossier:
            logger.error(f"Cannot update missing dossier: {report_id}")
            return

        dossier["data"][stage] = result
        dossier["updated_at"] = datetime.utcnow().isoformat()
        
        await self._save_to_disk(report_id, dossier)

    async def get_dossier(self, report_id: str) -> Optional[dict]:
        """Retrieve the dossier from disk."""
        path = self.storage_dir / f"{report_id}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except Exception as e:
            logger.error(f"Failed to read dossier {report_id}: {e}")
            return None

    async def _save_to_disk(self, report_id: str, dossier: dict):
        path = self.storage_dir / f"{report_id}.json"
        try:
            path.write_text(json.dumps(dossier, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to save dossier {report_id}: {e}")

dossier_service = DossierService()
