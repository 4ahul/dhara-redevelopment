"""Auth Routes — GET /auth/me only.

User creation handled by Clerk webhook (POST /api/webhooks/clerk).
Frontend uses Clerk JWT directly as Bearer token on all API calls.
"""

import logging

from fastapi import APIRouter, Depends

from ..core.dependencies import get_current_user
from ..schemas.auth import MeResponse, UserMetadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=MeResponse)
async def me(user=Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
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
