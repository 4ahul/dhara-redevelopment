"""
Dhara AI — Admin Service
Business logic for admin portal, user management, enquiries, and statistics.
Refactored to use CRUD and Repository layers.
"""

import logging
import math
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.models.enums import UserRole
from services.orchestrator.models.role import Role
from services.orchestrator.repositories import admin_repository, enquiry_repository, user_repository
from services.orchestrator.schemas.admin import EnquiryResponse
from services.orchestrator.schemas.common import PaginatedResponse

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_pmc_users(
        self, page: int = 1, page_size: int = 20, search: str = None, is_active: bool = None
    ) -> PaginatedResponse:
        """Fetch PMC users with stats, optimized via the Repository layer."""
        items, total = await admin_repository.list_pmc_users_with_stats(
            self.db, page, page_size, search, is_active
        )
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    async def admin_search(
        self, q: str, entity_type: str = None, page: int = 1, page_size: int = 20
    ) -> PaginatedResponse:
        """
        Search across multiple entities.
        Note: Complex cross-entity search remains here for now, but uses Repository helpers.
        """
        # For now, we'll keep the multi-entity logic here but could move to search_service
        # or a specialized search_repository if it gets more complex.
        # Keeping it for backward compatibility during re-org.

        results, term = [], f"%{q}%"
        if not entity_type or entity_type == "user":
            users, _ = await user_repository.list_users_by_role(
                self.db, UserRole.PMC, 1, page_size, search=q
            )
            for u in users:
                results.append(
                    {
                        "type": "user",
                        "id": str(u.id),
                        "title": u.name,
                        "subtitle": f"{u.email} — {u.role.value}",
                        "status": "active" if u.is_active else "inactive",
                        "created_at": u.created_at.isoformat(),
                    }
                )

        if not entity_type or entity_type == "society":
            # For admin search, we'll need a way to search societies across ALL users
            from sqlalchemy import or_, select

            from services.orchestrator.models import Society

            stmt = (
                select(Society)
                .where(or_(Society.name.ilike(term), Society.address.ilike(term)))
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

        if not entity_type or entity_type == "enquiry":
            enquiries, _ = await enquiry_repository.list_enquiries(self.db, 1, page_size)
            for e in enquiries:
                if q.lower() in e.name.lower() or q.lower() in e.email.lower():
                    results.append(
                        {
                            "type": "enquiry",
                            "id": str(e.id),
                            "title": e.name,
                            "subtitle": e.subject or e.message[:80],
                            "status": e.status.value,
                            "created_at": e.created_at.isoformat(),
                        }
                    )

        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        total = len(results)
        off = (page - 1) * page_size
        return PaginatedResponse(
            items=results[off : off + page_size],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    async def list_enquiries(
        self, page: int = 1, page_size: int = 20, status: str = None, source: str = None
    ) -> PaginatedResponse:
        """List enquiries via the Repository layer."""
        items, total = await enquiry_repository.list_enquiries(
            self.db, page, page_size, status, source
        )
        serialized = [EnquiryResponse.model_validate(e).model_dump() for e in items]
        return PaginatedResponse(
            items=serialized,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_enquiry(self, enquiry_id: UUID) -> EnquiryResponse:
        """Retrieve enquiry details."""
        e = await enquiry_repository.get_enquiry_by_id(self.db, enquiry_id)
        if not e:
            raise HTTPException(404, "Enquiry not found")
        return EnquiryResponse.model_validate(e)

    async def update_enquiry(self, enquiry_id: UUID, req_data: dict) -> EnquiryResponse:
        """Update enquiry status or assignment."""
        e = await enquiry_repository.get_enquiry_by_id(self.db, enquiry_id)
        if not e:
            raise HTTPException(404, "Enquiry not found")

        if req_data.get("assigned_to"):
            assigned_user = await user_repository.get_user_by_id(self.db, req_data["assigned_to"])
            if not assigned_user:
                raise HTTPException(400, "Assigned user not found")

        for k, v in req_data.items():
            setattr(e, k, v)
        await self.db.flush()
        await self.db.refresh(e)
        return EnquiryResponse.model_validate(e)

    async def get_dashboard_stats(self) -> dict:
        """Fetch dashboard statistics via the Repository layer."""
        return await admin_repository.get_dashboard_counts(self.db)

    async def get_roles(self) -> list[Role]:
        """Fetch all user roles."""
        from sqlalchemy import select

        return list((await self.db.execute(select(Role).order_by(Role.name))).scalars().all())
