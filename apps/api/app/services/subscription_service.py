"""
Subscription management service for handling Stripe subscriptions.

This service provides methods for creating, updating, and managing
user subscriptions integrated with Stripe.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json
import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.db.models import User, Subscription, PaymentMethod, Invoice, SubscriptionEvent, PaymentAuditLog
from app.core.config import settings
from app.core.rate_limiter import get_redis_client

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Cache TTL for subscription status
SUBSCRIPTION_STATUS_TTL = 900  # 15 minutes


class SubscriptionService:
    """Service for managing user subscriptions with Stripe integration."""

    async def create_checkout_session(
        self, db: AsyncSession, user_id: int, plan_id: str = "premium"
    ) -> Dict[str, Any]:
        """
        Create a Stripe checkout session for subscription.

        Args:
            db: Database session
            user_id: User ID
            plan_id: Subscription plan ID (default: premium)

        Returns:
            Checkout session details including URL

        Raises:
            HTTPException: If user not found or Stripe error
        """
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Ensure user has Stripe customer ID
        if not user.stripe_customer_id:
            try:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=user.full_name,
                    metadata={
                        "user_id": str(user_id),
                        "platform": "afinewinedynasty"
                    }
                )
                user.stripe_customer_id = customer.id
                await db.commit()
            except stripe.error.StripeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create Stripe customer: {str(e)}"
                )

        # Create checkout session
        try:
            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=["card"],
                mode="subscription",
                line_items=[{
                    "price": settings.STRIPE_PREMIUM_PRICE_ID,
                    "quantity": 1
                }],
                success_url=settings.STRIPE_SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=settings.STRIPE_CANCEL_URL,
                metadata={
                    "user_id": str(user_id),
                    "plan_id": plan_id
                }
            )

            return {
                "checkout_url": session.url,
                "session_id": session.id,
                "customer_id": user.stripe_customer_id
            }

        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create checkout session: {str(e)}"
            )

    async def sync_subscription_from_stripe(
        self, db: AsyncSession, stripe_subscription_id: str
    ) -> Subscription:
        """
        Sync subscription data from Stripe to database with proper transaction boundaries.

        Uses SELECT FOR UPDATE to prevent race conditions and ensures idempotency.

        Args:
            db: Database session
            stripe_subscription_id: Stripe subscription ID

        Returns:
            Updated subscription record

        Raises:
            HTTPException: If subscription not found in Stripe
        """
        try:
            # Fetch subscription from Stripe first (before any DB operations)
            stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)

            # Start transaction with proper isolation
            async with db.begin():
                # Find user by Stripe customer ID with lock to prevent concurrent updates
                stmt = select(User).where(
                    User.stripe_customer_id == stripe_sub.customer
                ).with_for_update()
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found for Stripe customer"
                    )

                # Check if subscription exists with lock
                stmt = select(Subscription).where(
                    Subscription.stripe_subscription_id == stripe_subscription_id
                ).with_for_update()
                result = await db.execute(stmt)
                subscription = result.scalar_one_or_none()

                if subscription:
                    # Update existing subscription
                    subscription.status = stripe_sub.status
                    subscription.current_period_start = datetime.fromtimestamp(
                        stripe_sub.current_period_start
                    )
                    subscription.current_period_end = datetime.fromtimestamp(
                        stripe_sub.current_period_end
                    )
                    subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
                    subscription.canceled_at = (
                        datetime.fromtimestamp(stripe_sub.canceled_at)
                        if stripe_sub.canceled_at else None
                    )
                    subscription.updated_at = datetime.now()
                else:
                    # Create new subscription
                    subscription = Subscription(
                        user_id=user.id,
                        stripe_subscription_id=stripe_subscription_id,
                        stripe_customer_id=stripe_sub.customer,
                        status=stripe_sub.status,
                        plan_id="premium",  # Default to premium for paid subscriptions
                        current_period_start=datetime.fromtimestamp(
                            stripe_sub.current_period_start
                        ),
                        current_period_end=datetime.fromtimestamp(
                            stripe_sub.current_period_end
                        ),
                        cancel_at_period_end=stripe_sub.cancel_at_period_end,
                        canceled_at=(
                            datetime.fromtimestamp(stripe_sub.canceled_at)
                            if stripe_sub.canceled_at else None
                        )
                    )
                    db.add(subscription)

                # Update user subscription tier
                if stripe_sub.status in ["active", "trialing"]:
                    user.subscription_tier = "premium"
                else:
                    user.subscription_tier = "free"

                # Commit happens automatically at end of context manager

            # Refresh subscription after commit
            await db.refresh(subscription)

            # Invalidate cache after successful commit
            await self._invalidate_subscription_cache(user.id)

            return subscription

        except IntegrityError:
            # Handle race condition where subscription was created concurrently
            await db.rollback()
            # Try to fetch the existing subscription
            stmt = select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
            result = await db.execute(stmt)
            subscription = result.scalar_one_or_none()
            if subscription:
                return subscription
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Concurrent subscription creation detected"
            )
        except stripe.error.StripeError as e:
            await db.rollback()
            # Sanitize error message to not leak Stripe account info
            error_msg = "Failed to sync subscription from Stripe"
            if isinstance(e, stripe.error.RateLimitError):
                error_msg = "Rate limit exceeded, please try again later"
            elif isinstance(e, stripe.error.InvalidRequestError):
                error_msg = "Invalid subscription data"
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

    async def cancel_subscription(
        self, db: AsyncSession, user_id: int, immediate: bool = False
    ) -> Subscription:
        """
        Cancel user subscription.

        Args:
            db: Database session
            user_id: User ID
            immediate: Cancel immediately vs at period end

        Returns:
            Updated subscription record

        Raises:
            HTTPException: If subscription not found or Stripe error
        """
        # Get subscription
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )

        try:
            # Cancel in Stripe
            if immediate:
                stripe_sub = stripe.Subscription.delete(
                    subscription.stripe_subscription_id
                )
            else:
                stripe_sub = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )

            # Update local record
            subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
            subscription.canceled_at = datetime.now()
            if immediate:
                subscription.status = "canceled"

            # Create event record
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="canceled" if immediate else "cancel_scheduled",
                metadata={
                    "immediate": immediate,
                    "user_initiated": True
                }
            )
            db.add(event)

            await db.commit()
            await db.refresh(subscription)

            # Invalidate cache
            await self._invalidate_subscription_cache(user_id)

            return subscription

        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to cancel subscription: {str(e)}"
            )

    async def reactivate_subscription(
        self, db: AsyncSession, user_id: int
    ) -> Subscription:
        """
        Reactivate a canceled subscription (undo cancellation).

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Updated subscription record

        Raises:
            HTTPException: If subscription not found or cannot be reactivated
        """
        # Get subscription
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No subscription found"
            )

        if not subscription.cancel_at_period_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription is not scheduled for cancellation"
            )

        try:
            # Reactivate in Stripe
            stripe_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )

            # Update local record
            subscription.cancel_at_period_end = False
            subscription.canceled_at = None

            # Create event record
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="reactivated",
                metadata={"user_initiated": True}
            )
            db.add(event)

            await db.commit()
            await db.refresh(subscription)

            # Invalidate cache
            await self._invalidate_subscription_cache(user_id)

            return subscription

        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to reactivate subscription: {str(e)}"
            )

    async def get_subscription_status(
        self, db: AsyncSession, user_id: int
    ) -> Optional[Subscription]:
        """
        Get current subscription status for user with caching.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Subscription record or None if no subscription
        """
        # Check Redis cache first
        redis = await get_redis_client()
        cache_key = f"subscription:status:{user_id}"

        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    # Deserialize cached subscription data
                    cached_data = json.loads(cached)
                    # Return cached subscription data (create object from cached data)
                    stmt = select(Subscription).where(Subscription.id == cached_data['id'])
                    result = await db.execute(stmt)
                    subscription = result.scalar_one_or_none()
                    if subscription:
                        return subscription
            except Exception as e:
                # Log cache error but continue with database query
                print(f"Cache retrieval error: {e}")

        # Query database
        stmt = select(Subscription).where(Subscription.user_id == user_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        # Cache result if Redis available
        if redis and subscription:
            try:
                # Serialize subscription data for caching
                cache_data = {
                    'id': subscription.id,
                    'user_id': subscription.user_id,
                    'status': subscription.status,
                    'plan_id': subscription.plan_id,
                    'cancel_at_period_end': subscription.cancel_at_period_end,
                    'current_period_end': subscription.current_period_end.isoformat()
                }
                await redis.setex(cache_key, SUBSCRIPTION_STATUS_TTL, json.dumps(cache_data))
            except Exception as e:
                # Log cache error but don't fail the request
                print(f"Cache storage error: {e}")

        return subscription

    async def update_payment_method(
        self, db: AsyncSession, user_id: int, payment_method_id: str
    ) -> PaymentMethod:
        """
        Update user's default payment method.

        Args:
            db: Database session
            user_id: User ID
            payment_method_id: Stripe payment method ID

        Returns:
            Updated payment method record

        Raises:
            HTTPException: If user or payment method not found
        """
        # Get user
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User or Stripe customer not found"
            )

        try:
            # Attach payment method to customer in Stripe
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=user.stripe_customer_id
            )

            # Set as default payment method
            stripe.Customer.modify(
                user.stripe_customer_id,
                invoice_settings={"default_payment_method": payment_method_id}
            )

            # Get payment method details
            pm = stripe.PaymentMethod.retrieve(payment_method_id)

            # Update local database
            # First, unset any existing default
            stmt = select(PaymentMethod).where(
                PaymentMethod.user_id == user_id,
                PaymentMethod.is_default == True
            )
            result = await db.execute(stmt)
            existing_defaults = result.scalars().all()
            for existing in existing_defaults:
                existing.is_default = False

            # Check if payment method exists
            stmt = select(PaymentMethod).where(
                PaymentMethod.stripe_payment_method_id == payment_method_id
            )
            result = await db.execute(stmt)
            payment_method = result.scalar_one_or_none()

            if not payment_method:
                # Create new payment method record
                payment_method = PaymentMethod(
                    user_id=user_id,
                    stripe_payment_method_id=payment_method_id,
                    card_brand=pm.card.brand,
                    last4=pm.card.last4,
                    exp_month=pm.card.exp_month,
                    exp_year=pm.card.exp_year,
                    is_default=True
                )
                db.add(payment_method)
            else:
                payment_method.is_default = True

            await db.commit()
            await db.refresh(payment_method)

            return payment_method

        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update payment method: {str(e)}"
            )

    # Webhook handlers
    async def handle_subscription_created(
        self, db: AsyncSession, stripe_subscription: dict, event_id: str
    ):
        """Handle subscription.created webhook event."""
        await self.sync_subscription_from_stripe(db, stripe_subscription["id"])

        # Log event
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription["id"]
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="created",
                stripe_event_id=event_id,
                metadata={"status": stripe_subscription["status"]}
            )
            db.add(event)
            await db.commit()

    async def handle_subscription_updated(
        self, db: AsyncSession, stripe_subscription: dict, event_id: str
    ):
        """Handle subscription.updated webhook event."""
        await self.sync_subscription_from_stripe(db, stripe_subscription["id"])

        # Log event
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription["id"]
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="updated",
                stripe_event_id=event_id,
                metadata={
                    "status": stripe_subscription["status"],
                    "cancel_at_period_end": stripe_subscription.get("cancel_at_period_end")
                }
            )
            db.add(event)
            await db.commit()

    async def handle_subscription_deleted(
        self, db: AsyncSession, stripe_subscription: dict, event_id: str
    ):
        """Handle subscription.deleted webhook event."""
        # Update subscription status
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription["id"]
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.status = "canceled"
            subscription.updated_at = datetime.now()

            # Update user tier
            stmt = select(User).where(User.id == subscription.user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.subscription_tier = "free"

            # Log event
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="deleted",
                stripe_event_id=event_id,
                metadata={"final_status": "canceled"}
            )
            db.add(event)
            await db.commit()

            # Invalidate cache
            await self._invalidate_subscription_cache(subscription.user_id)

    async def handle_payment_succeeded(
        self, db: AsyncSession, invoice: dict, event_id: str
    ):
        """Handle invoice.payment_succeeded webhook event."""
        # Find subscription
        if not invoice.get("subscription"):
            return

        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == invoice["subscription"]
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            # Create invoice record
            invoice_record = Invoice(
                user_id=subscription.user_id,
                stripe_invoice_id=invoice["id"],
                subscription_id=subscription.id,
                amount_paid=invoice["amount_paid"],
                status="paid",
                billing_reason=invoice.get("billing_reason", "subscription_cycle"),
                invoice_pdf=invoice.get("invoice_pdf")
            )
            db.add(invoice_record)

            # Log event
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="payment_succeeded",
                stripe_event_id=event_id,
                metadata={
                    "amount": invoice["amount_paid"],
                    "currency": invoice["currency"]
                }
            )
            db.add(event)
            await db.commit()

    async def handle_trial_ending(
        self, db: AsyncSession, stripe_subscription: dict, event_id: str
    ):
        """Handle subscription.trial_will_end webhook event."""
        # This would trigger email notifications in production
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == stripe_subscription["id"]
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="trial_ending",
                stripe_event_id=event_id,
                metadata={
                    "trial_end": stripe_subscription.get("trial_end")
                }
            )
            db.add(event)
            await db.commit()

    async def _invalidate_subscription_cache(self, user_id: int):
        """Invalidate subscription cache for a user."""
        redis = await get_redis_client()
        if redis:
            cache_key = f"subscription:status:{user_id}"
            await redis.delete(cache_key)