"""Search & Roles Routes — GET /api/search, GET /api/roles"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.config import settings
from ..core.dependencies import get_current_user, get_search_service
from ..schemas.admin import RoleResponse
from ..schemas.common import PaginatedResponse
from ..services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Search & Roles"])


@router.get("/search/places/autocomplete")
async def autocomplete_places(
    q: str = Query(..., min_length=3),
    user=Depends(get_current_user)
):
    """Google Maps Places Autocomplete for Mumbai (Proxy to Site Analysis Service)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.SITE_ANALYSIS_URL}/places/autocomplete",
                params={"q": q}
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except Exception as e:
        logger.error(f"Failed to proxy autocomplete request: {e}")
        raise HTTPException(status_code=500, detail="Search service unavailable") from e


@router.get("/search/places/{place_id}")
async def get_place_details(
    place_id: str,
    user=Depends(get_current_user)
):
    """Get full details (lat, lng, address) for a selected place_id."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.SITE_ANALYSIS_URL}/places/{place_id}"
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text) from e
    except Exception as e:
        logger.error(f"Failed to proxy place details request: {e}")
        raise HTTPException(status_code=500, detail="Search service unavailable") from e


@router.get("/search", response_model=PaginatedResponse)
async def global_search(
    q: str = Query(min_length=1, max_length=500),
    entity_type: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
):
    return await service.global_search(q, user.id, entity_type, page, page_size)


@router.get("/roles", response_model=list[RoleResponse])
async def get_roles(service: SearchService = Depends(get_search_service)):
    return await service.get_active_roles()
