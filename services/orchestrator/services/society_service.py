"""
Dhara AI — Society Service
Business logic for managing societies, reports, and tenders.
Refactored to use CRUD layer.
"""

import logging
import math
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from models.society import Society
from models.report import SocietyReport
from models.team import SocietyTender
from schemas.society import SocietyCreate, SocietyUpdate, ReportCreate, TenderCreate
from repositories import society_repository

logger = logging.getLogger(__name__)

class SocietyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_societies(
        self, 
        user_id: UUID, 
        page: int = 1, 
        page_size: int = 20, 
        status: str = None, 
        ward: str = None, 
        search: str = None
    ) -> dict:
        """Fetch paginated societies for a user."""
        items, total = await society_repository.list_societies(
            self.db, user_id, page, page_size, status, ward, search
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0
        }

    async def create_society(self, user_id: UUID, req: SocietyCreate) -> Society:
        """Register a new society."""
        data = req.model_dump(exclude_unset=True)
        soc = await society_repository.create_society(self.db, user_id, data)
        logger.info("Society created: %s", soc.name)
        return soc

    async def get_society(self, user_id: UUID, society_id: UUID) -> Society | None:
        """Retrieve a specific society for the user."""
        return await society_repository.get_society_by_id(self.db, society_id, user_id)

    async def update_society(self, user_id: UUID, society_id: UUID, req: SocietyUpdate) -> Society | None:
        """Update society details."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None
        
        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(soc, k, v)
        
        await self.db.flush()
        await self.db.refresh(soc)
        return soc

    async def list_reports(self, user_id: UUID, society_id: UUID, page: int = 1, page_size: int = 20) -> dict | None:
        """List reports for a specific society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None
            
        items, total = await society_repository.list_society_reports(self.db, society_id, page, page_size)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0
        }

    async def create_report(self, user_id: UUID, society_id: UUID, req: ReportCreate) -> SocietyReport | None:
        """Add a report to a society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None
            
        data = {
            "society_id": society_id,
            "title": req.title,
            "report_type": req.report_type
        }
        return await society_repository.create_society_report(self.db, data)

    async def list_tenders(self, user_id: UUID, society_id: UUID, page: int = 1, page_size: int = 20) -> dict | None:
        """List tenders for a specific society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None
            
        items, total = await society_repository.list_society_tenders(self.db, society_id, page, page_size)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0
        }

    async def create_tender(self, user_id: UUID, society_id: UUID, req: TenderCreate) -> SocietyTender | None:
        """Open a new tender for a society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None
            
        data = req.model_dump(exclude_unset=True)
        data["society_id"] = society_id
        return await society_repository.create_society_tender(self.db, data)
