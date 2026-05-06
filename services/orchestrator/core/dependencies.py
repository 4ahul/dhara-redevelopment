"""
Dhara AI — FastAPI Dependencies
Reusable Depends() callables for auth, roles, and DB sessions.
Refactored to use CRUD layer for user retrieval.
"""

import logging
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import settings
from orchestrator.core.security import decode_token
from orchestrator.repositories import user_repository

logger = logging.getLogger(__name__)

# Standard security scheme for Swagger UI integration
# auto_error=False to allow test mode bypass
security = HTTPBearer(auto_error=False)

# ─── DB Session ─────────────────────────────────────────────────────────────


async def get_db() -> AsyncSession:
    """Yield an async DB session. Imported from orchestrator.db module at runtime."""
    from orchestrator.db import async_session_factory

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
    request: Request = None,
    auth: HTTPAuthorizationCredentials = None,
    db: AsyncSession = Depends(get_db),
):
    """Extract and validate user from JWT. Returns the full User ORM object."""
    # Test mode: bypass auth if X-Test-User-ID header is present (dev only)
    if request and hasattr(request, 'headers') and 'X-Test-User-ID' in request.headers and settings.DEBUG:
        test_user_id = request.headers.get('X-Test-User-ID')
        user = await user_repository.get_user_by_id(db, UUID(test_user_id))
        if user:
            return user
    
    # Normal auth flow
    if auth is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.credentials
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
            from orchestrator.services.auth_service import AuthService

            await AuthService(db).sync_clerk_user(token)
            user = await user_repository.get_user_by_clerk_id(db, user_id)

    if not user:
        raise HTTPException(status_code=401, detail="User not found or deactivated")
    return user


async def get_current_user_id(auth: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Lightweight dependency — returns just the user ID string from JWT."""
    payload = decode_token(auth.credentials)
    return payload.get("sub", "")


# ─── Role Guards ─────────────────────────────────────────────────────────────


def require_role(*allowed_roles: str):
    """Factory: returns a dependency that enforces role membership."""

    async def _guard(
        auth: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db),
    ):
        user = await get_current_user(auth, db)
        if user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {', '.join(allowed_roles)}. You have: {user.role.value}",
            )
        return user

    return _guard


# ─── Service Providers ───────────────────────────────────────────────────────


async def get_auth_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.auth_service import AuthService

    return AuthService(db)


async def get_team_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.team_service import TeamService

    return TeamService(db)


async def get_admin_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.admin_service import AdminService

    return AdminService(db)


async def get_society_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.society_service import SocietyService

    return SocietyService(db)


async def get_feasibility_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.feasibility_service import FeasibilityService

    return FeasibilityService(db)


async def get_profile_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.profile_service import ProfileService

    return ProfileService(db)


async def get_landing_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.landing_service import LandingService

    return LandingService(db)


async def get_agent_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.agent_service import AgentService

    return AgentService(db)


async def get_legacy_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.legacy_service import LegacyService

    return LegacyService(db)


async def get_search_service(db: AsyncSession = Depends(get_db)):
    from orchestrator.services.search_service import SearchService

    return SearchService(db)


require_admin = require_role("admin")
require_pmc = require_role("pmc", "admin")
