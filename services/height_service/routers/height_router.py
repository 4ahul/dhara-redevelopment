from fastapi import APIRouter, HTTPException
from schemas import HeightRequest, HeightResponse
from services.height_service import height_service
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Height"])


@router.post("/check-height", response_model=HeightResponse)
async def get_permissible_height(request: HeightRequest):
    """
    Get permissible building height for given coordinates.

    Flow:
    1. Fetch elevation (Google + Open-Meteo in parallel)
    2. Fetch max height from NOCAS
    3. Return result or clear error if all fail
    """
    logger.info(f"Height request for lat={request.lat}, lng={request.lng}")
    try:
        result = await height_service.get_height(
            lat=request.lat,
            lng=request.lng,
            site_elevation=request.site_elevation,
        )
        return HeightResponse(**result)
    except Exception as e:
        logger.error(f"Error in height service: {e}")
        raise HTTPException(status_code=500, detail=str(e))
