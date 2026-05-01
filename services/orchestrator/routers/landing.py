"""Landing Page Routes — Refactored version using Service Layer"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from ..core.dependencies import get_landing_service
from ..schemas.landing import (
    ContactRequestSchema,
    FormSubmissionResponse,
    GetStartedRequestSchema,
    LandingPageResponse,
)
from ..services.landing_service import LandingService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Landing Page"])


@router.get("/landing", response_model=LandingPageResponse)
async def get_landing_page(service: LandingService = Depends(get_landing_service)):
    return await service.get_landing_page()


@router.post("/get-started", response_model=FormSubmissionResponse, status_code=201)
async def get_started(
    req: GetStartedRequestSchema,
    bg: BackgroundTasks,
    service: LandingService = Depends(get_landing_service),
):
    return await service.submit_get_started(req, bg)


@router.post("/contact-us", response_model=FormSubmissionResponse, status_code=201)
async def contact_us(
    req: ContactRequestSchema,
    bg: BackgroundTasks,
    service: LandingService = Depends(get_landing_service),
):
    return await service.submit_contact(req, bg)
