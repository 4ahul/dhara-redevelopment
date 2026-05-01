"""Team Routes -- GET /api/team, POST /api/team/invite, PATCH/DELETE /api/team/{id}

FE-aligned: camelCase responses, roles as array, status mapping.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query

from ..core.dependencies import get_current_user, get_team_service
from ..schemas.common import PaginatedResponse
from ..schemas.team import (
    InviteRequest,
    InviteResponse,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from ..services.team_service import TeamService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/team", tags=["Team Management"])


def _member_to_response(member) -> dict:
    """Build camelCase response from ORM TeamMember."""
    return TeamMemberResponse.model_validate(member).model_dump(by_alias=True)


@router.get("", response_model=PaginatedResponse)
async def list_team(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias='pageSize'),
    status: str = Query(None),
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    result = await service.list_members(user.organization, page, page_size, status)
    # Re-serialize items through our response model for camelCase + roles array
    if isinstance(result, dict) and "items" in result:
        result["items"] = [_member_to_response(m) for m in result["items"]]
    return result


@router.post("/invite", status_code=201)
async def invite_member(
    req: InviteRequest,
    bg: BackgroundTasks,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    resp = await service.invite_member(req, user.name, user.email, user.organization, user.id, bg)
    if hasattr(resp, 'model_dump'):
        return resp.model_dump(by_alias=True)
    return resp


@router.patch("/{member_id}")
async def patch_member(
    member_id: UUID,
    req: TeamMemberUpdate,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    result = await service.update_member(member_id, user.organization, req)
    if hasattr(result, '__dict__') and hasattr(result, 'id'):
        return _member_to_response(result)
    return result


@router.delete("/{member_id}")
async def remove_member(
    member_id: UUID,
    user=Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
):
    return await service.remove_member(member_id, user.organization)
