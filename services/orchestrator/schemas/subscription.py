"""
Dhara AI -- Subscription & Payment Schemas
Request/Response models for Razorpay payment integration.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Checkout (create order) ──────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    """FE sends planId to start checkout."""
    plan_id: str = Field(alias='planId', description="Plan key: growth, pro, or enterprise")

    model_config = {'populate_by_name': True}


class CheckoutResponse(BaseModel):
    """Returned to FE — everything needed to open Razorpay modal."""
    order_id: str = Field(serialization_alias='orderId')
    amount: int = Field(description="Amount in paise")
    currency: str = Field(default="INR")
    key_id: str = Field(serialization_alias='keyId', description="Razorpay public key for FE")
    plan_id: str = Field(serialization_alias='planId')
    plan_name: str = Field(serialization_alias='planName')
    receipt: str
    prefill: dict = Field(description="{name, email, phone} for Razorpay modal")

    model_config = {'populate_by_name': True}


# ── Verify Payment ───────────────────────────────────────────────────────────

class PaymentVerifyRequest(BaseModel):
    """FE sends these 3 values after Razorpay checkout completes."""
    razorpay_payment_id: str = Field(alias='razorpayPaymentId')
    razorpay_order_id: str = Field(alias='razorpayOrderId')
    razorpay_signature: str = Field(alias='razorpaySignature')

    model_config = {'populate_by_name': True}


class PaymentVerifyResponse(BaseModel):
    """Returned after signature verification."""
    success: bool
    message: str
    subscription: "SubscriptionStatusResponse | None" = None


# ── Subscription Status ──────────────────────────────────────────────────────

class SubscriptionStatusResponse(BaseModel):
    """Maps to what FE expects from pmc-subscription-status."""
    active: bool
    plan_id: str | None = Field(default=None, serialization_alias='planId')
    plan_name: str | None = Field(default=None, serialization_alias='planName')
    current_period_end: datetime | None = Field(default=None, serialization_alias='currentPeriodEnd')
    current_period_start: datetime | None = Field(default=None, serialization_alias='currentPeriodStart')
    status: str | None = None

    model_config = {'from_attributes': True, 'populate_by_name': True}


# ── Payment History ──────────────────────────────────────────────────────────

class PaymentHistoryItem(BaseModel):
    """Single payment in history list."""
    id: UUID
    razorpay_order_id: str = Field(serialization_alias='razorpayOrderId')
    razorpay_payment_id: str | None = Field(default=None, serialization_alias='razorpayPaymentId')
    amount_paise: int = Field(serialization_alias='amountPaise')
    currency: str
    status: str
    method: str | None = None
    plan_id: str | None = Field(default=None, serialization_alias='planId')
    created_at: datetime = Field(serialization_alias='createdAt')

    model_config = {'from_attributes': True, 'populate_by_name': True}


# ── Webhook ──────────────────────────────────────────────────────────────────
# No schema needed — webhook receives raw JSON from Razorpay,
# verified via HMAC signature in the header.
