"""
Test suite for SubscriptionService.

Tests subscription management operations including creation,
cancellation, and synchronization with Stripe.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subscription_service import SubscriptionService
from app.db.models import User, Subscription, PaymentMethod, Invoice, SubscriptionEvent


@pytest.fixture
def subscription_service():
    """Create SubscriptionService instance."""
    return SubscriptionService()


@pytest.fixture
def mock_db():
    """Create mock database session."""
    mock = AsyncMock(spec=AsyncSession)
    return mock


@pytest.fixture
def sample_user():
    """Create sample user for testing."""
    user = User(
        id=1,
        email="test@example.com",
        full_name="Test User",
        stripe_customer_id="cus_test123",
        subscription_tier="free"
    )
    return user


@pytest.fixture
def sample_subscription():
    """Create sample subscription for testing."""
    subscription = Subscription(
        id=1,
        user_id=1,
        stripe_subscription_id="sub_test123",
        stripe_customer_id="cus_test123",
        status="active",
        plan_id="premium",
        current_period_start=datetime.now(),
        current_period_end=datetime.now() + timedelta(days=30),
        cancel_at_period_end=False
    )
    return subscription


class TestSubscriptionService:
    """Test SubscriptionService methods."""

    @pytest.mark.asyncio
    @patch('app.services.subscription_service.stripe.checkout.Session.create')
    async def test_create_checkout_session_success(
        self, mock_stripe_session, subscription_service, mock_db, sample_user
    ):
        """Test successful checkout session creation."""
        # Setup
        mock_stripe_session.return_value = Mock(
            url="https://checkout.stripe.com/test",
            id="cs_test123"
        )

        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user

        # Execute
        result = await subscription_service.create_checkout_session(
            mock_db, user_id=1, plan_id="premium"
        )

        # Assert
        assert result["checkout_url"] == "https://checkout.stripe.com/test"
        assert result["session_id"] == "cs_test123"
        assert result["customer_id"] == "cus_test123"
        mock_stripe_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_checkout_session_user_not_found(
        self, subscription_service, mock_db
    ):
        """Test checkout session creation with non-existent user."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        # Execute & Assert
        with pytest.raises(HTTPException) as exc_info:
            await subscription_service.create_checkout_session(
                mock_db, user_id=999
            )

        assert exc_info.value.status_code == 404
        assert "User not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch('app.services.subscription_service.stripe.Customer.create')
    @patch('app.services.subscription_service.stripe.checkout.Session.create')
    async def test_create_checkout_session_creates_stripe_customer(
        self, mock_stripe_session, mock_stripe_customer,
        subscription_service, mock_db, sample_user
    ):
        """Test checkout session creates Stripe customer if missing."""
        # Setup
        sample_user.stripe_customer_id = None
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user

        mock_stripe_customer.return_value = Mock(id="cus_new123")
        mock_stripe_session.return_value = Mock(
            url="https://checkout.stripe.com/test",
            id="cs_test123"
        )

        # Execute
        result = await subscription_service.create_checkout_session(
            mock_db, user_id=1
        )

        # Assert
        mock_stripe_customer.assert_called_once_with(
            email=sample_user.email,
            name=sample_user.full_name,
            metadata={"user_id": "1", "platform": "afinewinedynasty"}
        )
        assert sample_user.stripe_customer_id == "cus_new123"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.subscription_service.stripe.Subscription.retrieve')
    async def test_sync_subscription_from_stripe_success(
        self, mock_stripe_retrieve, subscription_service, mock_db,
        sample_user, sample_subscription
    ):
        """Test successful subscription sync from Stripe."""
        # Setup
        mock_stripe_retrieve.return_value = Mock(
            id="sub_test123",
            customer="cus_test123",
            status="active",
            current_period_start=int(datetime.now().timestamp()),
            current_period_end=int((datetime.now() + timedelta(days=30)).timestamp()),
            cancel_at_period_end=False,
            canceled_at=None
        )

        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_user,  # User query
            sample_subscription  # Subscription query
        ]

        # Execute
        result = await subscription_service.sync_subscription_from_stripe(
            mock_db, "sub_test123"
        )

        # Assert
        assert result.status == "active"
        assert sample_user.subscription_tier == "premium"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_subscription_at_period_end(
        self, subscription_service, mock_db, sample_subscription
    ):
        """Test canceling subscription at period end."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        with patch('app.services.subscription_service.stripe.Subscription.modify') as mock_modify:
            mock_modify.return_value = Mock(cancel_at_period_end=True)

            # Execute
            result = await subscription_service.cancel_subscription(
                mock_db, user_id=1, immediate=False
            )

            # Assert
            assert result.cancel_at_period_end == True
            assert result.canceled_at is not None
            mock_modify.assert_called_once_with(
                "sub_test123",
                cancel_at_period_end=True
            )

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediate(
        self, subscription_service, mock_db, sample_subscription
    ):
        """Test immediate subscription cancellation."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        with patch('app.services.subscription_service.stripe.Subscription.delete') as mock_delete:
            mock_delete.return_value = Mock(status="canceled")

            # Execute
            result = await subscription_service.cancel_subscription(
                mock_db, user_id=1, immediate=True
            )

            # Assert
            assert result.status == "canceled"
            mock_delete.assert_called_once_with("sub_test123")

    @pytest.mark.asyncio
    async def test_reactivate_subscription_success(
        self, subscription_service, mock_db, sample_subscription
    ):
        """Test reactivating a canceled subscription."""
        # Setup
        sample_subscription.cancel_at_period_end = True
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        with patch('app.services.subscription_service.stripe.Subscription.modify') as mock_modify:
            mock_modify.return_value = Mock(cancel_at_period_end=False)

            # Execute
            result = await subscription_service.reactivate_subscription(
                mock_db, user_id=1
            )

            # Assert
            assert result.cancel_at_period_end == False
            assert result.canceled_at is None
            mock_modify.assert_called_once_with(
                "sub_test123",
                cancel_at_period_end=False
            )

    @pytest.mark.asyncio
    async def test_get_subscription_status_with_cache(
        self, subscription_service, mock_db, sample_subscription
    ):
        """Test getting subscription status with caching."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        with patch('app.services.subscription_service.get_redis_client') as mock_redis:
            mock_redis_client = AsyncMock()
            mock_redis_client.get.return_value = None  # Cache miss
            mock_redis.return_value = mock_redis_client

            # Execute
            result = await subscription_service.get_subscription_status(
                mock_db, user_id=1
            )

            # Assert
            assert result == sample_subscription
            mock_redis_client.get.assert_called_once_with("subscription:status:1")
            mock_redis_client.setex.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.services.subscription_service.stripe.PaymentMethod.attach')
    @patch('app.services.subscription_service.stripe.PaymentMethod.retrieve')
    @patch('app.services.subscription_service.stripe.Customer.modify')
    async def test_update_payment_method_success(
        self, mock_customer_modify, mock_pm_retrieve, mock_pm_attach,
        subscription_service, mock_db, sample_user
    ):
        """Test updating payment method."""
        # Setup
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_user
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        mock_pm_retrieve.return_value = Mock(
            card=Mock(brand="visa", last4="4242", exp_month=12, exp_year=2025)
        )

        # Execute
        result = await subscription_service.update_payment_method(
            mock_db, user_id=1, payment_method_id="pm_test123"
        )

        # Assert
        assert result.card_brand == "visa"
        assert result.last4 == "4242"
        mock_pm_attach.assert_called_once()
        mock_customer_modify.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_subscription_created_webhook(
        self, subscription_service, mock_db, sample_subscription
    ):
        """Test handling subscription.created webhook event."""
        # Setup
        stripe_subscription = {
            "id": "sub_test123",
            "status": "active"
        }

        with patch.object(
            subscription_service,
            'sync_subscription_from_stripe',
            new_callable=AsyncMock
        ) as mock_sync:
            mock_sync.return_value = sample_subscription
            mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

            # Execute
            await subscription_service.handle_subscription_created(
                mock_db, stripe_subscription, "evt_test123"
            )

            # Assert
            mock_sync.assert_called_once_with(mock_db, "sub_test123")
            # Check that event was added
            assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_handle_payment_succeeded_webhook(
        self, subscription_service, mock_db, sample_subscription
    ):
        """Test handling invoice.payment_succeeded webhook event."""
        # Setup
        invoice = {
            "id": "in_test123",
            "subscription": "sub_test123",
            "amount_paid": 999,
            "currency": "usd",
            "billing_reason": "subscription_cycle",
            "invoice_pdf": "https://stripe.com/invoice.pdf"
        }

        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_subscription

        # Execute
        await subscription_service.handle_payment_succeeded(
            mock_db, invoice, "evt_test123"
        )

        # Assert
        # Check that invoice and event were added
        assert mock_db.add.call_count == 2
        mock_db.commit.assert_called_once()