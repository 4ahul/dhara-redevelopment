import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from ...core.dependencies import get_landing_service
from ...schemas.landing import (
    ContactRequestSchema,
    FormSubmissionResponse,
    GetStartedRequestSchema,
    LandingPageResponse,
)
from ...services.landing_service import LandingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Public"])


@router.get("/landing", response_model=LandingPageResponse)
async def get_landing_page(service: LandingService = Depends(get_landing_service)):
    """Fetch content and configuration for the Dhara AI landing page."""
    return await service.get_landing_page()


@router.post("/get-started", response_model=FormSubmissionResponse, status_code=201)
async def submit_interest(
    req: GetStartedRequestSchema,
    bg: BackgroundTasks,
    service: LandingService = Depends(get_landing_service),
):
    """Initial onboarding request for societies interested in redevelopment."""
    return await service.submit_get_started(req, bg)


@router.post("/contact-us", response_model=FormSubmissionResponse, status_code=201)
async def contact_us(
    req: ContactRequestSchema,
    bg: BackgroundTasks,
    service: LandingService = Depends(get_landing_service),
):
    """Send a message to the Dhara AI support or sales team."""
    return await service.submit_contact(req, bg)
