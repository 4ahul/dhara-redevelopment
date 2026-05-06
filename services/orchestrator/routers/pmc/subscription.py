"""Subscription & Payment Routes -- Razorpay Integration"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.core.dependencies import get_current_user, get_db
from services.orchestrator.services.razorpay_service import RazorpayService, verify_webhook_signature
from services.orchestrator.schemas.subscription import (
    CheckoutRequest, CheckoutResponse, PaymentHistoryItem,
    PaymentVerifyRequest, PaymentVerifyResponse, SubscriptionStatusResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Subscription & Payments"])


def get_svc(db: AsyncSession = Depends(get_db)) -> RazorpayService:
    return RazorpayService(db)


@router.post("/subscription/status")
async def subscription_status(user=Depends(get_current_user), svc: RazorpayService = Depends(get_svc)):
    return SubscriptionStatusResponse(**(await svc.get_subscription_status(user))).model_dump(by_alias=True)


@router.post("/subscription/checkout")
async def create_checkout(req: CheckoutRequest, user=Depends(get_current_user), svc: RazorpayService = Depends(get_svc), db: AsyncSession = Depends(get_db)):
    result = await svc.create_checkout(user, req.plan_id)
    await db.commit()
    return CheckoutResponse(**result).model_dump(by_alias=True)


@router.post("/subscription/verify")
async def verify_payment(req: PaymentVerifyRequest, user=Depends(get_current_user), svc: RazorpayService = Depends(get_svc), db: AsyncSession = Depends(get_db)):
    result = await svc.verify_payment(user, req.razorpay_payment_id, req.razorpay_order_id, req.razorpay_signature)
    await db.commit()
    return PaymentVerifyResponse(
        success=result["success"], message=result["message"],
        subscription=SubscriptionStatusResponse(**result["subscription"]) if result.get("subscription") else None,
    ).model_dump(by_alias=True)


@router.get("/subscription/history")
async def payment_history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
                          user=Depends(get_current_user), svc: RazorpayService = Depends(get_svc)):
    payments = await svc.get_payment_history(user, page, page_size)
    return [PaymentHistoryItem.model_validate(p).model_dump(by_alias=True) for p in payments]
