"""
Dhara AI -- Subscription & Payment Models
Razorpay integration for PMC subscription billing.
"""

import enum
import uuid
from datetime import datetime

from services.orchestrator.db.base import Base
from services.orchestrator.db.mixins import TimestampMixin, UUIDMixin
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"
    TRIALING = "trialing"
    CREATED = "created"


class PaymentStatus(enum.StrEnum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


# ── Subscription Plans (config, not a table) ────────────────────────────────

PLANS = {
    "growth": {
        "name": "Growth",
        "amount_paise": 999900,       # Rs 9,999
        "currency": "INR",
        "period_days": 30,
        "description": "PMC Growth Plan - up to 10 societies",
    },
    "pro": {
        "name": "Professional",
        "amount_paise": 2499900,      # Rs 24,999
        "currency": "INR",
        "period_days": 30,
        "description": "PMC Professional Plan - up to 50 societies",
    },
    "enterprise": {
        "name": "Enterprise",
        "amount_paise": 4999900,      # Rs 49,999
        "currency": "INR",
        "period_days": 30,
        "description": "PMC Enterprise Plan - unlimited societies",
    },
}


# ── Subscription ─────────────────────────────────────────────────────────────

class Subscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_id: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(SubscriptionStatus, name="subscription_status", create_constraint=True),
        nullable=False, default=SubscriptionStatus.CREATED,
    )
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    razorpay_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user = relationship("User", backref="subscriptions", lazy="selectin")
    payments = relationship("Payment", back_populates="subscription", lazy="selectin")

    __table_args__ = (
        Index("ix_subscriptions_user", "user_id"),
        Index("ix_subscriptions_status", "status"),
    )


# ── Payment ──────────────────────────────────────────────────────────────────

class Payment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    razorpay_order_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    razorpay_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", create_constraint=True),
        nullable=False, default=PaymentStatus.CREATED,
    )
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    receipt: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    user = relationship("User", backref="payments", lazy="selectin")
    subscription = relationship("Subscription", back_populates="payments", lazy="selectin")

    __table_args__ = (
        Index("ix_payments_user", "user_id"),
        Index("ix_payments_order", "razorpay_order_id"),
        Index("ix_payments_status", "status"),
    )


# ── Webhook Events (audit log) ──────────────────────────────────────────────

class WebhookEvent(Base, UUIDMixin):
    __tablename__ = "webhook_events"

    razorpay_event_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.utcnow(), nullable=False
    )

    __table_args__ = (
        Index("ix_webhook_event_type", "event_type"),
        Index("ix_webhook_processed", "processed"),
    )
