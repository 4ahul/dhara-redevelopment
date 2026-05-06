"""
User CRUD Operations — Specialized repository for user-related data access.
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.enums import UserRole
from ..models.user import User


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    """Fetch a single user by their primary UUID."""
    return (
        await db.execute(select(User).where(User.id == user_id, User.is_active))
    ).scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Fetch a single user by email."""
    return (
        await db.execute(select(User).where(User.email == email, User.is_active))
    ).scalar_one_or_none()


async def get_user_by_clerk_id(db: AsyncSession, clerk_id: str) -> User | None:
    """Fetch a single user by their external Clerk ID."""
    return (
        await db.execute(select(User).where(User.clerk_id == clerk_id, User.is_active))
    ).scalar_one_or_none()


async def list_users_by_role(
    db: AsyncSession,
    role: UserRole,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    is_active: bool | None = None,
) -> tuple[Sequence[User], int]:
    """List users with a specific role, supporting pagination and search."""
    base = select(User).where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active == is_active)
    if search:
        base = base.where(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.organization.ilike(f"%{search}%"),
            )
        )

    # Get total count
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    # Get rows
    stmt = base.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(stmt)).scalars().all()

    return rows, total


async def create_user(db: AsyncSession, user_data: dict) -> User:
    """Initialize a new user record."""
    user = User(**user_data)
    db.add(user)
    await db.flush()  # Flush to get IDs/Defaults without committing
    await db.refresh(user)
    return user


async def update_last_login(db: AsyncSession, user: User) -> None:
    """Atomic update for last login timestamp."""
    user.last_login_at = datetime.now(UTC)
    await db.flush()
