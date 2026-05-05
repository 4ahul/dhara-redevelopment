import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_db
from ...services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Infrastructure"])


def get_webhook_service(db: AsyncSession = Depends(get_db)) -> WebhookService:
    return WebhookService(db)


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    service: WebhookService = Depends(get_webhook_service),
    svix_id: str | None = Header(None, alias="svix-id"),
    svix_timestamp: str | None = Header(None, alias="svix-timestamp"),
    svix_signature: str | None = Header(None, alias="svix-signature"),
):
    """Handle incoming identity events from Clerk (User Created, Updated, etc.)."""
    body = await request.body()

    if not service.verify_clerk_signature(body, svix_id, svix_timestamp, svix_signature):
        logger.warning("Invalid Clerk webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        event = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    event_type = event.get("type", "")
    data = event.get("data", {})

    handlers = {
        "user.created": service.handle_user_created,
        "user.updated": service.handle_user_updated,
        "user.deleted": service.handle_user_deleted,
        "session.created": service.handle_session_created,
    }

    handler = handlers.get(event_type)
    if handler:
        await handler(data)
    else:
        logger.info(f"Unhandled Clerk event type: {event_type}")

    return {"status": "ok"}
