import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from services.rag_service.db.session import get_db, User
from services.rag_service.core.auth import (
    decode_token, generate_session_id
)
from services.rag_service.core.config import settings

# Note: We need password hashing and token generation logic. 
# Re-adding them here or importing from a utility.
import bcrypt
import jwt

router = APIRouter(prefix="/api/auth", tags=["Auth"])
logger = logging.getLogger(__name__)

# --- Auth Helpers ---
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

from services.rag_service.schemas.auth import RegisterRequest, LoginRequest

@router.post("/register")
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=request.email,
        username=request.email.split("@")[0],
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        auth_provider="email",
        is_verified=True, 
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Registration successful", "user_id": user.id}

@router.post("/login")
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        (User.email == request.email) | (User.username == request.email)
    ).first()

    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
        }
    }

