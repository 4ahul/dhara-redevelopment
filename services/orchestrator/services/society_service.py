"""
Dhara AI — Society Service
Business logic for managing societies, reports, and tenders.
Refactored to use CRUD layer.
"""

import json
import logging
import math
import os
import re
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from models.society import Society
from models.report import SocietyReport
from models.team import SocietyTender
from schemas.society import SocietyCreate, SocietyUpdate, ReportCreate, TenderCreate
from repositories import society_repository

logger = logging.getLogger(__name__)


async def resolve_address_with_ai(address: str) -> dict:
    """Use Google Gemini AI to extract ward, village, taluka, district from address."""
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not set, skipping address resolution")
            return {}
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.1-pro-preview")
        
        prompt = f"""Extract location details from this Mumbai address. Return ONLY a JSON object with these fields:
- ward (e.g., "G/S", "E/S", "K/W")
- village (e.g., "Dharavi", "Kurla", "Andheri")
- taluka (e.g., "Kurla", "Andheri", "Borivali")
- district (e.g., "Mumbai", "Mumbai Suburban")

Address: {address}

Return ONLY valid JSON, no other text."""

        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            logger.info(f"AI resolved address: ward={data.get('ward')}, village={data.get('village')}")
            return {
                "ward": data.get("ward"),
                "village": data.get("village"),
                "taluka": data.get("taluka"),
                "district": data.get("district"),
            }
    except Exception as e:
        logger.warning(f"Address AI resolution failed: {e}")
    return {}

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
        
        # Auto-resolve ward/village/taluka from address if not provided
        address = data.get("address")
        if address and not (data.get("ward") or data.get("village")):
            location_data = await resolve_address_with_ai(address)
            if location_data:
                data.setdefault("ward", location_data.get("ward"))
                data.setdefault("village", location_data.get("village"))
                data.setdefault("taluka", location_data.get("taluka"))
                data.setdefault("district", location_data.get("district"))
        
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
        
        update_data = req.model_dump(exclude_unset=True)
        
        # Auto-resolve ward/village/taluka from new address if address is being updated
        new_address = update_data.get("address")
        if new_address and not (update_data.get("ward") or update_data.get("village")):
            location_data = await resolve_address_with_ai(new_address)
            if location_data:
                update_data.setdefault("ward", location_data.get("ward"))
                update_data.setdefault("village", location_data.get("village"))
                update_data.setdefault("taluka", location_data.get("taluka"))
                update_data.setdefault("district", location_data.get("district"))
        
        for k, v in update_data.items():
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
