"""Team Routes — GET /api/team, POST /api/team/invite, PATCH/DELETE /api/team/{id}"""

import logging
from uuid import UUID

from core.dependencies import get_current_user, get_team_service
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from schemas.common import PaginatedResponse
from schemas.team import InviteRequest, InviteResponse, TeamMemberResponse, TeamMemberUpdate

from services.team_service import TeamService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team", tags=["Team Management"])


@router.get("", response_model=PaginatedResponse)
async def list_team(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service)
):
    return await service.list_members(user.organization, page, page_size, status)


@router.post("/invite", response_model=InviteResponse, status_code=201)
async def invite_member(
    req: InviteRequest,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service)
):
    return await service.invite_member(req, user.name, user.email, user.organization, user.id, bg)


@router.patch("/{member_id}", response_model=TeamMemberResponse)
async def patch_member(
    member_id: UUID,
    req: TeamMemberUpdate,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service)
):
    return await service.update_member(member_id, user.organization, req)


@router.delete("/{member_id}")
async def remove_member(
    member_id: UUID,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service)
):
    return await service.remove_member(member_id, user.organization)



