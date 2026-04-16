from datetime import datetime, timedelta
from typing import Optional
import uuid
import hashlib
import os
import jwt
import bcrypt

_secret = os.environ.get("SECRET_KEY", "")
if not _secret:
    raise RuntimeError(
        "SECRET_KEY environment variable is required. "
        "Set a strong random secret in .env or your deployment config."
    )
SECRET_KEY = _secret

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = 24
PASSWORD_RESET_TOKEN_EXPIRE_HOURS = 1

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def create_verification_token() -> str:
    return str(uuid.uuid4()) + "-" + str(uuid.uuid4())


def create_session_token() -> str:
    return str(uuid.uuid4())


def generate_session_id() -> str:
    return str(uuid.uuid4())


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_email_verification_link(token: str, base_url: str = None) -> str:
    url = base_url or FRONTEND_URL
    return f"{url}/auth/verify-email?token={token}"


def create_password_reset_link(token: str, base_url: str = None) -> str:
    url = base_url or FRONTEND_URL
    return f"{url}/auth/reset-password?token={token}"
