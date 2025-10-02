from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime, timedelta
import stripe

from app.api import deps
from app.db.database import get_db
from app.services.data_ingestion_service import DataIngestionService
from app.db.models import User, Subscription, SubscriptionEvent, Invoice
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/data-refresh")
async def trigger_manual_data_refresh(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger data refresh for development and testing.
    Requires admin privileges.
    """
    # Check if user has admin privileges (assuming subscription_tier == "admin" indicates admin)
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        ingestion_service = DataIngestionService(db)

        # Execute manual data ingestion
        await ingestion_service.ingest_daily_data()

        logger.info(f"Manual data refresh triggered by user {current_user.id}")

        return {
            "status": "success",
            "message": "Data refresh completed successfully",
            "triggered_by": current_user.email
        }

    except Exception as e:
        logger.error(f"Manual data refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Data refresh failed: {str(e)}"
        )


@router.post("/data-refresh/{prospect_id}")
async def trigger_prospect_data_refresh(
    prospect_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Manually trigger data refresh for a specific prospect.
    Requires admin privileges.
    """
    # Check if user has admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    try:
        ingestion_service = DataIngestionService(db)

        # Execute prospect-specific data refresh
        success = await ingestion_service.refresh_prospect_data(prospect_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prospect {prospect_id} not found or refresh failed"
            )

        logger.info(f"Prospect {prospect_id} data refresh triggered by user {current_user.id}")

        return {
            "status": "success",
            "message": f"Data refresh for prospect {prospect_id} completed successfully",
            "prospect_id": prospect_id,
            "triggered_by": current_user.email
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prospect {prospect_id} data refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prospect data refresh failed: {str(e)}"
        )


# Subscription Admin Endpoints
@router.get("/subscriptions")
async def get_subscription_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Get subscription metrics for admin dashboard.
    Requires admin privileges.

    Returns:
        Subscription metrics including total active, MRR, churn rate
    """
    # Check admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # Get total active subscriptions
    stmt = select(func.count(Subscription.id)).where(
        Subscription.status.in_(["active", "trialing"])
    )
    result = await db.execute(stmt)
    total_active = result.scalar_one()

    # Get total canceled this month
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(Subscription.id)).where(
        Subscription.status == "canceled",
        Subscription.canceled_at >= start_of_month
    )
    result = await db.execute(stmt)
    canceled_this_month = result.scalar_one()

    # Get total revenue (simplified - in production would use Stripe API)
    stmt = select(func.sum(Invoice.amount_paid)).where(
        Invoice.status == "paid",
        Invoice.created_at >= start_of_month
    )
    result = await db.execute(stmt)
    monthly_revenue = result.scalar_one() or 0

    # Calculate MRR (Monthly Recurring Revenue)
    mrr = total_active * 999  # $9.99 per subscription in cents

    # Calculate churn rate
    churn_rate = (canceled_this_month / total_active * 100) if total_active > 0 else 0

    # Get recent subscription events
    stmt = select(SubscriptionEvent).order_by(
        SubscriptionEvent.created_at.desc()
    ).limit(10)
    result = await db.execute(stmt)
    recent_events = result.scalars().all()

    return {
        "metrics": {
            "total_active_subscriptions": total_active,
            "monthly_recurring_revenue": mrr / 100,  # Convert to dollars
            "monthly_revenue": monthly_revenue / 100,  # Convert to dollars
            "churn_rate": round(churn_rate, 2),
            "canceled_this_month": canceled_this_month
        },
        "recent_events": [
            {
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "subscription_id": event.subscription_id
            }
            for event in recent_events
        ]
    }


@router.get("/subscriptions/{user_id}")
async def get_user_subscription_details(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Get specific user subscription details.
    Requires admin privileges.
    """
    # Check admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # Get user
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get subscription
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    # Get invoices
    stmt = select(Invoice).where(Invoice.user_id == user_id).order_by(
        Invoice.created_at.desc()
    ).limit(10)
    result = await db.execute(stmt)
    invoices = result.scalars().all()

    # Get subscription events
    events = []
    if subscription:
        stmt = select(SubscriptionEvent).where(
            SubscriptionEvent.subscription_id == subscription.id
        ).order_by(SubscriptionEvent.created_at.desc()).limit(20)
        result = await db.execute(stmt)
        events = result.scalars().all()

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "subscription_tier": user.subscription_tier,
            "stripe_customer_id": user.stripe_customer_id
        },
        "subscription": {
            "status": subscription.status if subscription else "no_subscription",
            "plan_id": subscription.plan_id if subscription else None,
            "current_period_start": subscription.current_period_start.isoformat() if subscription else None,
            "current_period_end": subscription.current_period_end.isoformat() if subscription else None,
            "cancel_at_period_end": subscription.cancel_at_period_end if subscription else None
        } if subscription else None,
        "invoices": [
            {
                "stripe_invoice_id": invoice.stripe_invoice_id,
                "amount_paid": invoice.amount_paid / 100,  # Convert to dollars
                "status": invoice.status,
                "created_at": invoice.created_at.isoformat()
            }
            for invoice in invoices
        ],
        "events": [
            {
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "metadata": event.metadata
            }
            for event in events
        ]
    }


