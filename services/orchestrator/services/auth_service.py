"""
Dhara AI — Auth Service
Handles Clerk-backed user provisioning and legacy admin password auth.
"""

import logging
import httpx
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import decode_token, hash_password, verify_password, create_access_token
from models.enums import UserRole
from schemas.auth import LoginRequest, AuthResponse, AuthUserInfo
from repositories import user_repository

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ #
    # Clerk — primary auth path                                           #
    # ------------------------------------------------------------------ #

    async def sync_clerk_user(self, clerk_token: str) -> AuthResponse:
        """Provision or refresh a user from a Clerk session token.

        Called once after Clerk sign-in to ensure the user exists in our DB.
        Fetches authoritative user data from the Clerk REST API so we never
        rely on what claims happen to be in the JWT.
        """
        payload = decode_token(clerk_token)
        clerk_id: str = payload.get("sub", "")
        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid Clerk token")

        clerk_user = await self._fetch_clerk_user(clerk_id)

        email = clerk_user.get("email_addresses", [{}])[0].get("email_address", "")
        name = (
            f"{clerk_user.get('first_name') or ''} {clerk_user.get('last_name') or ''}".strip()
            or email
        )
        avatar_url = clerk_user.get("image_url")

        # Upsert: find by clerk_id first, fall back to email match
        user = await user_repository.get_user_by_clerk_id(self.db, clerk_id)

        if not user and email:
            user = await user_repository.get_user_by_email(self.db, email)

        if user:
            # Refresh fields that may have changed in Clerk
            user.clerk_id = clerk_id
            user.name = name or user.name
            user.avatar_url = avatar_url or user.avatar_url
            user.last_login_at = datetime.utcnow()
            await self.db.flush()
        else:
            # First login — provision with default PMC role
            user = await user_repository.create_user(self.db, {
                "clerk_id": clerk_id,
                "email": email,
                "name": name or "Unknown",
                "role": UserRole.PMC,
                "avatar_url": avatar_url,
                "is_active": True,
                "last_login_at": datetime.utcnow(),
            })
            logger.info("Provisioned new Clerk user: %s (%s)", email, clerk_id)

        return AuthResponse(
            access_token=clerk_token,
            user=AuthUserInfo(
                id=str(user.id),
                email=user.email,
                name=user.name,
                role=user.role.value,
                organization=user.organization,
                avatar_url=user.avatar_url,
            ),
        )

    async def _fetch_clerk_user(self, clerk_id: str) -> dict:
        """Call Clerk REST API to get authoritative user data."""
        url = f"{settings.CLERK_API_BASE_URL}/users/{clerk_id}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
                )
            if resp.status_code == 404:
                raise HTTPException(status_code=401, detail="Clerk user not found")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Clerk API error %s: %s", exc.response.status_code, exc.response.text)
            raise HTTPException(status_code=502, detail="Failed to verify identity with Clerk")
        except httpx.RequestError as exc:
            logger.error("Clerk API unreachable: %s", exc)
            raise HTTPException(status_code=502, detail="Auth service temporarily unavailable")

    # ------------------------------------------------------------------ #
    # Admin — password auth (service accounts only)                       #
    # ------------------------------------------------------------------ #

    async def admin_login(self, req: LoginRequest) -> AuthResponse:
        """Password-based login restricted to ADMIN role service accounts."""
        user = await user_repository.get_user_by_email(self.db, req.email)

        if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        if user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Admin credentials required")

        await user_repository.update_last_login(self.db, user)

        token = create_access_token(str(user.id), user.email, user.role.value, user.name)
        return AuthResponse(
            access_token=token,
            user=AuthUserInfo(
                id=str(user.id),
                email=user.email,
                name=user.name,
                role=user.role.value,
                organization=user.organization,
                avatar_url=user.avatar_url,
            ),
        )
