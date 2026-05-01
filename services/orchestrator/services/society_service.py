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


def _get_genai_client(api_key: str):
    """Import google.genai, working around the google namespace package conflict."""
    import sys

    # google-generativeai and google-genai both claim the 'google' namespace.
    # If the venv has google-generativeai but not google-genai we fall back to
    # searching the system (global) site-packages where google-genai is installed.
    try:
        from google import genai as _genai
        from google.genai import types as _types

        return _genai.Client(api_key=api_key), _types
    except ImportError:
        pass

    # Fall back: inject global site-packages
    import sysconfig

    user_sp = sysconfig.get_path("purelib")
    for sp in [user_sp, "C:/Users/Admin/AppData/Local/Programs/Python/Python314/Lib/site-packages"]:
        if sp and sp not in sys.path:
            sys.path.insert(0, sp)
    try:
        import importlib

        _genai_mod = importlib.import_module("google.genai")
        _types_mod = importlib.import_module("google.genai.types")
        return _genai_mod.Client(api_key=api_key), _types_mod
    except Exception as e:
        raise ImportError(f"google-genai not available: {e}") from e


async def resolve_address_with_ai(address: str) -> dict:
    """Use Google Gemini AI to extract ward, village, taluka, district from address."""
    try:
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not configured, skipping address resolution")
            return {}

        client, gtypes = _get_genai_client(api_key)

        prompt = f"""Extract location details from this Mumbai address. Return ONLY a JSON object with these fields:
- ward (BMC ward code e.g. "K/W", "G/S", "H/E", "E")
- village (neighbourhood e.g. "Vile Parle", "Dharavi", "Kurla")
- taluka (e.g. "Andheri", "Kurla", "Borivali")
- district (e.g. "Mumbai", "Mumbai Suburban")

Address: {address}

Return ONLY valid JSON, no markdown, no explanation."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=gtypes.GenerateContentConfig(temperature=0.0, max_output_tokens=512),
        )
        text = (response.text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            logger.info(
                f"AI resolved address: ward={data.get('ward')}, village={data.get('village')}"
            )
            return {
                "ward": data.get("ward"),
                "village": data.get("village"),
                "taluka": data.get("taluka"),
                "district": data.get("district"),
            }
    except Exception as e:
        logger.warning(f"Address AI resolution failed: {e}")
    return {}


async def resolve_tps_scheme(address: str, fp_no: str = None) -> str | None:
    """Use Google Gemini AI to find TPS scheme name for a property."""
    try:
        api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None

        client, gtypes = _get_genai_client(api_key)

        prompt = f"""Find the TPS (Town Planning Scheme) name for this Mumbai property.
Return ONLY a JSON object with:
- tps_name (e.g. "TPS IV", "TPS No. 2", or null if unknown)

Address: {address}
FP Number: {fp_no or "unknown"}

Return ONLY valid JSON, no markdown, no explanation."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=gtypes.GenerateContentConfig(temperature=0.0, max_output_tokens=256),
        )
        text = (response.text or "").strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)

        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            tps = data.get("tps_name")
            if tps and str(tps).lower() not in ("null", "none", ""):
                logger.info(f"AI found TPS: {tps}")
                return tps
    except Exception as e:
        logger.warning(f"TPS AI resolution failed: {e}")
    return None


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
        search: str = None,
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
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    async def create_society(self, user_id: UUID, req: SocietyCreate) -> Society:
        """Register a new society.

        On creation:
        1. Resolve ward/village/taluka/district from address using AI.
        2. Map OCR-extracted document fields into the proper DB columns.
        3. Save the society.
        """
        data = req.model_dump(exclude_unset=True, by_alias=False)

        # ── Map frontend camelCase fields to DB columns ───────────────────────
        # point_of_contact list → flat columns for first contact; full list stored in ocr_data
        poc_list = data.pop("point_of_contact", [])
        if poc_list:
            first = poc_list[0] if isinstance(poc_list[0], dict) else {}
            data.setdefault("poc_name", first.get("contact_person"))
            data.setdefault("poc_email", first.get("contact_mail"))
            data.setdefault("poc_phone", first.get("contact_phone"))
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

        # status defaults to "New" from schema; keep whatever came in
        # registration_number already mapped correctly by field name

        address = data.get("address")
        logger.info(f"Creating society: {data.get('name')} | address: {address}")

        # ── Step 1: Location resolution ──────────────────────────────────────
        needs_location = bool(address and not (data.get("ward") or data.get("village")))
        logger.info(f"Needs location resolution? {needs_location}")

        if needs_location:
            from .address_resolver import resolve_address_from_input
            location_data = await resolve_address_from_input(address)
            logger.info(f"Resolved location data for '{address}': {location_data}")
            if location_data:
                data.setdefault("ward", location_data.get("ward"))
                data.setdefault("village", location_data.get("village"))
                data.setdefault("taluka", location_data.get("taluka"))
                data.setdefault("district", location_data.get("district"))
                logger.info(f"Set ward to: {data.get('ward')}")

        # ── Step 2: Skip OCR (Moved to feasibility report phase) ─────────────────

        # ── Step 3: Map FE-specific fields to DB columns ────────────────────
        # initial_status → status
        if "initial_status" in data:
            data["status"] = data.pop("initial_status")

        # point_of_contact array → flat poc fields (use first contact)
        poc_list = data.pop("point_of_contact", None)
        if poc_list and isinstance(poc_list, list) and len(poc_list) > 0:
            first = poc_list[0]
            data.setdefault("poc_name",  first.get("contactPerson"))
            data.setdefault("poc_email", first.get("contactMail"))
            data.setdefault("poc_phone", first.get("contactPhone"))

        data["cts_validated"] = None

        soc = await society_repository.create_society(self.db, user_id, data)
        logger.info("Society created: %s (ward=%s)", soc.name, soc.ward)

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
