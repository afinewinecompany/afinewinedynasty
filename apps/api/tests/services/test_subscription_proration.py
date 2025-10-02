"""
Test suite for subscription proration calculations.

Tests proration logic for plan upgrades, downgrades, and mid-cycle changes.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
import stripe

from app.services.subscription_service import SubscriptionService
from app.db.models import User, Subscription


class TestSubscriptionProration:
    """Test suite for subscription proration calculations."""

    @pytest.fixture
    def subscription_service(self):
        """Create subscription service instance."""
        return SubscriptionService()

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "test@example.com"
        user.stripe_customer_id = "cus_test123"
        return user

    @pytest.fixture
    def mock_subscription(self):
        """Create mock subscription."""
        sub = Mock(spec=Subscription)
        sub.id = 1
        sub.user_id = 1
        sub.stripe_subscription_id = "sub_test123"
        sub.status = "active"
        sub.plan_id = "premium"
        sub.current_period_start = datetime.now()
        sub.current_period_end = datetime.now() + timedelta(days=30)
        return sub

    @pytest.mark.asyncio
    async def test_proration_mid_cycle_upgrade(
        self, subscription_service, mock_user, mock_subscription
    ):
        """Test proration calculation for mid-cycle upgrade."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock Stripe API calls
        with patch('stripe.Subscription.modify') as mock_modify:
            mock_modify.return_value = Mock(
                id="sub_test123",
                status="active",
                latest_invoice=Mock(
                    id="inv_test123",
                    amount_due=500,  # $5.00 prorated amount
                    lines=Mock(data=[
                        Mock(
                            proration=True,
                            amount=500,
                            description="Remaining time on Premium plan"
                        )
                    ])
                )
            )

            # Calculate proration for upgrade
            result = await subscription_service.calculate_proration(
                mock_db,
                mock_subscription,
                "premium_plus"  # Upgrading to higher tier
            )

            assert result["proration_amount"] == 500
            assert result["proration_description"] == "Remaining time on Premium plan"
            assert result["requires_immediate_payment"] is True

    @pytest.mark.asyncio
    async def test_proration_immediate_downgrade(
        self, subscription_service, mock_subscription
    ):
        """Test proration for immediate downgrade."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock Stripe API for downgrade
        with patch('stripe.Subscription.modify') as mock_modify:
            mock_modify.return_value = Mock(
                id="sub_test123",
                status="active",
                latest_invoice=Mock(
                    id="inv_test123",
                    amount_due=-300,  # Credit for unused time
                    lines=Mock(data=[
                        Mock(
                            proration=True,
                            amount=-300,
                            description="Unused time on Premium plan"
                        )
                    ])
                )
            )

            result = await subscription_service.calculate_proration(
                mock_db,
                mock_subscription,
                "basic"  # Downgrading to lower tier
            )

            assert result["proration_amount"] == -300
            assert result["credit_applied"] is True
            assert result["requires_immediate_payment"] is False

    @pytest.mark.asyncio
    async def test_proration_at_period_end(
        self, subscription_service, mock_subscription
    ):
        """Test no proration when change scheduled at period end."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch('stripe.Subscription.modify') as mock_modify:
            mock_modify.return_value = Mock(
                id="sub_test123",
                status="active",
                cancel_at_period_end=False,
                schedule=Mock(
                    phases=[
                        Mock(
                            start_date=mock_subscription.current_period_end.timestamp(),
                            items=[Mock(price="price_new")]
                        )
                    ]
                )
            )

            result = await subscription_service.calculate_proration(
                mock_db,
                mock_subscription,
                "premium",
                immediate=False  # Change at period end
            )

            assert result["proration_amount"] == 0
            assert result["scheduled_change"] is True
            assert result["change_date"] == mock_subscription.current_period_end.isoformat()

    @pytest.mark.asyncio
    async def test_proration_multiple_line_items(
        self, subscription_service, mock_subscription
    ):
        """Test proration with multiple subscription items."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch('stripe.Subscription.retrieve') as mock_retrieve:
            mock_retrieve.return_value = Mock(
                id="sub_test123",
                items=Mock(data=[
                    Mock(
                        id="si_base",
                        price=Mock(id="price_base", unit_amount=999),
                        quantity=1
                    ),
                    Mock(
                        id="si_addon",
                        price=Mock(id="price_addon", unit_amount=299),
                        quantity=2
                    )
                ])
            )

            with patch('stripe.Invoice.upcoming') as mock_upcoming:
                mock_upcoming.return_value = Mock(
                    amount_due=750,
                    lines=Mock(data=[
                        Mock(proration=True, amount=450, description="Base plan proration"),
                        Mock(proration=True, amount=300, description="Add-on proration")
                    ])
                )

                result = await subscription_service.calculate_proration_preview(
                    mock_db,
                    mock_subscription,
                    {"base": "premium", "addon_quantity": 3}
                )

                assert result["total_proration"] == 750
                assert len(result["line_items"]) == 2
                assert result["line_items"][0]["amount"] == 450
                assert result["line_items"][1]["amount"] == 300

    @pytest.mark.asyncio
    async def test_proration_with_discount(
        self, subscription_service, mock_subscription
    ):
        """Test proration calculation with active discount/coupon."""
        mock_db = AsyncMock(spec=AsyncSession)

        with patch('stripe.Subscription.modify') as mock_modify:
            mock_modify.return_value = Mock(
                id="sub_test123",
                discount=Mock(
                    coupon=Mock(
                        percent_off=20,
                        valid=True
                    )
                ),
                latest_invoice=Mock(
                    amount_due=400,  # After 20% discount
                    subtotal=500,
                    discount=Mock(amount=100),
                    lines=Mock(data=[
                        Mock(
                            proration=True,
                            amount=500,
                            discount_amounts=[Mock(amount=100)]
                        )
                    ])
                )
            )

            result = await subscription_service.calculate_proration(
                mock_db,
                mock_subscription,
                "premium_plus"
            )

            assert result["subtotal"] == 500
            assert result["discount_amount"] == 100
            assert result["proration_amount"] == 400
            assert result["has_discount"] is True

    @pytest.mark.asyncio
    async def test_proration_timezone_handling(
        self, subscription_service, mock_subscription
    ):
        """Test proration handles timezones correctly."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Set specific dates with timezone info
        start_date = datetime(2024, 1, 15, 10, 0, 0)
        end_date = datetime(2024, 2, 15, 10, 0, 0)
        change_date = datetime(2024, 1, 30, 10, 0, 0)  # Mid-cycle

        mock_subscription.current_period_start = start_date
        mock_subscription.current_period_end = end_date

        with patch('stripe.Invoice.upcoming') as mock_upcoming:
            # Calculate expected proration (15 days used, 15 days remaining)
            days_remaining = (end_date - change_date).days
            days_total = (end_date - start_date).days
            expected_proration = int((days_remaining / days_total) * 999)

            mock_upcoming.return_value = Mock(
                amount_due=expected_proration,
                lines=Mock(data=[
                    Mock(
                        proration=True,
                        amount=expected_proration,
                        period=Mock(
                            start=int(change_date.timestamp()),
                            end=int(end_date.timestamp())
                        )
                    )
                ])
            )

            result = await subscription_service.calculate_proration(
                mock_db,
                mock_subscription,
                "premium_plus",
                change_date=change_date
            )

            assert result["proration_amount"] == expected_proration
            assert result["days_remaining"] == days_remaining
            assert result["days_total"] == days_total

    @pytest.mark.asyncio
    async def test_proration_error_handling(
        self, subscription_service, mock_subscription
    ):
        """Test proration calculation error handling."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Test Stripe API error
        with patch('stripe.Invoice.upcoming') as mock_upcoming:
            mock_upcoming.side_effect = stripe.error.InvalidRequestError(
                "Invalid subscription", None
            )

            with pytest.raises(Exception) as exc_info:
                await subscription_service.calculate_proration(
                    mock_db,
                    mock_subscription,
                    "invalid_plan"
                )

            assert "Invalid subscription" in str(exc_info.value)

        # Test invalid plan transition
        with patch('stripe.Invoice.upcoming') as mock_upcoming:
            mock_upcoming.return_value = Mock(
                amount_due=0,
                lines=Mock(data=[])
            )

            result = await subscription_service.calculate_proration(
                mock_db,
                mock_subscription,
                "same_plan"  # No change
            )

            assert result["proration_amount"] == 0
            assert result["no_change"] is True