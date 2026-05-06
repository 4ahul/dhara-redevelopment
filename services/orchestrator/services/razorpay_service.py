"""Razorpay Service -- order creation, signature verification, webhook processing, subscription lifecycle."""

import hashlib
import hmac
import logging
import uuid
from datetime import UTC, datetime, timedelta

import razorpay
from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.core.config import settings
from services.orchestrator.models.subscription import (
    PLANS, Payment, PaymentStatus, Subscription, SubscriptionStatus, WebhookEvent,
)

logger = logging.getLogger(__name__)


def _get_razorpay_client() -> razorpay.Client:
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise HTTPException(500, "Razorpay credentials not configured")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class RazorpayService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = _get_razorpay_client()

    async def create_checkout(self, user, plan_id: str) -> dict:
        plan = PLANS.get(plan_id)
        if not plan:
            raise HTTPException(400, f"Invalid plan_id: {plan_id}. Must be one of: {', '.join(PLANS.keys())}")
        receipt = f"rcpt_{user.id}_{uuid.uuid4().hex[:8]}"
        try:
            order = self.client.order.create({
                "amount": plan["amount_paise"], "currency": plan["currency"], "receipt": receipt,
                "notes": {"user_id": str(user.id), "user_email": user.email, "plan_id": plan_id, "plan_name": plan["name"]},
            })
        except Exception as e:
            logger.error("Razorpay order creation failed: %s", e)
            raise HTTPException(502, f"Payment gateway error: {e}")
        payment = Payment(
            id=uuid.uuid4(), user_id=user.id, razorpay_order_id=order["id"],
            amount_paise=plan["amount_paise"], currency=plan["currency"],
            status=PaymentStatus.CREATED, receipt=receipt, plan_id=plan_id, description=plan["description"],
        )
        self.db.add(payment)
        await self.db.flush()
        return {
            "order_id": order["id"], "amount": plan["amount_paise"], "currency": plan["currency"],
            "key_id": settings.RAZORPAY_KEY_ID, "plan_id": plan_id, "plan_name": plan["name"],
            "receipt": receipt, "prefill": {"name": user.name, "email": user.email, "contact": user.phone or ""},
        }

    async def verify_payment(self, user, razorpay_payment_id: str, razorpay_order_id: str, razorpay_signature: str) -> dict:
        result = await self.db.execute(select(Payment).where(Payment.razorpay_order_id == razorpay_order_id, Payment.user_id == user.id))
        payment = result.scalar_one_or_none()
        if not payment:
            raise HTTPException(404, "Payment order not found")
        if payment.status == PaymentStatus.CAPTURED:
            raise HTTPException(409, "Payment already verified")
        body = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, razorpay_signature):
            payment.status = PaymentStatus.FAILED
            payment.error_code = "SIGNATURE_MISMATCH"
            await self.db.flush()
            raise HTTPException(400, "Payment signature verification failed")
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.status = PaymentStatus.CAPTURED
        try:
            rp = self.client.payment.fetch(razorpay_payment_id)
            payment.method = rp.get("method")
        except Exception:
            pass
        sub = await self._activate_subscription(user, payment)
        payment.subscription_id = sub.id
        await self.db.flush()
        await self.db.refresh(sub)
        return {
            "success": True, "message": "Payment verified and subscription activated",
            "subscription": {"active": sub.status == SubscriptionStatus.ACTIVE, "plan_id": sub.plan_id,
                "plan_name": PLANS.get(sub.plan_id, {}).get("name"), "current_period_end": sub.current_period_end,
                "current_period_start": sub.current_period_start, "status": sub.status.value},
        }

    async def get_subscription_status(self, user) -> dict:
        result = await self.db.execute(select(Subscription).where(Subscription.user_id == user.id).order_by(desc(Subscription.created_at)).limit(1))
        sub = result.scalar_one_or_none()
        if not sub:
            return {"active": False, "plan_id": None, "current_period_end": None}
        now = datetime.now(UTC).replace(tzinfo=None)
        if sub.status == SubscriptionStatus.ACTIVE and sub.current_period_end and sub.current_period_end < now:
            sub.status = SubscriptionStatus.EXPIRED
            await self.db.flush()
        plan = PLANS.get(sub.plan_id, {})
        return {"active": sub.status == SubscriptionStatus.ACTIVE, "plan_id": sub.plan_id, "plan_name": plan.get("name"),
            "current_period_end": sub.current_period_end, "current_period_start": sub.current_period_start, "status": sub.status.value}

    async def get_payment_history(self, user, page: int = 1, page_size: int = 20) -> list:
        result = await self.db.execute(select(Payment).where(Payment.user_id == user.id).order_by(desc(Payment.created_at)).offset((page - 1) * page_size).limit(page_size))
        return list(result.scalars().all())

    async def process_webhook(self, event_id: str, event_type: str, payload: dict) -> dict:
        existing = await self.db.execute(select(WebhookEvent).where(WebhookEvent.razorpay_event_id == event_id))
        if existing.scalar_one_or_none():
            return {"status": "already_processed"}
        webhook = WebhookEvent(id=uuid.uuid4(), razorpay_event_id=event_id, event_type=event_type, payload=payload, processed=False)
        self.db.add(webhook)
        try:
            if event_type in ("payment.captured", "order.paid"):
                await self._handle_payment_captured(payload)
            elif event_type == "payment.failed":
                await self._handle_payment_failed(payload)
            webhook.processed = True
        except Exception as e:
            webhook.processing_error = str(e)
        await self.db.flush()
        return {"status": "processed" if webhook.processed else "error"}

    async def _activate_subscription(self, user, payment: Payment) -> Subscription:
        plan = PLANS.get(payment.plan_id, {})
        now = datetime.now(UTC).replace(tzinfo=None)
        result = await self.db.execute(select(Subscription).where(Subscription.user_id == user.id, Subscription.status == SubscriptionStatus.ACTIVE))
        existing = result.scalar_one_or_none()
        if existing and existing.current_period_end and existing.current_period_end > now:
            existing.current_period_end += timedelta(days=plan.get("period_days", 30))
            existing.plan_id = payment.plan_id
            return existing
        sub = Subscription(id=uuid.uuid4(), user_id=user.id, plan_id=payment.plan_id, status=SubscriptionStatus.ACTIVE,
            amount_paise=payment.amount_paise, currency=payment.currency,
            current_period_start=now, current_period_end=now + timedelta(days=plan.get("period_days", 30)))
        self.db.add(sub)
        return sub

    async def _handle_payment_captured(self, payload: dict):
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = entity.get("order_id")
        if not order_id:
            return
        result = await self.db.execute(select(Payment).where(Payment.razorpay_order_id == order_id))
        payment = result.scalar_one_or_none()
        if not payment or payment.status == PaymentStatus.CAPTURED:
            return
        payment.razorpay_payment_id = entity.get("id")
        payment.status = PaymentStatus.CAPTURED
        payment.method = entity.get("method")
        from services.orchestrator.models.user import User
        user = (await self.db.execute(select(User).where(User.id == payment.user_id))).scalar_one_or_none()
        if user:
            sub = await self._activate_subscription(user, payment)
            payment.subscription_id = sub.id

    async def _handle_payment_failed(self, payload: dict):
        entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = entity.get("order_id")
        if not order_id:
            return
        result = await self.db.execute(select(Payment).where(Payment.razorpay_order_id == order_id))
        payment = result.scalar_one_or_none()
        if payment and payment.status != PaymentStatus.CAPTURED:
            payment.status = PaymentStatus.FAILED
            payment.error_code = entity.get("error_code")
            payment.error_description = entity.get("error_description")


def verify_webhook_signature(body: bytes, signature: str) -> bool:
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return True
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
