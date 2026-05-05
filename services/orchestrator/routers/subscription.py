"""Subscription & Payment Routes -- Razorpay Integration

POST /api/subscription/status     -- check subscription status (FE: pmc-subscription-status)
POST /api/subscription/checkout   -- create Razorpay order (FE: pmc-checkout-session)
POST /api/subscription/verify     -- verify payment after checkout
GET  /api/subscription/history    -- payment history
POST /api/webhooks/razorpay       -- Razorpay webhook receiver (NO auth)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.core.dependencies import get_current_user, get_db
from services.orchestrator.logic.razorpay_service import RazorpayService, verify_webhook_signature
from services.orchestrator.schemas.subscription import (
    CheckoutRequest,
    CheckoutResponse,
    PaymentHistoryItem,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    SubscriptionStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Subscription & Payments"])


def get_razorpay_service(db: AsyncSession = Depends(get_db)) -> RazorpayService:
    return RazorpayService(db)


# ── 1. Subscription Status ───────────────────────────────────────────────────

@router.post("/subscription/status")
async def subscription_status(
    user=Depends(get_current_user),
    service: RazorpayService = Depends(get_razorpay_service),
):
    """Check if the PMC user has an active subscription.

    Maps to FE endpoint: POST /api/functions/pmc-subscription-status
    """
    result = await service.get_subscription_status(user)
    return SubscriptionStatusResponse(**result).model_dump(by_alias=True)


# ── 2. Create Checkout Session ───────────────────────────────────────────────

@router.post("/subscription/checkout")
async def create_checkout(
    req: CheckoutRequest,
    user=Depends(get_current_user),
    service: RazorpayService = Depends(get_razorpay_service),
    db: AsyncSession = Depends(get_db),
):
    """Create a Razorpay order and return checkout params for the FE modal.

    Maps to FE endpoint: POST /api/functions/pmc-checkout-session
    """
    result = await service.create_checkout(user, req.plan_id)
    await db.commit()
    return CheckoutResponse(**result).model_dump(by_alias=True)


# ── 3. Verify Payment ───────────────────────────────────────────────────────

@router.post("/subscription/verify")
async def verify_payment(
    req: PaymentVerifyRequest,
    user=Depends(get_current_user),
    service: RazorpayService = Depends(get_razorpay_service),
    db: AsyncSession = Depends(get_db),
):
    """Verify Razorpay signature after user completes payment.

    FE sends razorpayPaymentId, razorpayOrderId, razorpaySignature.
    BE verifies HMAC, activates subscription, returns status.
    """
    result = await service.verify_payment(
        user,
        req.razorpay_payment_id,
        req.razorpay_order_id,
        req.razorpay_signature,
    )
    await db.commit()

    return PaymentVerifyResponse(
        success=result["success"],
        message=result["message"],
        subscription=SubscriptionStatusResponse(**result["subscription"]) if result.get("subscription") else None,
    ).model_dump(by_alias=True)


# ── 4. Payment History ──────────────────────────────────────────────────────

@router.get("/subscription/history")
async def payment_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias='pageSize'),
    user=Depends(get_current_user),
    service: RazorpayService = Depends(get_razorpay_service),
):
    """List past payment records for the authenticated user."""
    payments = await service.get_payment_history(user, page, page_size)
    return [PaymentHistoryItem.model_validate(p).model_dump(by_alias=True) for p in payments]


# ── 5. Razorpay Webhook ─────────────────────────────────────────────────────

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    service: RazorpayService = Depends(get_razorpay_service),
    db: AsyncSession = Depends(get_db),
):
    """Receive and process Razorpay webhook events.

    NO authentication — Razorpay calls this directly.
    Security is via HMAC signature verification using X-Razorpay-Signature header.
    """
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    if not verify_webhook_signature(body, signature):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(400, "Invalid webhook signature")

    import json
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON payload")

    event_id = payload.get("event_id", payload.get("id", "unknown"))
    event_type = payload.get("event", "unknown")

    logger.info("Webhook received: event=%s id=%s", event_type, event_id)

    result = await service.process_webhook(event_id, event_type, payload)
    await db.commit()

    return {"status": "ok", **result}
