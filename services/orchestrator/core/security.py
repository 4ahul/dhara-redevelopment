"""
Dhara AI — Security Utilities
Password hashing and JWT token management. No DB access here — pure crypto helpers.
"""

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt as pyjwt
from jose import JWTError
from jose import jwt as jose_jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError as JWTInvalidTokenError

from .config import settings

logger = logging.getLogger(__name__)

# Module-level singleton — avoids fetching JWKS on every request
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.CLERK_JWT_ISSUER}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=3600,
        )
    return _jwks_client


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
    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """
    Decode JWT — tries local secret (HS256) first,
    then falls back to Clerk RSA (RS256) public key validation via JWKS.
    """
    # 1. Try Local Symmetric Token (PMC/Admin)
    try:
        return jose_jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            issuer="dhara-ai",
            options={"verify_exp": True, "require": ["sub", "iss"]},
        )
    except jose_jwt.ExpiredSignatureError as e:
        from fastapi import HTTPException

        logger.warning("JWT expired")
        raise HTTPException(status_code=401, detail="Token expired") from e
    except JWTError:
        pass

    # 2. Try External Clerk Asymmetric Token (Social/Client)
    try:
        # Use PyJWKClient to dynamically fetch the correct signing key from Clerk's JWKS
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        logger.info(f"Using signing key with kid: {signing_key.key_id}")
        return pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.CLERK_JWT_ISSUER,
            options={"verify_aud": False, "verify_iss": True},  # Verify issuer
        )
    except JWTInvalidTokenError as e:
        from fastapi import HTTPException

        logger.warning(f"JWT Validation failed: {e!s}")
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
    except Exception as e:
        from fastapi import HTTPException

        logger.exception(f"Unexpected error during Clerk JWT validation: {type(e).__name__}: {e!s}")
        raise HTTPException(status_code=401, detail="Invalid or expired token") from e
