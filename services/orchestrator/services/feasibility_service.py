import base64
import logging
import math
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.report import FeasibilityReport
from ..repositories import society_repository
from ..schemas.feasibility import (
    FeasibilityForm,
    FeasibilityReportUpdate,
)
from .feasibility_orchestrator import feasibility_orchestrator
from .redis import get_arq_or_init

logger = logging.getLogger(__name__)


class FeasibilityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_reports(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        society_id: UUID | None = None,
    ) -> dict:
        """Fetch paginated feasibility reports snapshots."""
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

    async def get_report(self, user_id: UUID, report_id: UUID) -> FeasibilityReport | None:
        """Fetch a specific technical report snapshot."""
        return await society_repository.get_feasibility_report(self.db, report_id, user_id)

    async def submit_feasibility_analysis(self, user_id: UUID, form: FeasibilityForm) -> dict:
        """Initiate feasibility analysis."""
        soc = await society_repository.get_society_by_id(self.db, form.society_id, user_id)
        if not soc:
            raise ValueError("Society not found or unauthorized")

        req_data = form.to_orchestrator_payload(soc)

        if form.old_plan:
            bytes_data = await form.old_plan.read()
            req_data["ocr_pdf_b64"] = base64.b64encode(bytes_data).decode()

        if form.dp_remark_pdf:
            bytes_data = await form.dp_remark_pdf.read()
            req_data["dp_remark_pdf_b64"] = base64.b64encode(bytes_data).decode()

        if form.tenements_sheet:
            bytes_data = await form.tenements_sheet.read()
            req_data["tenements_sheet_b64"] = base64.b64encode(bytes_data).decode()
            req_data["tenements_sheet_filename"] = form.tenements_sheet.filename

        job_id = str(uuid4())

        arq = await get_arq_or_init()
        if arq:
            await arq.enqueue_job("run_feasibility_analysis", req_data, str(user_id), job_id)
            return {"job_id": job_id, "status": "processing"}
        logger.warning("Arq unavailable, falling back to sync analysis for job %s", job_id)
        return await feasibility_orchestrator.analyze(
            req_data, background_tasks=None, user_id=str(user_id), report_id=job_id
        )

    async def update_report(
        self, user_id: UUID, report_id: UUID, req: FeasibilityReportUpdate
    ) -> FeasibilityReport | None:
        """Update report metadata snapshots."""
        report = await self.get_report(user_id, report_id)
        if not report:
            return None

        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(report, k, v)

        await self.db.commit()
        await self.db.refresh(report)
        return report
