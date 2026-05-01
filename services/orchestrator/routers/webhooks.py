"""
Clerk Webhooks
Handles events: user.created, user.updated, user.deleted, session.created, session.ended
"""

import base64
import hmac
import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from ..core.config import settings
from ..core.dependencies import get_db
from ..models.enums import UserRole
from ..repositories import user_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

_SVIX_TOLERANCE_SECONDS = 300


class ClerkWebhookEvent(BaseModel):
    type: str
    data: dict


def verify_clerk_signature(
    body: bytes,
    svix_id: str | None,
    svix_timestamp: str | None,
    svix_signature: str | None,
) -> bool:
    """Verify Clerk webhook signature using Svix standard.

    Signed content: "{svix-id}.{svix-timestamp}.{raw_body}"
    Secret format:  "whsec_<base64>" from Clerk dashboard.
    Signature format: space-separated "v1,<base64>" entries.
    """
    if not settings.CLERK_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    if not svix_id or not svix_timestamp or not svix_signature:
        return False

    # Replay-attack guard
    try:
        ts = int(svix_timestamp)
        now = int(datetime.now(timezone.utc).timestamp())
        if abs(now - ts) > _SVIX_TOLERANCE_SECONDS:
            logger.warning("Webhook timestamp too old or too far in future: %s", svix_timestamp)
            return False
    except ValueError:
        return False

    # Decode secret (strip optional "whsec_" prefix then base64-decode)
    secret = settings.CLERK_WEBHOOK_SECRET
    if secret.startswith("whsec_"):
        secret = secret[len("whsec_"):]
    try:
        secret_bytes = base64.b64decode(secret)
    except Exception:
        logger.error("CLERK_WEBHOOK_SECRET is not valid base64")
        return False

    # Build signed content
    signed_content = f"{svix_id}.{svix_timestamp}.".encode() + body

    expected = base64.b64encode(
        hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
    ).decode()

    # svix-signature may contain multiple space-separated "v1,<base64>" entries
    for sig in svix_signature.split(" "):
        if sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected):
            return True

    return False


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    svix_signature: str | None = Header(None, alias="svix-signature"),
):
    """Handle Clerk webhook events."""
    body = await request.body()

    # Verify Svix signature
    if not verify_clerk_signature(body, svix_id, svix_timestamp, svix_signature):
        logger.warning("Invalid Clerk webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = await request.json()
    except Exception:
        logger.error("Failed to parse webhook JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type", "")
    data = event.get("data", {})

    logger.info(f"Received Clerk webhook: {event_type}")

    # Handle events
    if event_type == "user.created":
        await handle_user_created(db, data)
    elif event_type == "user.updated":
        await handle_user_updated(db, data)
    elif event_type == "user.deleted":
        await handle_user_deleted(db, data)
    elif event_type == "session.created":
        await handle_session_created(db, data)
    elif event_type == "session.ended":
        await handle_session_ended(db, data)
    else:
        logger.info(f"Unhandled event type: {event_type}")

    return {"status": "ok"}


async def handle_user_created(db: AsyncSession, data: dict):
    """Handle user.created event - create user in DB."""
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("user.created event missing id")
        return

    # Check if user already exists
    existing = await user_repository.get_user_by_clerk_id(db, clerk_id)
    if existing:
        logger.info(f"User {clerk_id} already exists, skipping creation")
        return

    # Extract user data
    email = data.get("email_addresses", [{}])[0].get("email_address", "") if data.get("email_addresses") else ""
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or email or "Unknown"
    avatar_url = data.get("image_url")

    # Create user
    await user_repository.create_user(
        db,
        {
            "clerk_id": clerk_id,
            "email": email,
            "name": name,
            "role": UserRole.PMC,
            "avatar_url": avatar_url,
            "is_active": True,
            "last_login_at": datetime.utcnow(),
        },
    )
    await db.commit()
    logger.info(f"Created user from webhook: {email} ({clerk_id})")


async def handle_user_updated(db: AsyncSession, data: dict):
    """Handle user.updated event - update user in DB."""
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("user.updated event missing id")
        return

    user = await user_repository.get_user_by_clerk_id(db, clerk_id)
    if not user:
        logger.warning(f"User {clerk_id} not found for update")
        return

    # Update fields
    email = data.get("email_addresses", [{}])[0].get("email_address", "") if data.get("email_addresses") else ""
    first_name = data.get("first_name", "")
    last_name = data.get("last_name", "")
    name = f"{first_name} {last_name}".strip() or email
    avatar_url = data.get("image_url")

    user.email = email or user.email
    user.name = name or user.name
    user.avatar_url = avatar_url or user.avatar_url

    await db.commit()
    logger.info(f"Updated user from webhook: {email} ({clerk_id})")


async def handle_user_deleted(db: AsyncSession, data: dict):
    """Handle user.deleted event - deactivate user in DB."""
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("user.deleted event missing id")
        return

    user = await user_repository.get_user_by_clerk_id(db, clerk_id)
    if not user:
        logger.warning(f"User {clerk_id} not found for deletion")
        return

    # Deactivate user instead of hard delete
    user.is_active = False
    await db.commit()
    logger.info(f"Deactivated user from webhook: {user.email} ({clerk_id})")


async def handle_session_created(db: AsyncSession, data: dict):
    """Handle session.created event - update last login."""
    user_id = data.get("user_id")
    if not user_id:
        logger.warning("session.created event missing user_id")
        return

    user = await user_repository.get_user_by_clerk_id(db, user_id)
    if user:
        user.last_login_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Updated last login for user: {user_id}")


async def handle_session_ended(db: AsyncSession, data: dict):
    """Handle session.ended event - optional: track logout."""
    user_id = data.get("user_id")
    if user_id:
        logger.info(f"Session ended for user: {user_id}")
    # Could track session end time if needed