@router.post("/subscriptions/{user_id}/refund")
async def apply_refund(
    user_id: int,
    amount: Optional[int] = None,
    reason: str = "Customer support request",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Apply refund for customer support.
    Requires admin privileges.

    Args:
        user_id: User ID to refund
        amount: Amount in cents to refund (None for full refund)
        reason: Reason for refund
    """
    # Check admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # Get latest paid invoice
    stmt = select(Invoice).where(
        Invoice.user_id == user_id,
        Invoice.status == "paid"
    ).order_by(Invoice.created_at.desc())
    result = await db.execute(stmt)
    invoice = result.scalar_one_or_none()

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No paid invoice found for user"
        )

    try:
        # Create refund in Stripe
        refund_params = {
            "charge": invoice.stripe_invoice_id,
            "reason": "requested_by_customer",
            "metadata": {
                "admin_user_id": str(current_user.id),
                "reason": reason
            }
        }

        if amount:
            refund_params["amount"] = amount

        refund = stripe.Refund.create(**refund_params)

        # Log the refund event
        if invoice.subscription_id:
            event = SubscriptionEvent(
                subscription_id=invoice.subscription_id,
                event_type="refund_applied",
                metadata={
                    "refund_id": refund.id,
                    "amount": refund.amount,
                    "reason": reason,
                    "admin_user_id": current_user.id
                }
            )
            db.add(event)
            await db.commit()

        return {
            "status": "success",
            "refund_id": refund.id,
            "amount": refund.amount / 100,  # Convert to dollars
            "reason": reason,
            "applied_by": current_user.email
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund failed: {str(e)}"
        )


@router.post("/subscriptions/{user_id}/extend-trial")
async def extend_trial(
    user_id: int,
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Extend trial period for customer retention.
    Requires admin privileges.
    """
    # Check admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # Get subscription
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    result = await db.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for user"
        )

    if subscription.status != "trialing":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription is not in trial period"
        )

    try:
        # Extend trial in Stripe
        new_trial_end = datetime.now() + timedelta(days=days)
        stripe_sub = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            trial_end=int(new_trial_end.timestamp())
        )

        # Update local record
        subscription.current_period_end = new_trial_end

        # Log the event
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="trial_extended",
            metadata={
                "days_extended": days,
                "new_trial_end": new_trial_end.isoformat(),
                "admin_user_id": current_user.id
            }
        )
        db.add(event)
        await db.commit()

        return {
            "status": "success",
            "days_extended": days,
            "new_trial_end": new_trial_end.isoformat(),
            "extended_by": current_user.email
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trial extension failed: {str(e)}"
        )


@router.get("/subscriptions/events")
async def get_subscription_events(
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
) -> Dict[str, Any]:
    """
    Get subscription event audit trail.
    Requires admin privileges.
    """
    # Check admin privileges
    if not current_user.subscription_tier or current_user.subscription_tier != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    # Get total count
    stmt = select(func.count(SubscriptionEvent.id))
    result = await db.execute(stmt)
    total_count = result.scalar_one()

    # Get events with pagination
    stmt = select(SubscriptionEvent).order_by(
        SubscriptionEvent.created_at.desc()
    ).offset(offset).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()

    return {
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": event.id,
                "subscription_id": event.subscription_id,
                "event_type": event.event_type,
                "stripe_event_id": event.stripe_event_id,
                "metadata": event.metadata,
                "created_at": event.created_at.isoformat()
            }
            for event in events
        ]
    }