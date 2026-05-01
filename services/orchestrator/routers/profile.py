"""Profile Routes — GET/PATCH /api/profile, POST /api/profile/portfolio|avatar"""

import logging

from fastapi import APIRouter, Depends, File, UploadFile

from ..core.dependencies import get_current_user, get_profile_service
from ..schemas.profile import (
    PortfolioUploadResponse,
    ProfileResponse,
    ProfileUpdate,
)
from ..services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("")
async def get_profile(user=Depends(get_current_user)):
    return ProfileResponse.model_validate(user).model_dump(by_alias=True)


@router.patch("")
async def update_profile(
    req: ProfileUpdate,
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    updated = await service.update_profile(user, req)
    if hasattr(updated, 'model_dump'):
        return updated.model_dump(by_alias=True)
    return ProfileResponse.model_validate(updated).model_dump(by_alias=True)


@router.post("/portfolio", response_model=PortfolioUploadResponse)
async def upload_portfolio_file(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.handle_portfolio_upload(user, file)


@router.post("/avatar")
async def upload_avatar_image(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.handle_avatar_upload(user, file)
