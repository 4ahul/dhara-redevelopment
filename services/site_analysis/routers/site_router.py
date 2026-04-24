from fastapi import APIRouter, HTTPException

try:
    from services.site_analysis.schemas import SiteAnalysisRequest, SiteAnalysisResponse
    from services.site_analysis.services import site_analysis_service
    from services.site_analysis.services.analyse import SiteAnalysisUnavailableError
except ImportError:
    from services.site_analysis.schemas import SiteAnalysisRequest, SiteAnalysisResponse
    from services.site_analysis.services import site_analysis_service
    from services.site_analysis.services.analyse import SiteAnalysisUnavailableError

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
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health():
    return {"status": "ok", "service": "site_analysis"}

