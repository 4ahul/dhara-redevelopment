"""
        Razorpay Service
Business logic for payment order creation, signature verification,
webhook processing, and subscription lifecycle management.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta

import razorpay
from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.core.config import settings
from services.orchestrator.models.subscription import (
    PLANS,
    Payment,
    PaymentStatus,
    Subscription,
    SubscriptionStatus,
    WebhookEvent,
)

logger = logging.getLogger(__name__)


def _get_razorpay_client() -> razorpay.Client:
    """Create a Razorpay SDK client from config."""
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(500, "Razorpay credentials not configured")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class RazorpayService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = _get_razorpay_client()

    # ── 1. Create Razorpay Order ─────────────────────────────────────────

    async def create_checkout(self, user, plan_id: str) -> dict:
        """Create a Razorpay order and a local Payment record.

        Returns everything the FE needs to open the Razorpay checkout modal.
        """
        plan = PLANS.get(plan_id)
        if not plan:
            raise HTTPException(400, f"Invalid plan_id: {plan_id}. Must be one of: {', '.join(PLANS.keys())}")

        receipt = f"rcpt_{user.id}_{uuid.uuid4().hex[:8]}"

        # Call Razorpay Orders API
        try:
            order = self.client.order.create({
                "amount": plan["amount_paise"],
                "currency": plan["currency"],
                "receipt": receipt,
                "notes": {
                    "user_id": str(user.id),
                    "user_email": user.email,
                    "plan_id": plan_id,
                    "plan_name": plan["name"],
                },
            })
        except Exception as e:
            logger.error("Razorpay order creation failed: %s", e)
            raise HTTPException(502, f"Payment gateway error: {e}")

        razorpay_order_id = order["id"]

        # Save Payment record locally (status=created)
        payment = Payment(
            id=uuid.uuid4(),
            user_id=user.id,
            razorpay_order_id=razorpay_order_id,
            amount_paise=plan["amount_paise"],
            currency=plan["currency"],
            status=PaymentStatus.CREATED,
            receipt=receipt,
            plan_id=plan_id,
            description=plan["description"],
        )
        self.db.add(payment)
        await self.db.flush()

        return {
            "order_id": razorpay_order_id,
            "amount": plan["amount_paise"],
            "currency": plan["currency"],
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan_id": plan_id,
            "plan_name": plan["name"],
            "receipt": receipt,
            "prefill": {
                "name": user.name,
                "email": user.email,
                "contact": user.phone or "",
            },
        }

    # ── 2. Verify Payment Signature ──────────────────────────────────────

    async def verify_payment(
        self,
        user,
        razorpay_payment_id: str,
        razorpay_order_id: str,
        razorpay_signature: str,
    ) -> dict:
        """Verify Razorpay signature, update Payment, activate Subscription."""

        # Find the local Payment record
        result = await self.db.execute(
            select(Payment).where(
                Payment.razorpay_order_id == razorpay_order_id,
                Payment.user_id == user.id,
            )
        )
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment order not found")

        if payment.status == PaymentStatus.CAPTURED:
            raise HTTPException(409, "Payment already verified")

        # Verify HMAC SHA256 signature
        body = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, razorpay_signature):
            payment.status = PaymentStatus.FAILED
            payment.error_code = "SIGNATURE_MISMATCH"
            payment.error_description = "Razorpay signature verification failed"
            await self.db.flush()
            raise HTTPException(400, "Payment signature verification failed")

        # Signature valid — update payment
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.status = PaymentStatus.CAPTURED

        # Fetch payment details from Razorpay for method info
        try:
            rp_payment = self.client.payment.fetch(razorpay_payment_id)
            payment.method = rp_payment.get("method")
        except Exception as e:
            logger.warning("Could not fetch payment details: %s", e)

        # Activate or extend subscription
        subscription = await self._activate_subscription(user, payment)
        payment.subscription_id = subscription.id

        await self.db.flush()
        await self.db.refresh(subscription)

        logger.info(
            "Payment verified: user=%s order=%s payment=%s plan=%s",
            user.id, razorpay_order_id, razorpay_payment_id, payment.plan_id,
        )

        return {
            "success": True,
            "message": "Payment verified and subscription activated",
            "subscription": {
                "active": subscription.status == SubscriptionStatus.ACTIVE,
                "plan_id": subscription.plan_id,
                "plan_name": PLANS.get(subscription.plan_id, {}).get("name"),
                "current_period_end": subscription.current_period_end,
                "current_period_start": subscription.current_period_start,
                "status": subscription.status.value,
            },
        }

    # ── 3. Get Subscription Status ───────────────────────────────────────

    async def get_subscription_status(self, user) -> dict:
        """Check if user has an active subscription."""
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(desc(Subscription.created_at))
            .limit(1)
        )
        sub = result.scalar_one_or_none()

        if not sub:
            return {"active": False, "plan_id": None, "current_period_end": None}

        # Check if expired
        now = datetime.utcnow()
        if sub.status == SubscriptionStatus.ACTIVE and sub.current_period_end and sub.current_period_end < now:
            sub.status = SubscriptionStatus.EXPIRED
            await self.db.flush()

        plan = PLANS.get(sub.plan_id, {})
        return {
            "active": sub.status == SubscriptionStatus.ACTIVE,
            "plan_id": sub.plan_id,
            "plan_name": plan.get("name"),
            "current_period_end": sub.current_period_end,
            "current_period_start": sub.current_period_start,
            "status": sub.status.value,
        }

    # ── 4. Payment History ───────────────────────────────────────────────

    async def get_payment_history(self, user, page: int = 1, page_size: int = 20) -> list:
        """List past payments for a user."""
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(Payment)
            .where(Payment.user_id == user.id)
            .order_by(desc(Payment.created_at))
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all())

    # ── 5. Process Webhook ───────────────────────────────────────────────

    async def process_webhook(self, event_id: str, event_type: str, payload: dict) -> dict:
        """Process a Razorpay webhook event.

        Idempotent — safe to call multiple times for the same event_id.
        """
        # Check if already processed
        existing = await self.db.execute(
            select(WebhookEvent).where(WebhookEvent.razorpay_event_id == event_id)
        )
        if existing.scalar_one_or_none():
            return {"status": "already_processed"}

        # Store the event
        webhook = WebhookEvent(
            id=uuid.uuid4(),
            razorpay_event_id=event_id,
            event_type=event_type,
            payload=payload,
            processed=False,
        )
        self.db.add(webhook)

        try:
            if event_type == "payment.captured":
                await self._handle_payment_captured(payload)
            elif event_type == "order.paid":
                await self._handle_order_paid(payload)
            elif event_type == "payment.failed":
                await self._handle_payment_failed(payload)

            webhook.processed = True
        except Exception as e:
            webhook.processing_error = str(e)
            logger.error("Webhook processing error for %s: %s", event_id, e)

        await self.db.flush()
        return {"status": "processed" if webhook.processed else "error"}

    # ── Private helpers ──────────────────────────────────────────────────

    async def _activate_subscription(self, user, payment: Payment) -> Subscription:
        """Create or extend a subscription after successful payment."""
        plan = PLANS.get(payment.plan_id, {})
        period_days = plan.get("period_days", 30)
        now = datetime.utcnow()

        # Check for existing active subscription to extend
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
        )
        existing = result.scalar_one_or_none()

        if existing and existing.current_period_end and existing.current_period_end > now:
            # Extend from current end date
            existing.current_period_end = existing.current_period_end + timedelta(days=period_days)
            existing.plan_id = payment.plan_id
            existing.amount_paise = payment.amount_paise
            return existing

        # Create new subscription
        sub = Subscription(
            id=uuid.uuid4(),
            user_id=user.id,
            plan_id=payment.plan_id,
            status=SubscriptionStatus.ACTIVE,
            amount_paise=payment.amount_paise,
            currency=payment.currency,
            current_period_start=now,
            current_period_end=now + timedelta(days=period_days),
        )
        self.db.add(sub)
        return sub

    async def _handle_payment_captured(self, payload: dict):
        """Handle payment.captured webhook — activate subscription if not already done."""
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = entity.get("order_id")
        payment_id = entity.get("id")

        if not order_id:
            return

        result = await self.db.execute(
            select(Payment).where(Payment.razorpay_order_id == order_id)
        )
        payment = result.scalar_one_or_none()
        if not payment:
            logger.warning("Webhook: Payment not found for order %s", order_id)
            return

        if payment.status == PaymentStatus.CAPTURED:
            return  # Already processed via verify endpoint

        payment.razorpay_payment_id = payment_id
        payment.status = PaymentStatus.CAPTURED
        payment.method = entity.get("method")

        # Load user for subscription activation
        from services.orchestrator.models.user import User
        user_result = await self.db.execute(
            select(User).where(User.id == payment.user_id)
        )
        user = user_result.scalar_one_or_none()
        if user:
            sub = await self._activate_subscription(user, payment)
            payment.subscription_id = sub.id

    async def _handle_order_paid(self, payload: dict):
        """Handle order.paid webhook — similar to payment.captured."""
        await self._handle_payment_captured(payload)

    async def _handle_payment_failed(self, payload: dict):
        """Handle payment.failed webhook — mark payment as failed."""
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = entity.get("order_id")

        if not order_id:
            return

        result = await self.db.execute(
            select(Payment).where(Payment.razorpay_order_id == order_id)
        )
        payment = result.scalar_one_or_none()
        if payment and payment.status != PaymentStatus.CAPTURED:
            payment.status = PaymentStatus.FAILED
            payment.error_code = entity.get("error_code")
            payment.error_description = entity.get("error_description")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    """Verify Razorpay webhook signature (called from router, not service)."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        logger.warning("RAZORPAY_WEBHOOK_SECRET not configured — skipping verification")
        return True

    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
