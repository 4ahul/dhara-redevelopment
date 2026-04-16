"""Landing Page Routes — Refactored version using Service Layer"""

import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from core.dependencies import get_landing_service
from services.landing_service import LandingService
from schemas.landing import GetStartedRequestSchema, ContactRequestSchema, LandingPageResponse, FormSubmissionResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Landing Page"])


@router.get("/landing", response_model=LandingPageResponse)
async def get_landing_page(service: LandingService = Depends(get_landing_service)):
    return await service.get_landing_page()


@router.post("/get-started", response_model=FormSubmissionResponse, status_code=201)
async def get_started(
    req: GetStartedRequestSchema, 
    bg: BackgroundTasks, 
    service: LandingService = Depends(get_landing_service)
):
    return await service.submit_get_started(req, bg)


@router.post("/contact-us", response_model=FormSubmissionResponse, status_code=201)
@router.post("/contact", response_model=FormSubmissionResponse, include_in_schema=False)
async def contact_us(
    req: ContactRequestSchema, 
    bg: BackgroundTasks, 
    service: LandingService = Depends(get_landing_service)
):
    return await service.submit_contact(req, bg)
