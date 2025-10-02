"""
Dunning service for handling payment failures and retry logic.

Manages failed payments, retry attempts, subscription status transitions,
and customer communications for payment recovery.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import stripe
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.db.models import User, Subscription, SubscriptionEvent, Invoice
from app.core.config import settings

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Dunning configuration
RETRY_INTERVALS = [1, 3, 7]  # Days between retry attempts
GRACE_PERIOD_DAYS = 7  # Days before restricting features
MAX_RETRY_ATTEMPTS = 3


class DunningService:
    """Service for managing payment failures and dunning processes."""

    async def handle_payment_failed(
        self, db: AsyncSession, invoice: dict, event_id: str
    ):
        """
        Handle failed payment webhook event.

        Updates subscription status, schedules retries, and triggers notifications.

        Args:
            db: Database session
            invoice: Stripe invoice object from webhook
            event_id: Stripe event ID

        """
        if not invoice.get("subscription"):
            return

        # Find subscription
        stmt = select(Subscription).where(
            Subscription.stripe_subscription_id == invoice["subscription"]
        )
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        # Create failed invoice record
        invoice_record = Invoice(
            user_id=subscription.user_id,
            stripe_invoice_id=invoice["id"],
            subscription_id=subscription.id,
            amount_paid=0,
            status="uncollectible",
            billing_reason=invoice.get("billing_reason", "subscription_cycle"),
            invoice_pdf=invoice.get("invoice_pdf")
        )
        db.add(invoice_record)

        # Update subscription status to past_due
        previous_status = subscription.status
        subscription.status = "past_due"
        subscription.updated_at = datetime.now()

        # Create event record
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="payment_failed",
            stripe_event_id=event_id,
            metadata={
                "invoice_id": invoice["id"],
                "amount": invoice["amount_due"],
                "currency": invoice["currency"],
                "attempt_count": invoice.get("attempt_count", 1),
                "next_payment_attempt": invoice.get("next_payment_attempt"),
                "previous_status": previous_status
            }
        )
        db.add(event)

        # Get user for notifications
        stmt = select(User).where(User.id == subscription.user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Schedule payment retry
            await self._schedule_retry(subscription, invoice, attempt_number=1)

            # Send failure notification email
            await self._send_payment_failed_notification(user, subscription, invoice)

            # Apply grace period
            await self.apply_grace_period(db, subscription.id)

        await db.commit()

    async def retry_payment(
        self, db: AsyncSession, subscription_id: int
    ) -> bool:
        """
        Attempt to retry a failed payment.

        Args:
            db: Database session
            subscription_id: Subscription ID

        Returns:
            True if payment successful, False otherwise
        """
        # Get subscription
        stmt = select(Subscription).where(Subscription.id == subscription_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            return False

        try:
            # Get the latest unpaid invoice
            invoices = stripe.Invoice.list(
                customer=subscription.stripe_customer_id,
                subscription=subscription.stripe_subscription_id,
                status="open",
                limit=1
            )

            if not invoices.data:
                return False

            invoice = invoices.data[0]

            # Attempt to pay the invoice
            paid_invoice = stripe.Invoice.pay(invoice.id)

            if paid_invoice.status == "paid":
                # Update subscription status
                subscription.status = "active"
                subscription.updated_at = datetime.now()

                # Create success event
                event = SubscriptionEvent(
                    subscription_id=subscription.id,
                    event_type="payment_retry_succeeded",
                    metadata={
                        "invoice_id": invoice.id,
                        "amount": invoice.amount_paid,
                        "retry_attempt": invoice.attempt_count
                    }
                )
                db.add(event)

                # Send success notification
                stmt = select(User).where(User.id == subscription.user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                if user:
                    await self._send_payment_success_notification(user, subscription, invoice)

                await db.commit()
                return True

        except stripe.error.CardError as e:
            # Card was declined
            await self._handle_retry_failure(db, subscription, e)
        except stripe.error.StripeError as e:
            # Other Stripe errors
            print(f"Payment retry error: {str(e)}")

        return False

    async def apply_grace_period(
        self, db: AsyncSession, subscription_id: int
    ):
        """
        Apply grace period before restricting features.

        Args:
            db: Database session
            subscription_id: Subscription ID
        """
        # Get subscription
        stmt = select(Subscription).where(Subscription.id == subscription_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        # Calculate grace period end
        grace_period_end = datetime.now() + timedelta(days=GRACE_PERIOD_DAYS)

        # Create event record
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="grace_period_applied",
            metadata={
                "grace_period_end": grace_period_end.isoformat(),
                "days": GRACE_PERIOD_DAYS
            }
        )
        db.add(event)

        await db.commit()

    async def check_and_apply_restrictions(
        self, db: AsyncSession, user_id: int
    ) -> Dict[str, Any]:
        """
        Check if grace period expired and apply restrictions.

        Optimized to avoid N+1 queries by using joins.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Dictionary with restriction status and details
        """
        # Get subscription and user in a single query with join
        stmt = (
            select(Subscription, User)
            .join(User, User.id == Subscription.user_id)
            .where(Subscription.user_id == user_id)
        )
        result = await db.execute(stmt)
        row = result.one_or_none()

        if not row:
            return {"restricted": False, "reason": "no_subscription"}

        subscription, user = row

        if subscription.status != "past_due":
            return {"restricted": False, "reason": "subscription_active"}

        # Check grace period - get the latest grace period event
        stmt = select(SubscriptionEvent).where(
            SubscriptionEvent.subscription_id == subscription.id,
            SubscriptionEvent.event_type == "grace_period_applied"
        ).order_by(SubscriptionEvent.created_at.desc()).limit(1)
        result = await db.execute(stmt)
        grace_event = result.scalar_one_or_none()

        if not grace_event:
            return {"restricted": False, "reason": "no_grace_period"}

        grace_end = datetime.fromisoformat(
            grace_event.metadata.get("grace_period_end")
        )

        if datetime.now() > grace_end:
            # Grace period expired - apply restrictions
            subscription.status = "unpaid"
            if user:
                user.subscription_tier = "free"

            # Create restriction event
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="restrictions_applied",
                metadata={
                    "grace_period_expired": grace_end.isoformat(),
                    "previous_status": "past_due"
                }
            )
            db.add(event)

            await db.commit()

            return {
                "restricted": True,
                "reason": "grace_period_expired",
                "grace_expired_at": grace_end.isoformat()
            }

        return {
            "restricted": False,
            "reason": "in_grace_period",
            "grace_expires_at": grace_end.isoformat()
        }

    async def cancel_unpaid_subscription(
        self, db: AsyncSession, subscription_id: int
    ):
        """
        Cancel subscription after maximum retry attempts.

        Args:
            db: Database session
            subscription_id: Subscription ID
        """
        # Get subscription
        stmt = select(Subscription).where(Subscription.id == subscription_id)
        result = await db.execute(stmt)
        subscription = result.scalar_one_or_none()

        if not subscription:
            return

        try:
            # Cancel subscription in Stripe
            stripe.Subscription.delete(subscription.stripe_subscription_id)

            # Update local record
            subscription.status = "canceled"
            subscription.canceled_at = datetime.now()

            # Update user tier
            stmt = select(User).where(User.id == subscription.user_id)
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                user.subscription_tier = "free"

            # Create cancellation event
            event = SubscriptionEvent(
                subscription_id=subscription.id,
                event_type="canceled_unpaid",
                metadata={
                    "reason": "max_retry_attempts_reached",
                    "attempts": MAX_RETRY_ATTEMPTS
                }
            )
            db.add(event)

            # Send cancellation notification
            if user:
                await self._send_subscription_canceled_notification(
                    user, subscription, reason="unpaid"
                )

            await db.commit()

        except stripe.error.StripeError as e:
            print(f"Error canceling unpaid subscription: {str(e)}")

    # Private helper methods
    async def _schedule_retry(
        self, subscription: Subscription, invoice: dict, attempt_number: int
    ):
        """Schedule payment retry based on attempt number."""
        if attempt_number > MAX_RETRY_ATTEMPTS:
            # Max attempts reached, cancel subscription
            await self.cancel_unpaid_subscription(None, subscription.id)
            return

        # Calculate next retry date
        if attempt_number <= len(RETRY_INTERVALS):
            days_until_retry = RETRY_INTERVALS[attempt_number - 1]
        else:
            days_until_retry = RETRY_INTERVALS[-1]

        next_retry = datetime.now() + timedelta(days=days_until_retry)

        # In production, this would schedule a background job
        # For now, just log the scheduled retry
        print(f"Payment retry scheduled for subscription {subscription.id} at {next_retry}")

    async def _handle_retry_failure(
        self, db: AsyncSession, subscription: Subscription, error: stripe.error.CardError
    ):
        """Handle failed retry attempt."""
        # Create failure event
        event = SubscriptionEvent(
            subscription_id=subscription.id,
            event_type="payment_retry_failed",
            metadata={
                "error_code": error.code,
                "error_message": str(error),
                "decline_code": getattr(error, "decline_code", None)
            }
        )
        db.add(event)
        await db.commit()

    # Email notification methods (placeholders)
    async def _send_payment_failed_notification(
        self, user: User, subscription: Subscription, invoice: dict
    ):
        """Send payment failure notification email."""
        # In production, integrate with email service
        print(f"Payment failed notification for user {user.email}")
        print(f"Amount: ${invoice.get('amount_due', 0) / 100:.2f}")
        print(f"Next retry: {invoice.get('next_payment_attempt')}")

    async def _send_payment_success_notification(
        self, user: User, subscription: Subscription, invoice: dict
    ):
        """Send payment success notification email."""
        # In production, integrate with email service
        print(f"Payment succeeded notification for user {user.email}")
        print(f"Amount: ${invoice.get('amount_paid', 0) / 100:.2f}")

    async def _send_subscription_canceled_notification(
        self, user: User, subscription: Subscription, reason: str
    ):
        """Send subscription cancellation notification email."""
        # In production, integrate with email service
        print(f"Subscription canceled notification for user {user.email}")
        print(f"Reason: {reason}")