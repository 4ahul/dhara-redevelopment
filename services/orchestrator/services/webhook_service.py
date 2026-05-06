import base64
import hashlib
import hmac
import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.enums import UserRole
from ..repositories import user_repository

logger = logging.getLogger(__name__)

_SVIX_TOLERANCE_SECONDS = 300


class WebhookService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def verify_clerk_signature(
        self,
        body: bytes,
        svix_id: str | None,
        svix_timestamp: str | None,
        svix_signature: str | None,
    ) -> bool:
        """Verify Clerk webhook signature using Svix standard."""
        if not settings.CLERK_WEBHOOK_SECRET:
            raise HTTPException(status_code=500, detail="Webhook secret not configured")

        if not svix_id or not svix_timestamp or not svix_signature:
            return False

        try:
            ts = int(svix_timestamp)
            now = int(datetime.now(UTC).timestamp())
            if abs(now - ts) > _SVIX_TOLERANCE_SECONDS:
                logger.warning("Webhook timestamp too old or too far in future: %s", svix_timestamp)
                return False
        except ValueError:
            return False

        secret = settings.CLERK_WEBHOOK_SECRET
        if secret.startswith("whsec_"):
            secret = secret[len("whsec_") :]
        try:
            secret_bytes = base64.b64decode(secret)
        except Exception:
            logger.exception("CLERK_WEBHOOK_SECRET is not valid base64")
            return False

        signed_content = f"{svix_id}.{svix_timestamp}.".encode() + body
        expected = base64.b64encode(
            hmac.new(secret_bytes, signed_content, hashlib.sha256).digest()
        ).decode()

        for sig in svix_signature.split(" "):
            if sig.startswith("v1,") and hmac.compare_digest(sig[3:], expected):
                return True

        return False

    async def handle_user_created(self, data: dict):
        """Handle user.created event - create user in DB."""
        clerk_id = data.get("id")
        if not clerk_id:
            logger.warning("user.created event missing id")
            return

        existing = await user_repository.get_user_by_clerk_id(self.db, clerk_id)
        if existing:
            logger.info(f"User {clerk_id} already exists, skipping creation")
            return

        email = (
            data.get("email_addresses", [{}])[0].get("email_address", "")
            if data.get("email_addresses")
            else ""
        )
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        name = f"{first_name} {last_name}".strip() or email or "Unknown"
        avatar_url = data.get("image_url")

        await user_repository.create_user(
            self.db,
            {
                "clerk_id": clerk_id,
                "email": email,
                "name": name,
                "role": UserRole.PMC,
                "avatar_url": avatar_url,
                "is_active": True,
                "last_login_at": datetime.now(UTC).replace(tzinfo=None),
            },
        )
        await self.db.commit()
        logger.info(f"Created user from webhook: {email} ({clerk_id})")

    async def handle_user_updated(self, data: dict):
        """Handle user.updated event - update user in DB."""
        clerk_id = data.get("id")
        if not clerk_id:
            logger.warning("user.updated event missing id")
            return

        user = await user_repository.get_user_by_clerk_id(self.db, clerk_id)
        if not user:
            logger.warning(f"User {clerk_id} not found for update")
            return

        email = (
            data.get("email_addresses", [{}])[0].get("email_address", "")
            if data.get("email_addresses")
            else ""
        )
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        name = f"{first_name} {last_name}".strip() or email
        avatar_url = data.get("image_url")

        user.email = email or user.email
        user.name = name or user.name
        user.avatar_url = avatar_url or user.avatar_url

        await self.db.commit()
        logger.info(f"Updated user from webhook: {email} ({clerk_id})")

    async def handle_user_deleted(self, data: dict):
        """Handle user.deleted event - deactivate user in DB."""
        clerk_id = data.get("id")
        if not clerk_id:
            logger.warning("user.deleted event missing id")
            return

        user = await user_repository.get_user_by_clerk_id(self.db, clerk_id)
        if not user:
            logger.warning(f"User {clerk_id} not found for deletion")
            return

        user.is_active = False
        await self.db.commit()
        logger.info(f"Deactivated user from webhook: {user.email} ({clerk_id})")

    async def handle_session_created(self, data: dict):
        """Handle session.created event - update last login."""
        clerk_user_id = data.get("user_id")
        if not clerk_user_id:
            return

        user = await user_repository.get_user_by_clerk_id(self.db, clerk_user_id)
        if user:
            user.last_login_at = datetime.now(UTC).replace(tzinfo=None)
            await self.db.commit()
            logger.info(f"Updated last login for user: {clerk_user_id}")
