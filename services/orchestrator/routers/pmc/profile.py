import logging

from fastapi import APIRouter, Depends, File, UploadFile

from ...core.dependencies import get_current_user, get_profile_service
from ...schemas.profile import (
    PortfolioUploadResponse,
    ProfileResponse,
    ProfileUpdate,
)
from ...services.profile_service import ProfileService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=ProfileResponse)
async def get_profile(user=Depends(get_current_user)):
    """Fetch current user profile details."""
    return ProfileResponse.model_validate(user)


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    req: ProfileUpdate,
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Update profile information (Name, Organization, etc.)."""
    return await service.update_profile(user, req)


@router.post("/portfolio", response_model=PortfolioUploadResponse)
async def upload_portfolio(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Upload a portfolio PDF/DOCX to showcase your professional experience."""
    return await service.handle_portfolio_upload(user, file)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Upload a professional avatar image."""
    return await service.handle_avatar_upload(user, file)
