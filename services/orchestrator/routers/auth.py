"""Auth Routes

POST /api/auth/sync          — provision/refresh DB user from a Clerk session token
GET  /api/auth/me            — return current authenticated user's profile
POST /api/auth/admin/login   — password login for ADMIN service accounts only
POST /api/auth/admin/logout  — admin logout (session invalidation is Clerk-side)
"""

import logging
from fastapi import APIRouter, Depends, Header
from core.dependencies import get_current_user, get_auth_service
from services.auth_service import AuthService
from schemas.auth import LoginRequest, AuthResponse, MeResponse, LogoutResponse
from models import UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/sync", response_model=AuthResponse)
async def sync_clerk_user(
    authorization: str = Header(None),
    service: AuthService = Depends(get_auth_service),
):
    """Provision or refresh the caller's DB record from their Clerk session token.

    Call this once after Clerk sign-in completes on the frontend.  Subsequent
    requests use the standard Bearer token flow — no repeated sync needed.
    """
    from fastapi import HTTPException
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.removeprefix("Bearer ").strip()
    return await service.sync_clerk_user(token)


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
    )


@router.post("/admin/login", response_model=AuthResponse)
async def admin_login(req: LoginRequest, service: AuthService = Depends(get_auth_service)):
    """Password-based login for ADMIN service accounts only."""
    return await service.admin_login(req)


@router.post("/admin/logout", response_model=LogoutResponse)
async def admin_logout(user=Depends(get_current_user)):
    """Admin logout — revoke server-side session if needed."""
    from fastapi import HTTPException
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    logger.info("Admin logout: %s", user.email)
    return LogoutResponse()
