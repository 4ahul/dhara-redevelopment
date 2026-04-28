"""
Dhara AI — FastAPI Dependencies
Reusable Depends() callables for auth, roles, and DB sessions.
Refactored to use CRUD layer for user retrieval.
"""

import logging
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.core.security import decode_token
from services.orchestrator.repositories import user_repository

logger = logging.getLogger(__name__)


# ─── DB Session ─────────────────────────────────────────────────────────────


async def get_db() -> AsyncSession:
    """Yield an async DB session. Imported from services.orchestrator.db module at runtime."""
    from services.orchestrator.db import async_session_factory

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ─── Current User ───────────────────────────────────────────────────────────


async def get_current_user(
    authorization: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Extract and validate user from JWT. Returns the full User ORM object.

    Supports two token types:
    - HS256 (admin service accounts) — sub is a UUID string
    - RS256 Clerk tokens           — sub is a Clerk user ID (e.g. "user_abc123")

    For Clerk tokens: if the user has no DB record yet, they are auto-provisioned
    on first request via the Clerk REST API.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Authorization header required (Bearer <token>)"
        )

    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = None
    try:
        # HS256 admin tokens carry a UUID as sub
        user = await user_repository.get_user_by_id(db, UUID(user_id))
    except (ValueError, TypeError):
        # Clerk tokens carry a Clerk ID string as sub
        user = await user_repository.get_user_by_clerk_id(db, user_id)

        if not user:
            # Auto-provision on first request for this Clerk user
            from services.orchestrator.services.auth_service import AuthService

            await AuthService(db).sync_clerk_user(token)
            user = await user_repository.get_user_by_clerk_id(db, user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return user


async def get_current_user_id(authorization: str = Header(None)) -> str:
    """Lightweight dependency — returns just the user ID string from JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    payload = decode_token(authorization.removeprefix("Bearer ").strip())
    return payload.get("sub", "")


# ─── Role Guards ─────────────────────────────────────────────────────────────


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that enforces role membership."""

    async def _guard(
        authorization: str = Header(None),
        db: AsyncSession = Depends(get_db),
    ):
        user = await get_current_user(authorization, db)
        if user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {', '.join(allowed_roles)}. You have: {user.role.value}",
            )
        return user

    return _guard


# ─── Service Providers ───────────────────────────────────────────────────────


async def get_auth_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.auth_service import AuthService

    return AuthService(db)


async def get_team_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.team_service import TeamService

    return TeamService(db)


async def get_admin_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.admin_service import AdminService

    return AdminService(db)


async def get_society_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.society_service import SocietyService

    return SocietyService(db)


async def get_feasibility_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.feasibility_service import FeasibilityService

    return FeasibilityService(db)


async def get_profile_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.profile_service import ProfileService

    return ProfileService(db)


async def get_landing_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.landing_service import LandingService

    return LandingService(db)


async def get_agent_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.agent_service import AgentService

    return AgentService(db)


async def get_legacy_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.legacy_service import LegacyService

    return LegacyService(db)


async def get_search_service(db: AsyncSession = Depends(get_db)):
    from services.orchestrator.services.search_service import SearchService

    return SearchService(db)


require_admin = require_role("admin")
require_pmc = require_role("pmc", "admin")
