"""
Dhara AI — Auth Service
Handles Clerk-backed user provisioning and legacy admin password auth.
"""

import logging
from datetime import UTC, datetime

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.security import (
    create_access_token,
    decode_token,
)
from ..models.enums import UserRole
from ..models.user import User
from ..repositories import user_repository
from ..schemas.auth import AuthResponse, AuthUserInfo

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------ #
    # Clerk — primary auth path                                           #
    # ------------------------------------------------------------------ #

    async def sync_clerk_user(self, clerk_token: str) -> AuthResponse:
        """Get user from DB after Clerk login.

        User should already exist from webhook. If not found, returns 404.
        This validates the token and returns user profile.
        """
        payload = decode_token(clerk_token)
        clerk_id: str = payload.get("sub", "")
        if not clerk_id:
            raise HTTPException(status_code=401, detail="Invalid Clerk token")

        # Get user from DB (already created by webhook)
        user = await user_repository.get_user_by_clerk_id(self.db, clerk_id)

        if not user:
            # Fallback: try by email from token (if webhook hasn't fired yet)
            email = (
                payload.get("email")
                or payload.get("email_addresses", [{}])[0].get("email_address", "")
                if isinstance(payload.get("email_addresses"), list)
                else ""
            )
            if email:
                user = await user_repository.get_user_by_email(self.db, email)

        if not user:
            user = await self._auto_create_from_claims(payload)

        # Update last login
        user.last_login_at = datetime.now(UTC)
        await self.db.flush()

        access_token = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role.value,
            name=user.name or "",
        )

        return AuthResponse(
            access_token=access_token,
            user=AuthUserInfo(
                id=str(user.id),
                email=user.email,
                name=user.name,
                role=user.role.value,
                organization=user.organization,
                avatar_url=user.avatar_url,
            ),
        )

    async def _auto_create_from_claims(self, payload: dict) -> User:
        """Create user in DB from Clerk JWT claims — used when webhook hasn't fired yet."""
        clerk_id = payload.get("sub", "") or ""
        email = payload.get("email") or ""
        if not email:
            try:
                ea = payload.get("email_addresses")
                if isinstance(ea, list) and ea:
                    email = ea[0].get("email_address", "")
            except Exception:
                email = ""
        first_name = payload.get("first_name", "") or ""
        last_name = payload.get("last_name", "") or ""
        name = payload.get("name") or f"{first_name} {last_name}".strip() or email or "Unknown"
        avatar_url = payload.get("image_url") or payload.get("profile_picture_url") or ""

        logger.info(f"Auto-creating user from JWT claims: clerk_id={clerk_id}, email={email}")
        return await user_repository.create_user(
            self.db,
            {
                "clerk_id": clerk_id,
                "email": email,
                "name": name,
                "role": UserRole.PMC,
                "avatar_url": avatar_url,
                "is_active": True,
                "last_login_at": datetime.now(UTC),
            },
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
            logger.exception("Clerk API error %s: %s", exc.response.status_code, exc.response.text)
            raise HTTPException(
                status_code=502, detail="Failed to verify identity with Clerk"
            ) from exc
        except httpx.RequestError as exc:
            logger.exception("Clerk API unreachable: %s", exc)
            raise HTTPException(
                status_code=502, detail="Auth service temporarily unavailable"
            ) from exc
