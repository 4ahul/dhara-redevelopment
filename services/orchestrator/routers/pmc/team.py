import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ...core.dependencies import get_current_user, get_team_service
from ...schemas.common import PaginatedResponse
from ...schemas.team import (
    InviteRequest,
    InviteResponse,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from ...services.team_service import TeamService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team", tags=["Team Management"])


def _member_to_response(member) -> dict:
    """Helper to ensure camelCase output."""
    return TeamMemberResponse.model_validate(member).model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_team(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    status: str = Query(None),
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    """List team members in your organization."""
    result = await service.list_members(user.organization, page, page_size, status)
    if "items" in result:
        result["items"] = [_member_to_response(m) for m in result["items"]]
    return result


@router.post("/invite", response_model=InviteResponse, status_code=201)
async def invite_member(
    req: InviteRequest,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    """Invite a new professional to join your team."""
    return await service.invite_member(req, user.name, user.email, user.organization, user.id, bg)


@router.patch("/{member_id}", response_model=TeamMemberResponse)
async def patch_member(
    member_id: UUID,
    req: TeamMemberUpdate,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    """Update roles or permissions of a team member."""
    result = await service.update_member(member_id, user.organization, req)
    return TeamMemberResponse.model_validate(result)


@router.delete("/{member_id}")
async def remove_member(
    member_id: UUID,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    """Remove a member from the organization."""
    return await service.remove_member(member_id, user.organization)
