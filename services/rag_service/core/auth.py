import logging
import os
import uuid

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from .config import settings

logger = logging.getLogger(__name__)

# Fallback for local development/testing without Clerk
SECRET_KEY = os.environ.get("SECRET_KEY", "temporary-secret-key-for-dhara-rag")


def decode_token(token: str) -> dict | None:
    """
    Decodes and validates a JWT token, trying Clerk RS256 first (via JWKS), then local HS256.
    """
    # 1. Try Clerk RS256 via dynamic JWKS
    try:
        jwks_client = PyJWKClient(settings.CLERK_JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token, signing_key.key, algorithms=["RS256"], options={"verify_aud": False}
        )
    except InvalidTokenError:
        logger.debug("Clerk RS256 token decoding failed, trying HS256.")
        # Fall through to HS256
    except Exception as e:
        logger.exception(f"Unexpected error decoding Clerk RS256 token: {e}")
        # Fall through in case of other errors

    # 2. Try local HS256 (frontend's own login/register flow)
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        logger.warning("Local HS256 token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid local HS256 token: {e}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error decoding local HS256 token: {e}")
        return None


def generate_session_id() -> str:
    """Generates a random short session ID."""
    return str(uuid.uuid4())[:8]
