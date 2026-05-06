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


# ── Razorpay Webhook ─────────────────────────────────────────────────────────

@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Razorpay payment events. No auth — verified via HMAC signature."""
    import json as _json
    from services.orchestrator.services.razorpay_service import RazorpayService, verify_webhook_signature

    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = _json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_id = payload.get("event_id", payload.get("id", "unknown"))
    event_type = payload.get("event", "unknown")
    logger.info("Razorpay webhook: event=%s id=%s", event_type, event_id)

    svc = RazorpayService(db)
    result = await svc.process_webhook(event_id, event_type, payload)
    await db.commit()
    return {"status": "ok", **result}
