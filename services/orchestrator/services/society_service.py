"""
Dhara AI — Society Service
Business logic for managing societies, reports, and tenders.
Refactored to use CRUD layer.
"""

import logging
import math
import os
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.core.config import settings
from services.orchestrator.models.report import SocietyReport
from services.orchestrator.models.society import Society
from services.orchestrator.models.team import SocietyTender
from services.orchestrator.repositories import society_repository
from services.orchestrator.schemas.society import (
    ReportCreate,
    SocietyCreate,
    SocietyUpdate,
    TenderCreate,
)

logger = logging.getLogger(__name__)


async def resolve_address_with_ai(address: str) -> dict:
    """Use Google Gemini AI to extract ward, village, taluka, district from address."""
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not configured, skipping address resolution")
        return {}

    # TODO: Implement actual Gemini AI address resolution
    logger.warning("resolve_address_with_ai not fully implemented, returning empty result")
    return {}


async def resolve_tps_scheme(address: str, fp_no: str | None = None) -> str | None:
    """Use Google Gemini AI to find TPS scheme name for a property."""
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    # TODO: Implement actual Gemini AI TPS scheme resolution
    logger.warning("resolve_tps_scheme not fully implemented, returning None")
    return None


class SocietyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_societies(
        self,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        search: str | None = None,
    ) -> dict:
        """Fetch paginated societies for a user."""
        items, total = await society_repository.list_societies(
            self.db, user_id, page, page_size, status, search
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    async def create_society(self, user_id: UUID, req: SocietyCreate) -> Society:
        """Register a new society."""

        data = req.model_dump(exclude_unset=True, by_alias=False)

        if "initial_status" in data:
            data["status"] = data.pop("initial_status")

        poc_list = data.pop("point_of_contact", [])
        if poc_list and isinstance(poc_list, list) and len(poc_list) > 0:
            first = poc_list[0]
            # Support both camelCase (from FE docs) and snake_case (internal)
            data["poc_name"] = first.get("contactPerson") or first.get("contact_person")
            data["poc_email"] = first.get("contactMail") or first.get("contact_mail")
            data["poc_phone"] = first.get("contactPhone") or first.get("contact_phone")

            # Persist full contacts array in ocr_data so additional contacts aren't lost
            if len(poc_list) > 1:
                ocr_blob = data.get("ocr_data") or {}
                ocr_blob["contacts"] = poc_list
                data["ocr_data"] = ocr_blob

        # onboarded_date_ts (int, ms or s) → onboarded_date (datetime)
        ts = data.pop("onboarded_date_ts", None)
        if ts and not data.get("onboarded_date"):
            from datetime import datetime as _dt

            if ts > 1_000_000_000_000:  # milliseconds
                ts = ts / 1000
            data["onboarded_date"] = _dt.utcfromtimestamp(ts)

        address = data.get("address")
        logger.info(f"Creating society: {data.get('name')} | address: {address}")

        soc = await society_repository.create_society(self.db, user_id, data)
        logger.info("Society created: %s", soc.name)

        return soc

    async def get_society(self, user_id: UUID, society_id: UUID) -> Society | None:
        """Retrieve a specific society for the user."""
        return await society_repository.get_society_by_id(self.db, society_id, user_id)

    async def update_society(
        self, user_id: UUID, society_id: UUID, req: SocietyUpdate
    ) -> Society | None:
        """Update society details."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None

        update_data = req.model_dump(exclude_unset=True)

        for k, v in update_data.items():
            setattr(soc, k, v)

        await self.db.flush()
        await self.db.refresh(soc)
        return soc

    async def list_reports(
        self, user_id: UUID, society_id: UUID, page: int = 1, page_size: int = 20
    ) -> dict | None:
        """List reports for a specific society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None

        items, total = await society_repository.list_society_reports(
            self.db, society_id, page, page_size
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    async def create_report(
        self, user_id: UUID, society_id: UUID, req: ReportCreate
    ) -> SocietyReport | None:
        """Add a report to a society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None

        data = {"society_id": society_id, "title": req.title, "report_type": req.report_type}
        return await society_repository.create_society_report(self.db, data)

    async def list_tenders(
        self, user_id: UUID, society_id: UUID, page: int = 1, page_size: int = 20
    ) -> dict | None:
        """List tenders for a specific society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None

        items, total = await society_repository.list_society_tenders(
            self.db, society_id, page, page_size
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    async def create_tender(
        self, user_id: UUID, society_id: UUID, req: TenderCreate
    ) -> SocietyTender | None:
        """Open a new tender for a society."""
        soc = await self.get_society(user_id, society_id)
        if not soc:
            return None

        data = req.model_dump(exclude_unset=True)
        data["society_id"] = society_id
        return await society_repository.create_society_tender(self.db, data)
