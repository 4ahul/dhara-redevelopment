"""
Dhara AI — Search Service
Business logic for global searching across societies, reports, and tenders.
Also handles role retrieval and initialization.
"""

import logging
import math
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import settings
from orchestrator.models import FeasibilityReport, Role, Society, SocietyTender
from orchestrator.schemas.admin import RoleResponse
from orchestrator.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def autocomplete_places(self, query: str) -> dict:
        """Google Maps Places Autocomplete proxy."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{settings.SITE_ANALYSIS_URL}/places/autocomplete", params={"q": query}
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
        except Exception as e:
            logger.exception(f"Failed to proxy autocomplete request: {e}")
            raise HTTPException(status_code=500, detail="Search service unavailable") from e

    async def get_place_details(self, place_id: str) -> dict:
        """Get full details for a selected place_id proxy."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{settings.SITE_ANALYSIS_URL}/places/{place_id}")
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
        except Exception as e:
            logger.exception(f"Failed to proxy place details request: {e}")
            raise HTTPException(status_code=500, detail="Search service unavailable") from e

    async def global_search(
        self,
        query: str,
        user_id: UUID,
        entity_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedResponse:
        """Perform a cross-entity search for a specific user."""
        results, term = [], f"%{query}%"

        # 1. Society Search
        if not entity_type or entity_type == "society":
            stmt = (
                select(Society)
                .where(
                    Society.created_by == user_id,
                    or_(
                        Society.name.ilike(term),
                        Society.address.ilike(term),
                    ),
                )
                .limit(page_size)
            )
            for s in (await self.db.execute(stmt)).scalars().all():
                results.append(
                    {
                        "type": "society",
                        "id": str(s.id),
                        "title": s.name,
                        "subtitle": s.address,
                        "status": s.status,
                        "created_at": s.created_at.isoformat(),
                    }
                )

        # 2. Report Search
        if not entity_type or entity_type == "report":
            stmt = (
                select(FeasibilityReport)
                .where(FeasibilityReport.user_id == user_id, FeasibilityReport.title.ilike(term))
                .limit(page_size)
            )
            for r in (await self.db.execute(stmt)).scalars().all():
                results.append(
                    {
                        "type": "report",
                        "id": str(r.id),
                        "title": r.title,
                        "subtitle": f"Status: {r.status.value}",
                        "status": r.status.value,
                        "created_at": r.created_at.isoformat(),
                    }
                )

        # 3. Tender Search
        if not entity_type or entity_type == "tender":
            # Only search tenders belonging to societies created by this user
            soc_stmt = select(Society.id).where(Society.created_by == user_id)
            soc_ids = [row[0] for row in (await self.db.execute(soc_stmt)).all()]

            if soc_ids:
                stmt = (
                    select(SocietyTender)
                    .where(
                        SocietyTender.society_id.in_(soc_ids),
                        or_(SocietyTender.title.ilike(term), SocietyTender.description.ilike(term)),
                    )
                    .limit(page_size)
                )
                for t in (await self.db.execute(stmt)).scalars().all():
                    results.append(
                        {
                            "type": "tender",
                            "id": str(t.id),
                            "title": t.title,
                            "subtitle": (t.description or "")[:100],
                            "status": t.status.value,
                            "created_at": t.created_at.isoformat(),
                        }
                    )

        # Sorting and Pagination
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        total = len(results)
        offset = (page - 1) * page_size
        items = results[offset : offset + page_size]
        total_pages = math.ceil(total / page_size) if total else 0

        return PaginatedResponse(
            items=items, total=total, page=page, page_size=page_size, total_pages=total_pages
        )

    async def get_active_roles(self) -> list[RoleResponse]:
        """Fetch all active user roles, seeding defaults if none exist."""
        stmt = select(Role).where(Role.is_active).order_by(Role.name)
        rows = (await self.db.execute(stmt)).scalars().all()

        if not rows:
            logger.info("No roles found in DB. Seeding defaults...")
            from orchestrator.db.seed import seed_defaults

            await seed_defaults()
            # Re-fetch after seeding
            rows = (await self.db.execute(stmt)).scalars().all()

        return [RoleResponse.model_validate(r) for r in rows]
