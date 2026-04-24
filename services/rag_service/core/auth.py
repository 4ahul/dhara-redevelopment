import os
import logging
from typing import Optional
import jwt
import uuid

logger = logging.getLogger(__name__)

# Clerk configuration
CLERK_JWT_KEY = os.environ.get("CLERK_JWT_KEY", "")
# Fallback for local development/testing without Clerk
SECRET_KEY = os.environ.get("SECRET_KEY", "temporary-secret-key-for-dhara-rag")
ALGORITHM = "RS256" if CLERK_JWT_KEY.startswith("-----BEGIN PUBLIC KEY-----") else "HS256"

def decode_token(token: str) -> Optional[dict]:
    """
    Decodes and validates a JWT token, trying Clerk RS256 first, then local HS256.
    """
    # 1. Try Clerk RS256 if CLERK_JWT_KEY configured
    if CLERK_JWT_KEY:
        try:
            return jwt.decode(token, CLERK_JWT_KEY, algorithms=["RS256"],
                               options={"verify_aud": False})
        except jwt.InvalidTokenError:
            logger.debug("Clerk RS256 token decoding failed, trying HS256.")
            pass  # Fall through to HS256
        except Exception as e:
            logger.error(f"Unexpected error decoding Clerk RS256 token: {e}")
            pass # Fall through in case of other errors
    
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
        logger.error(f"Unexpected error decoding local HS256 token: {e}")
        return None

def generate_session_id() -> str:
    """Generates a random short session ID."""
    return str(uuid.uuid4())[:8]

