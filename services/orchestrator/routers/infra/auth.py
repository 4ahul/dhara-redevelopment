import logging

from fastapi import APIRouter, Depends

from ...core.dependencies import get_current_user
from ...schemas.auth import MeResponse, UserMetadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Infrastructure"])


@router.get("/me", response_model=MeResponse)
async def get_my_profile(user=Depends(get_current_user)):
    """Return the currently authenticated user's profile metadata."""
    return MeResponse(
        id=str(user.id),
        clerk_id=user.clerk_id,
        email=user.email,
        name=user.name,
        role=user.role.value,
        organization=user.organization,
        avatar_url=user.avatar_url,
        phone=user.phone,
        user_metadata=UserMetadata(
            full_name=user.name,
            user_type=user.role.value,
            company_name=user.organization,
            country=getattr(user, "country", None),
        ),
    )
