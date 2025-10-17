"""
Subscription management endpoints.

Provides API endpoints for managing user subscriptions, payment methods,
and subscription status.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator
import re

from app.db.database import get_db
from app.db.models import User, Subscription, PaymentAuditLog
from app.api.deps import get_current_user, get_current_user_optional, get_subscription_status
from app.services.subscription_service import SubscriptionService
from sqlalchemy import select

router = APIRouter()


class CheckoutSessionRequest(BaseModel):
    """Request model for creating checkout session."""
    plan_id: str = Field(default="premium", pattern="^(free|premium)$", description="Subscription plan ID")

    @validator("plan_id")
    def validate_plan_id(cls, v):
        if v not in ["free", "premium"]:
            raise ValueError("Invalid plan_id. Must be 'free' or 'premium'")
        return v


class UpdatePaymentMethodRequest(BaseModel):
    """Request model for updating payment method."""
    payment_method_id: str = Field(..., min_length=20, max_length=100, description="Stripe payment method ID")

    @validator("payment_method_id")
    def validate_payment_method_id(cls, v):
        # Basic validation for Stripe payment method ID format (pm_...)
        if not re.match(r'^pm_[a-zA-Z0-9]+$', v):
            raise ValueError("Invalid payment method ID format")
        return v


@router.post("/checkout-session")
async def create_checkout_session(
    request_body: CheckoutSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a Stripe checkout session for subscription.

    Args:
        plan_id: Subscription plan ID (default: premium)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Checkout session details including URL
    """
    # Get user ID from email
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user already has active subscription
    if user.subscription_tier == "premium":
        existing = await get_subscription_status(current_user, db)
        if existing and existing.status in ["active", "trialing"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an active subscription"
            )

    service = SubscriptionService()
    return await service.create_checkout_session(db, user.id, request_body.plan_id)


@router.get("/status")
async def get_subscription_status_endpoint(
    current_user: Optional[UserLogin] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get current user's subscription status.

    This endpoint supports both authenticated and unauthenticated requests.
    Unauthenticated users receive the default free tier status.

    Args:
        current_user: Current authenticated user (optional)
        db: Database session

    Returns:
        Subscription status details
    """
    # If user is not authenticated, return free tier status
    if not current_user:
        return {
            "status": "no_subscription",
            "tier": "free",
            "features": {
                "prospects_limit": 100,
                "export_enabled": False,
                "advanced_filters_enabled": False,
                "comparison_enabled": False
            }
        }

    # First, check the user's subscription_tier from the database
    # This handles manually-granted premium access (e.g., admin users)
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user_db = result.scalar_one_or_none()

    if user_db and user_db.subscription_tier == "premium":
        # User has premium tier set in database (manual grant or active subscription)
        return {
            "status": "active",
            "tier": "premium",
            "is_admin": user_db.is_admin,
            "features": {
                "prospects_limit": 500,
                "export_enabled": True,
                "advanced_filters_enabled": True,
                "comparison_enabled": True
            }
        }

    # Check Stripe subscription status for regular subscribers
    subscription = await get_subscription_status(current_user, db)

    if not subscription:
        return {
            "status": "no_subscription",
            "tier": "free",
            "features": {
                "prospects_limit": 100,
                "export_enabled": False,
                "advanced_filters_enabled": False,
                "comparison_enabled": False
            }
        }

    return {
        "status": subscription.status,
        "tier": "premium" if subscription.status in ["active", "trialing"] else "free",
        "plan_id": subscription.plan_id,
        "current_period_start": subscription.current_period_start.isoformat(),
        "current_period_end": subscription.current_period_end.isoformat(),
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "features": {
            "prospects_limit": 500 if subscription.status in ["active", "trialing"] else 100,
            "export_enabled": subscription.status in ["active", "trialing"],
            "advanced_filters_enabled": subscription.status in ["active", "trialing"],
            "comparison_enabled": subscription.status in ["active", "trialing"]
        }
    }


@router.post("/cancel")
async def cancel_subscription(
    immediate: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Cancel user's subscription.

    Args:
        immediate: Cancel immediately vs at period end (default: False)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated subscription details
    """
    # Get user ID from email
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    service = SubscriptionService()
    subscription = await service.cancel_subscription(db, user.id, immediate)

    return {
        "status": subscription.status,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "current_period_end": subscription.current_period_end.isoformat(),
        "message": "Subscription will be canceled at the end of the billing period" if not immediate else "Subscription canceled immediately"
    }


@router.post("/reactivate")
async def reactivate_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reactivate a canceled subscription (undo cancellation).

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated subscription details
    """
    # Get user ID from email
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    service = SubscriptionService()
    subscription = await service.reactivate_subscription(db, user.id)

    return {
        "status": subscription.status,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "current_period_end": subscription.current_period_end.isoformat(),
        "message": "Subscription reactivated successfully"
    }


@router.put("/payment-method")
async def update_payment_method(
    request_body: UpdatePaymentMethodRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update user's payment method with PCI-compliant audit logging.

    Args:
        request_body: Payment method update request
        request: FastAPI request object for IP/user agent
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated payment method details
    """
    # Get user ID from email
    stmt = select(User).where(User.email == current_user.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Create PCI-compliant audit log entry
    audit_log = PaymentAuditLog(
        user_id=user.id,
        action="update_attempt",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent", "")[:512],
        success=False  # Will update after successful operation
    )
    db.add(audit_log)

    try:
        service = SubscriptionService()
        payment_method = await service.update_payment_method(db, user.id, request_body.payment_method_id)

        # Update audit log with success
        audit_log.success = True
        audit_log.action = "updated"
        audit_log.payment_method_last4 = payment_method.last4
        audit_log.card_brand = payment_method.card_brand

        await db.commit()

        return {
            "card_brand": payment_method.card_brand,
            "last4": payment_method.last4,
            "exp_month": payment_method.exp_month,
            "exp_year": payment_method.exp_year,
            "is_default": payment_method.is_default,
            "message": "Payment method updated successfully"
        }
    except Exception as e:
        # Update audit log with failure
        audit_log.failure_reason = str(e)[:255]
        await db.commit()
        raise