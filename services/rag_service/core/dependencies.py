from typing import Optional
from fastapi import Header, Query, HTTPException
from db.session import SessionLocal
from db.models import User
from core.auth import decode_token

def get_current_user(
    authorization: str = Header(None), token: Optional[str] = Query(None), db=None
) -> Optional[User]:
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.replace("Bearer ", "")
    elif token:
        auth_token = token

    if not auth_token:
        return None

    payload = decode_token(auth_token)
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    if not db:
        db = SessionLocal()

    return db.query(User).filter(User.id == int(user_id)).first()

def require_auth(
    authorization: str = Header(None), token: Optional[str] = Query(None), db=None
):
    auth_token = None
    if authorization and authorization.startswith("Bearer "):
        auth_token = authorization.replace("Bearer ", "")
    elif token:
        auth_token = token

    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
