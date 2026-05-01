import logging

from fastapi import APIRouter

from dhara_shared.schemas import InternalServiceResponse

from ..schemas import HeightRequest
from ..services.height_service import height_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Height"])


@router.post("/check-height", response_model=InternalServiceResponse)
async def get_permissible_height(request: HeightRequest):
    """
    Get permissible building height for given coordinates.
    """
    logger.info(f"Height request for lat={request.lat}, lng={request.lng}")
    try:
        result = await height_service.get_height(
            lat=request.lat,
            lng=request.lng,
            site_elevation=request.site_elevation,
        )
        return InternalServiceResponse(status="success", data=result)
    except Exception as e:
        logger.error(f"Error in height service: {e}")
        return InternalServiceResponse(status="error", error=str(e))
