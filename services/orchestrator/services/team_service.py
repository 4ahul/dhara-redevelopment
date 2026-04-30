"""
Dhara AI — Team Service
Business logic for team member management, invitations, and permissions.
Refactored to use CRUD layer.
"""

import logging
import math
import uuid as uuid_mod
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.enums import InviteStatus
from ..repositories import team_repository, user_repository
from ..schemas.common import PaginatedResponse
from ..schemas.team import (
    InviteRequest,
    InviteResponse,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from .email import send_team_invite

logger = logging.getLogger(__name__)


class TeamService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_members(self, organization: str, page: int = 1, page_size: int = 20, status: str = None) -> dict:
        """List team members within an organization with pagination.

        Returns raw dict with ORM items so the router can serialize with camelCase aliases.
        """
        if not organization:
            return {"items": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}

        items, total = await team_repository.list_team_members(self.db, organization, page, page_size, status)
        total_pages = math.ceil(total / page_size) if total else 0

        return {"items": items, "total": total, "page": page, "page_size": page_size, "total_pages": total_pages}

    async def invite_member(
        self,
        req: InviteRequest,
        inviter_name: str,
        inviter_email: str,
        organization: str,
        inviter_id: UUID,
        bg_tasks,
    ) -> InviteResponse:
        """Invite a new member to the organization."""
        if not organization:
            raise HTTPException(400, "Set your organization first")

        # Check if already a member or invited via CRUD
        existing = await team_repository.get_member_by_email_and_org(
            self.db, req.email, organization
        )

        if existing and existing.status in [InviteStatus.PENDING, InviteStatus.ACCEPTED]:
            raise HTTPException(
                409,
                f"Already {'a member' if existing.status == InviteStatus.ACCEPTED else 'invited'}",
            )

        # Check if user already exists in system to link user_id via CRUD
        existing_user = await user_repository.get_user_by_email(self.db, req.email)

        token = str(uuid_mod.uuid4())
        member_data = {
            "user_id": existing_user.id if existing_user else None,
            "organization": organization,
            "role": req.role,
            "email": req.email,
            "name": req.name or (existing_user.name if existing_user else None),
            "invited_by": inviter_id,
            "invite_token": token,
            "status": InviteStatus.PENDING,
        }

        member = await team_repository.create_team_member(self.db, member_data)

        # Trigger invitation email in background
        invite_url = f"{settings.ALLOWED_ORIGINS.split(',')[0]}/invite/{token}"
        bg_tasks.add_task(send_team_invite, req.email, inviter_name, req.role, invite_url, req.name)

        logger.info("Invite sent: %s → %s", inviter_email, req.email)
        return InviteResponse(
            message=f"Invitation sent to {req.email}", invite_id=member.id, email=req.email
        )

    async def update_member(self, member_id: UUID, organization: str, req: TeamMemberUpdate):
        """Update member details (roles, name, enabled) within an organization."""
        if not organization:
            raise HTTPException(400, "Organization not set")

        member = await team_repository.get_team_member_by_id(self.db, member_id, organization)

        if not member:
            raise HTTPException(404, "Team member not found")

        update_data = req.model_dump(exclude_unset=True)

        # FE sends 'roles' as array — DB stores single 'role' string (use first)
        if 'roles' in update_data:
            roles_list = update_data.pop('roles')
            if roles_list and len(roles_list) > 0:
                member.role = roles_list[0]

        # FE sends 'enabled' — DB stores 'is_enabled'
        if 'enabled' in update_data:
            member.is_enabled = update_data.pop('enabled')

        # Apply remaining fields directly
        for k, v in update_data.items():
            setattr(member, k, v)

        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def remove_member(self, member_id: UUID, organization: str) -> dict:
        """Remove a member from the organization."""
        if not organization:
            raise HTTPException(400, "Organization not set")

        member = await team_repository.get_team_member_by_id(self.db, member_id, organization)

        if not member:
            raise HTTPException(404, "Team member not found")

        await self.db.delete(member)
        await self.db.flush()
        return {"status": "success", "message": f"{member.email} removed"}
