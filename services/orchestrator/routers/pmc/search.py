import logging

from fastapi import APIRouter, Depends, Query

from ...core.dependencies import get_current_user, get_search_service
from ...schemas.admin import RoleResponse
from ...schemas.common import PaginatedResponse
from ...services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search & Roles"])


@router.get("/search/places/autocomplete")
async def autocomplete_places(
    q: str = Query(..., min_length=3),
    service: SearchService = Depends(get_search_service),
    user=Depends(get_current_user),
):
    """Google Maps Places Autocomplete for Mumbai."""
    return await service.autocomplete_places(q)


@router.get("/search/places/{place_id}")
async def get_place_details(
    place_id: str,
    service: SearchService = Depends(get_search_service),
    user=Depends(get_current_user),
):
    """Get full details (lat, lng, address) for a selected place_id."""
    return await service.get_place_details(place_id)


@router.get("/search", response_model=PaginatedResponse)
async def global_search(
    q: str = Query(min_length=1, max_length=500),
    entity_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    """Global search across societies, reports, and tenders."""
    return await service.global_search(q, user.id, entity_type, page, page_size)


@router.get("/roles", response_model=list[RoleResponse])
async def get_roles(service: SearchService = Depends(get_search_service)):
    """List available user roles."""
    return await service.get_active_roles()
