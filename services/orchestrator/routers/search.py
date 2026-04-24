"""Search & Roles Routes — GET /api/search, GET /api/roles"""

import logging

from services.orchestrator.core.dependencies import get_current_user, get_search_service
from fastapi import APIRouter, Depends, Query
from services.orchestrator.schemas.admin import RoleResponse
from services.orchestrator.schemas.common import PaginatedResponse

from services.orchestrator.services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search & Roles"])


@router.get("/search", response_model=PaginatedResponse)
async def global_search(
    q: str = Query(min_length=1, max_length=500),
    entity_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SearchService = Depends(get_search_service)
):
    return await service.global_search(q, user.id, entity_type, page, page_size)


@router.get("/roles", response_model=list[RoleResponse])
async def get_roles(service: SearchService = Depends(get_search_service)):
    return await service.get_active_roles()




