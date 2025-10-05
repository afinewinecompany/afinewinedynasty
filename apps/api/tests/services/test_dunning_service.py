"""
Test suite for DunningService.

Tests payment failure handling, retry logic, and dunning management.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.dunning_service import DunningService
from app.db.models import User, Subscription, SubscriptionEvent, Invoice


@pytest.fixture
def dunning_service():
    """Create DunningService instance."""
    return DunningService()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    return User(
        id=1,
        email="test@example.com",
        full_name="Test User",
        stripe_customer_id="cus_test123",
        subscription_tier="premium"
    )


@pytest.fixture
def sample_subscription():
    """Create sample subscription for testing."""
    return Subscription(
        id=1,
        user_id=1,
        stripe_subscription_id="sub_test123",
        stripe_customer_id="cus_test123",
        status="active",
        plan_id="premium",
        current_period_start=datetime.now(),
        current_period_end=datetime.now() + timedelta(days=30)
    )


class TestDunningService:
    """Test DunningService methods."""

    @pytest.mark.asyncio
    async def test_handle_payment_failed_creates_invoice(
        self, dunning_service, mock_db, sample_subscription, sample_user
    ):
        """Test handling failed payment creates invoice record."""
        # Setup
        invoice_data = {
            "id": "in_test123",
            "subscription": "sub_test123",
            "amount_due": 999,
            "currency": "usd",
            "billing_reason": "subscription_cycle",
            "invoice_pdf": "https://stripe.com/invoice.pdf",
            "attempt_count": 1,
            "next_payment_attempt": int((datetime.now() + timedelta(days=3)).timestamp())
        }

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_subscription,
            sample_user
        ]

        # Mock private methods
        with patch.object(dunning_service, '_schedule_retry', new_callable=AsyncMock) as mock_retry:
            with patch.object(dunning_service, '_send_payment_failed_notification', new_callable=AsyncMock) as mock_notify:
                with patch.object(dunning_service, 'apply_grace_period', new_callable=AsyncMock) as mock_grace:

                    # Execute
                    await dunning_service.handle_payment_failed(
                        mock_db, invoice_data, "evt_test123"
                    )

                    # Assert
                    assert sample_subscription.status == "past_due"
                    mock_db.add.assert_called()  # Invoice and event added
                    mock_db.commit.assert_called_once()
                    mock_retry.assert_called_once()
                    mock_notify.assert_called_once()
                    mock_grace.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.dunning_service.stripe.Invoice.list')
    @patch('app.services.dunning_service.stripe.Invoice.pay')
    async def test_retry_payment_success(
        self, mock_pay, mock_list, dunning_service, mock_db,
        sample_subscription, sample_user
    ):
        """Test successful payment retry."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_subscription,
            sample_user
        ]

        mock_invoice = Mock(
            id="in_test123",
            amount_paid=999,
            attempt_count=2
        )
        mock_list.return_value = Mock(data=[mock_invoice])
        mock_pay.return_value = Mock(status="paid")

        with patch.object(dunning_service, '_send_payment_success_notification', new_callable=AsyncMock) as mock_notify:

            # Execute
            result = await dunning_service.retry_payment(mock_db, subscription_id=1)

            # Assert
            assert result == True
            assert sample_subscription.status == "active"
            mock_db.add.assert_called()  # Event added
            mock_db.commit.assert_called_once()
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.dunning_service.stripe.Invoice.list')
    @patch('app.services.dunning_service.stripe.Invoice.pay')
    async def test_retry_payment_failure(
        self, mock_pay, mock_list, dunning_service, mock_db, sample_subscription
    ):
        """Test failed payment retry."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        mock_invoice = Mock(id="in_test123")
        mock_list.return_value = Mock(data=[mock_invoice])

        # Simulate card error
        import stripe
        mock_pay.side_effect = stripe.CardError(
            message="Card declined",
            param="payment_method",
            code="card_declined"
        )

        with patch.object(dunning_service, '_handle_retry_failure', new_callable=AsyncMock) as mock_handle_failure:

            # Execute
            result = await dunning_service.retry_payment(mock_db, subscription_id=1)

            # Assert
            assert result == False
            mock_handle_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_grace_period(
        self, dunning_service, mock_db, sample_subscription
    ):
        """Test applying grace period to subscription."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        # Execute
        await dunning_service.apply_grace_period(mock_db, subscription_id=1)

        # Assert
        mock_db.add.assert_called_once()  # Event added
        mock_db.commit.assert_called_once()

        # Check event metadata
        call_args = mock_db.add.call_args[0][0]
        assert isinstance(call_args, SubscriptionEvent)
        assert call_args.event_type == "grace_period_applied"
        assert "grace_period_end" in call_args.metadata
        assert call_args.metadata["days"] == 7

    @pytest.mark.asyncio
    async def test_check_and_apply_restrictions_no_subscription(
        self, dunning_service, mock_db
    ):
        """Test restriction check with no subscription."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        # Execute
        result = await dunning_service.check_and_apply_restrictions(
            mock_db, user_id=1
        )

        # Assert
        assert result["restricted"] == False
        assert result["reason"] == "no_subscription"

    @pytest.mark.asyncio
    async def test_check_and_apply_restrictions_active_subscription(
        self, dunning_service, mock_db, sample_subscription
    ):
        """Test restriction check with active subscription."""
        # Setup
        sample_subscription.status = "active"
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        # Execute
        result = await dunning_service.check_and_apply_restrictions(
            mock_db, user_id=1
        )

        # Assert
        assert result["restricted"] == False
        assert result["reason"] == "subscription_active"

    @pytest.mark.asyncio
    async def test_check_and_apply_restrictions_grace_period_expired(
        self, dunning_service, mock_db, sample_subscription, sample_user
    ):
        """Test applying restrictions when grace period expired."""
        # Setup
        sample_subscription.status = "past_due"
        grace_event = SubscriptionEvent(
            subscription_id=1,
            event_type="grace_period_applied",
            metadata={
                "grace_period_end": (datetime.now() - timedelta(days=1)).isoformat()
            }
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_subscription,  # First call for subscription
            grace_event,  # Second call for grace event
            sample_user   # Third call for user
        ]

        # Execute
        result = await dunning_service.check_and_apply_restrictions(
            mock_db, user_id=1
        )

        # Assert
        assert result["restricted"] == True
        assert result["reason"] == "grace_period_expired"
        assert sample_subscription.status == "unpaid"
        assert sample_user.subscription_tier == "free"
        mock_db.add.assert_called_once()  # Restriction event added
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_apply_restrictions_in_grace_period(
        self, dunning_service, mock_db, sample_subscription
    ):
        """Test restriction check during grace period."""
        # Setup
        sample_subscription.status = "past_due"
        grace_event = SubscriptionEvent(
            subscription_id=1,
            event_type="grace_period_applied",
            metadata={
                "grace_period_end": (datetime.now() + timedelta(days=3)).isoformat()
            }
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_subscription,
            grace_event
        ]

        # Execute
        result = await dunning_service.check_and_apply_restrictions(
            mock_db, user_id=1
        )

        # Assert
        assert result["restricted"] == False
        assert result["reason"] == "in_grace_period"
        assert "grace_expires_at" in result

    @pytest.mark.asyncio
    @patch('app.services.dunning_service.stripe.Subscription.delete')
    async def test_cancel_unpaid_subscription(
        self, mock_stripe_delete, dunning_service, mock_db,
        sample_subscription, sample_user
    ):
        """Test canceling unpaid subscription after max retries."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_subscription,
            sample_user
        ]

        with patch.object(dunning_service, '_send_subscription_canceled_notification', new_callable=AsyncMock) as mock_notify:

            # Execute
            await dunning_service.cancel_unpaid_subscription(
                mock_db, subscription_id=1
            )

            # Assert
            assert sample_subscription.status == "canceled"
            assert sample_subscription.canceled_at is not None
            assert sample_user.subscription_tier == "free"
            mock_stripe_delete.assert_called_once_with("sub_test123")
            mock_db.add.assert_called_once()  # Cancellation event added
            mock_db.commit.assert_called_once()
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_retry_max_attempts_reached(
        self, dunning_service, sample_subscription
    ):
        """Test schedule retry when max attempts reached."""
        # Setup
        invoice = {"id": "in_test123"}

        with patch.object(dunning_service, 'cancel_unpaid_subscription', new_callable=AsyncMock) as mock_cancel:

            # Execute
            await dunning_service._schedule_retry(
                sample_subscription, invoice, attempt_number=4
            )

            # Assert
            mock_cancel.assert_called_once_with(None, sample_subscription.id)

    @pytest.mark.asyncio
    async def test_schedule_retry_within_attempts(
        self, dunning_service, sample_subscription
    ):
        """Test schedule retry within allowed attempts."""
        # Setup
        invoice = {"id": "in_test123"}

        # Execute
        await dunning_service._schedule_retry(
            sample_subscription, invoice, attempt_number=2
        )

        # Assert - Should not raise any exceptions
        # In production, this would schedule a background job
        assert True