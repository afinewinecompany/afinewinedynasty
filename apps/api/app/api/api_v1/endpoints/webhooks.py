"""
Stripe webhook endpoints for subscription management.

Handles Stripe webhook events for subscription lifecycle management,
payment processing, and billing events.
"""

from fastapi import APIRouter, Request, HTTPException, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe
import json
import time
from datetime import datetime, timedelta
from app.db.database import get_db
from app.db.models import SubscriptionEvent
from app.core.config import settings
from app.services.subscription_service import SubscriptionService
from app.services.dunning_service import DunningService

router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


async def verify_stripe_signature(
    request: Request,
    stripe_signature: str = Header(None)
) -> dict:
    """
    Verify Stripe webhook signature for security with timestamp validation.

    Args:
        request: FastAPI request object
        stripe_signature: Stripe signature from header

    Returns:
        Verified Stripe event object

    Raises:
        HTTPException: If signature verification fails or timestamp is too old
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        payload = await request.body()

        # Verify signature and construct event
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )

        # Validate timestamp to prevent replay attacks (5 minute tolerance)
        event_timestamp = event.get("created", 0)
        current_timestamp = int(time.time())
        tolerance_seconds = 300  # 5 minutes

        if abs(current_timestamp - event_timestamp) > tolerance_seconds:
            raise HTTPException(
                status_code=400,
                detail="Webhook timestamp outside tolerance window"
            )

        return event
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")


@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: str = Header(None)
):
    """
    Handle Stripe webhook events with idempotency and replay attack prevention.

    Processes various Stripe webhook events related to subscriptions,
    payments, and customer management.

    Args:
        request: FastAPI request object
        db: Database session
        stripe_signature: Stripe signature header

    Returns:
        Success response or error
    """
    # Verify webhook signature and timestamp
    event = await verify_stripe_signature(request, stripe_signature)

    # Check for duplicate event processing (idempotency)
    event_id = event["id"]
    stmt = select(SubscriptionEvent).where(
        SubscriptionEvent.stripe_event_id == event_id
    )
    result = await db.execute(stmt)
    existing_event = result.scalar_one_or_none()

    if existing_event:
        # Event already processed, return success (idempotent)
        return {"status": "success", "event_id": event_id, "duplicate": True}

    # Initialize services
    subscription_service = SubscriptionService()
    dunning_service = DunningService()

    # Process event based on type
    event_type = event["type"]
    event_data = event["data"]["object"]

    try:
        if event_type == "customer.subscription.created":
            # New subscription created
            await subscription_service.handle_subscription_created(
                db, event_data, event["id"]
            )

        elif event_type == "customer.subscription.updated":
            # Subscription updated (plan change, cancellation, etc.)
            await subscription_service.handle_subscription_updated(
                db, event_data, event["id"]
            )

        elif event_type == "customer.subscription.deleted":
            # Subscription fully terminated
            await subscription_service.handle_subscription_deleted(
                db, event_data, event["id"]
            )

        elif event_type == "invoice.payment_succeeded":
            # Successful payment
            await subscription_service.handle_payment_succeeded(
                db, event_data, event["id"]
            )

        elif event_type == "invoice.payment_failed":
            # Failed payment - trigger dunning
            await dunning_service.handle_payment_failed(
                db, event_data, event["id"]
            )

        elif event_type == "customer.subscription.trial_will_end":
            # Trial ending soon (if trials implemented)
            await subscription_service.handle_trial_ending(
                db, event_data, event["id"]
            )

        else:
            # Log unhandled event types for monitoring
            print(f"Unhandled webhook event type: {event_type}")

        await db.commit()

    except Exception as e:
        await db.rollback()
        print(f"Error processing webhook event {event_type}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing webhook")

    return {"status": "success", "event_id": event["id"]}