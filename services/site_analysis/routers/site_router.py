from fastapi import APIRouter, HTTPException

from ..schemas import SiteAnalysisRequest, SiteAnalysisResponse
from ..services import site_analysis_service
from ..services.analyse import SiteAnalysisUnavailableError

router = APIRouter()


@router.post("/analyse", response_model=SiteAnalysisResponse)
async def analyse_site(req: SiteAnalysisRequest):
    """Analyze site location, landmarks, and MCGM zone data."""
    try:
        result = await site_analysis_service.analyse(
            address=req.address, ward=req.ward, plot_no=req.plot_no
        )
        return result
    except SiteAnalysisUnavailableError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "geocoding_unavailable",
                "message": str(e),
                "suggestion": "Check API keys or provide coordinates manually",
            },
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/places/autocomplete")
async def autocomplete_places(q: str):
    """Autocomplete places in Mumbai via Google Maps."""
    if not q or len(q) < 3:
        return []
    try:
        return await site_analysis_service.autocomplete(q)
    except SiteAnalysisUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/places/{place_id}")
async def get_place_details(place_id: str):
    """Get full details (lat, lng, address) for a place_id."""
    try:
        return await site_analysis_service.get_place_details(place_id)
    except SiteAnalysisUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/health")
def health():
    return {"status": "ok", "service": "site_analysis"}
