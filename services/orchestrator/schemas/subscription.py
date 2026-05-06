"""Subscription & Payment Schemas -- Razorpay integration."""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan_id: str = Field(alias="planId")
    model_config = {"populate_by_name": True}


class CheckoutResponse(BaseModel):
    order_id: str = Field(serialization_alias="orderId")
    amount: int
    currency: str = "INR"
    key_id: str = Field(serialization_alias="keyId")
    plan_id: str = Field(serialization_alias="planId")
    plan_name: str = Field(serialization_alias="planName")
    receipt: str
    prefill: dict
    model_config = {"populate_by_name": True}


class PaymentVerifyRequest(BaseModel):
    razorpay_payment_id: str = Field(alias="razorpayPaymentId")
    razorpay_order_id: str = Field(alias="razorpayOrderId")
    razorpay_signature: str = Field(alias="razorpaySignature")
    model_config = {"populate_by_name": True}


class PaymentVerifyResponse(BaseModel):
    success: bool
    message: str
    subscription: "SubscriptionStatusResponse | None" = None


class SubscriptionStatusResponse(BaseModel):
    active: bool
    plan_id: str | None = Field(default=None, serialization_alias="planId")
    plan_name: str | None = Field(default=None, serialization_alias="planName")
    current_period_end: datetime | None = Field(default=None, serialization_alias="currentPeriodEnd")
    current_period_start: datetime | None = Field(default=None, serialization_alias="currentPeriodStart")
    status: str | None = None
    model_config = {"from_attributes": True, "populate_by_name": True}


class PaymentHistoryItem(BaseModel):
    id: UUID
    razorpay_order_id: str = Field(serialization_alias="razorpayOrderId")
    razorpay_payment_id: str | None = Field(default=None, serialization_alias="razorpayPaymentId")
    amount_paise: int = Field(serialization_alias="amountPaise")
    currency: str
    status: str
    method: str | None = None
    plan_id: str | None = Field(default=None, serialization_alias="planId")
    created_at: datetime = Field(serialization_alias="createdAt")
    model_config = {"from_attributes": True, "populate_by_name": True}
