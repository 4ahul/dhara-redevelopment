import logging

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from ..db.session import User, get_db
from .auth import decode_token
from .config import settings

logger = logging.getLogger(__name__)


def get_token(authorization: str = Header(None), token: str | None = Query(None)) -> str | None:
    """Extracts bearer token from header or query string."""
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "")
    return token


def require_auth(
    authorization: str = Header(None),
    token: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """
    Production-ready auth dependency.
    Validates Clerk JWT and ensures user exists in local database for FK constraints.
    """
    if settings.DEV_MODE:
        # Check if dev user exists
        dev_user = db.query(User).filter(User.id == "dev_user_1").first()
        if not dev_user:
            dev_user = User(
                id="dev_user_1",
                email="dev@dhara.local",
                username="devuser",
                full_name="Developer",
            )
            db.add(dev_user)
            db.commit()
            db.refresh(dev_user)
        return {"sub": dev_user.id, "email": dev_user.email, "dev_mode": True}

    auth_token = get_token(authorization, token)
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Handle mock token for testing
    if auth_token == "mock":
        mock_user = db.query(User).filter(User.id == "mock_user_1").first()
        if not mock_user:
            mock_user = User(
                id="mock_user_1",
                email="mock@example.com",
                username="mockuser",
                full_name="Mock User",
            )
            db.add(mock_user)
            db.commit()
            db.refresh(mock_user)
        return {"sub": mock_user.id, "email": mock_user.email, "mock": True}

    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Clerk specific claims
    # sub is the Clerk User ID
    user_id = payload.get("sub")
    email = payload.get("email") or payload.get("upn")  # Some JWTs use upn for email

    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user identification")

    # Ensure user exists locally for FK consistency
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        try:
            user = User(
                id=user_id,
                email=email,
                username=email.split("@")[0] if email else f"user_{user_id[:8]}",
                full_name=payload.get("name") or "User",
            )
            db.add(user)
            db.commit()
            logger.info(f"Synchronized new user from JWT: {user_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync user from JWT: {e}")
            # We still allow the request if we have the ID

    return payload
