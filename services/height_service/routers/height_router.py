from fastapi import APIRouter, HTTPException
from schemas import HeightRequest, HeightResponse
from services.height_service import height_service, NOCASUnavailableError
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Height"])


@router.post("/check-height", response_model=HeightResponse)
async def get_permissible_height(request: HeightRequest):
    """
    Get permissible building height from NOCAS for given coordinates.
    Returns 503 if NOCAS is unavailable after retries.
    """
    logger.info(f"Height request for lat={request.lat}, lng={request.lng}")
    try:
        result = await height_service.get_height(
            lat=request.lat,
            lng=request.lng,
            site_elevation=request.site_elevation or 0.0,
        )
        return HeightResponse(**result)
    except NOCASUnavailableError as e:
        logger.error(f"NOCAS unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": "nocas_unavailable",
                "message": str(e),
                "suggestion": "Retry later or provide height data manually",
            },
        )
    except Exception as e:
        logger.error(f"Error in height router: {e}")
        raise HTTPException(status_code=500, detail=str(e))
