"""
Dhara AI — Security Utilities
Password hashing and JWT token management. No DB access here — pure crypto helpers.
"""

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from .config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    # Ensure password is within bcrypt limit (unlikely here but safe)
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT ─────────────────────────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    name: str,
    expires_hours: int = 24,
    permanent: bool = False,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "name": name,
        "iat": now,
        "iss": "dhara-ai",
    }
    if not permanent:
        payload["exp"] = now + timedelta(hours=expires_hours)
    # permanent tokens have no "exp" claim → never expire
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """
    Decode JWT — tries local secret (HS256) first,
    then falls back to Clerk RSA (RS256) public key validation.
    """
    # 1. Try Local Symmetric Token (PMC/Admin)
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            issuer="dhara-ai",
            options={"verify_exp": True, "require": ["sub", "iss"]},
        )
    except jwt.ExpiredSignatureError as e:
        from fastapi import HTTPException

        logger.warning("JWT expired")
        raise HTTPException(status_code=401, detail="Token expired") from e
    except JWTError:
        pass

    # 2. Try External Clerk Asymmetric Token (Social/Client)
    try:
        # RS256 is the standard for Clerk PEM public keys
        return jwt.decode(
            token,
            settings.CLERK_JWT_KEY,
            algorithms=["RS256"],
            issuer=settings.CLERK_JWT_ISSUER,
            options={"verify_aud": False},  # Permissive mode since audience is not in .env
        )
    except JWTError as e:
        from fastapi import HTTPException

        logger.warning(f"JWT Validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
