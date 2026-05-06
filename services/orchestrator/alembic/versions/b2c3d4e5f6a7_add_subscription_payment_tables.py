"""add_subscription_payment_tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-06
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '20260507000001'
branch_labels = None
depends_on = ["a1b2c3d4e5f6", "fd819f308a81"]


def upgrade() -> None:
    sub_status = sa.Enum('active', 'cancelled', 'expired', 'past_due', 'trialing', 'created', name='subscription_status')
    sub_status.create(op.get_bind(), checkfirst=True)
    pay_status = sa.Enum('created', 'authorized', 'captured', 'failed', 'refunded', name='payment_status')
    pay_status.create(op.get_bind(), checkfirst=True)

    op.create_table('subscriptions',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_id', sa.String(50), nullable=False),
        sa.Column('status', sub_status, nullable=False, server_default='created'),
        sa.Column('razorpay_subscription_id', sa.String(100), nullable=True, unique=True),
        sa.Column('razorpay_customer_id', sa.String(100), nullable=True),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancel_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_subscriptions_user', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])

    op.create_table('payments',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subscription_id', sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey('subscriptions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('razorpay_order_id', sa.String(100), nullable=False, unique=True),
        sa.Column('razorpay_payment_id', sa.String(100), nullable=True, unique=True),
        sa.Column('razorpay_signature', sa.String(255), nullable=True),
        sa.Column('amount_paise', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('status', pay_status, nullable=False, server_default='created'),
        sa.Column('method', sa.String(50), nullable=True),
        sa.Column('receipt', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('plan_id', sa.String(50), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_payments_user', 'payments', ['user_id'])
    op.create_index('ix_payments_order', 'payments', ['razorpay_order_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])

    op.create_table('webhook_events',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('razorpay_event_id', sa.String(100), nullable=False, unique=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processing_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_webhook_event_type', 'webhook_events', ['event_type'])
    op.create_index('ix_webhook_processed', 'webhook_events', ['processed'])


def downgrade() -> None:
    op.drop_table('webhook_events')
    op.drop_table('payments')
    op.drop_table('subscriptions')
    sa.Enum(name='payment_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='subscription_status').drop(op.get_bind(), checkfirst=True)
