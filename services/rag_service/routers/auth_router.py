import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form, Header, Query
from typing import Optional
import uuid

from db.session import get_db
from db.models import User
from core.auth import (
    hash_password, verify_password, create_access_token, 
    create_verification_token, hash_verification_token,
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS, PASSWORD_RESET_TOKEN_EXPIRE_HOURS
)
from services.email_service import (
    send_verification_email, send_password_reset_email, send_welcome_email
)
from schemas.chat import RegisterRequest, LoginRequest
from core.dependencies import require_auth

DEV_MODE = os.environ.get("DEV_MODE", "false").lower() == "true"
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")

router = APIRouter(prefix="/api/auth", tags=["Auth"])

@router.post("/register")
async def register(
    request: RegisterRequest, background_tasks: BackgroundTasks, db=Depends(get_db)
):
    existing = (
        db.query(User)
        .filter(
            (User.email == request.email)
            | (User.username == request.email.split("@")[0])
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    verification_token = create_verification_token()
    hashed_token = hash_verification_token(verification_token)
    token_expires = datetime.utcnow() + timedelta(
        hours=EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
    )

    user = User(
        email=request.email,
        username=request.email.split("@")[0],
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        auth_provider="email",
        is_verified=False,
        verification_token=hashed_token,
        verification_token_expires=token_expires,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    verification_link = f"{frontend_url}/auth/verify?token={verification_token}"
    background_tasks.add_task(send_verification_email, request.email, verification_link)

    return {
        "message": "Registration successful. Please check your email to verify your account.",
        "user_id": user.id,
    }

@router.post("/login")
async def login(request: LoginRequest, db=Depends(get_db)):
    user = (
        db.query(User)
        .filter((User.email == request.email) | (User.username == request.email))
        .first()
    )
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    if not user.is_verified and user.auth_provider == "email" and not DEV_MODE:
        return {"requires_verification": True, "email": user.email}

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "is_verified": user.is_verified,
        },
    }

@router.get("/verify")
async def verify_email(token: str, db=Depends(get_db)):
    hashed_token = hash_verification_token(token)
    user = (
        db.query(User)
        .filter(
            User.verification_token == hashed_token,
            User.verification_token_expires > datetime.utcnow(),
        )
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification token"
        )

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.commit()

    send_welcome_email(user.email, user.full_name or user.username)

    return {"message": "Email verified successfully"}

@router.post("/forgot-password")
async def forgot_password(
    background_tasks: BackgroundTasks, email: str = Form(...), db=Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if user and user.auth_provider == "email" and user.hashed_password:
        reset_token = create_verification_token()
        user.reset_token = hash_verification_token(reset_token)
        user.reset_token_expires = datetime.utcnow() + timedelta(
            hours=PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )
        db.commit()

        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        reset_link = f"{frontend_url}/auth/reset-password?token={reset_token}"
        background_tasks.add_task(send_password_reset_email, email, reset_link)

    return {
        "message": "If an account exists with this email, a password reset link has been sent"
    }

@router.post("/reset-password")
async def reset_password(
    token: str = Form(...), new_password: str = Form(...), db=Depends(get_db)
):
    hashed_token = hash_verification_token(token)
    user = (
        db.query(User)
        .filter(
            User.reset_token == hashed_token,
            User.reset_token_expires > datetime.utcnow(),
        )
        .first()
    )

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()

    return {"message": "Password reset successfully"}

@router.get("/me")
async def get_me(
    authorization: str = Header(None),
    token: Optional[str] = Query(None),
    db=Depends(get_db),
):
    payload = require_auth(authorization, token, db)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
