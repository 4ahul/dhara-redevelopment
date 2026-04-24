"""Profile Routes — GET/PATCH /api/profile, POST /api/profile/portfolio|avatar"""

import logging

from core.dependencies import get_current_user, get_profile_service
from fastapi import APIRouter, Depends, File, UploadFile
from schemas.profile import PortfolioUploadResponse, ProfileResponse, ProfileUpdate

from services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=ProfileResponse)
async def get_profile(user=Depends(get_current_user)):
    return ProfileResponse.model_validate(user)


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    req: ProfileUpdate,
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
):
    return await service.update_profile(user, req)


@router.post("/portfolio", response_model=PortfolioUploadResponse)
async def upload_portfolio_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
):
    return await service.handle_portfolio_upload(user, file)


@router.post("/avatar")
async def upload_avatar_image(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service)
):
    return await service.handle_avatar_upload(user, file)



