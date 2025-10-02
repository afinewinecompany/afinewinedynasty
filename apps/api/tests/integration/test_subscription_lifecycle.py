"""
Integration test suite for complete subscription lifecycle.

Tests the full flow from signup through billing, dunning, and cancellation.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import stripe
import json

from app.main import app
from app.db.models import User, Subscription, Invoice, SubscriptionEvent, PaymentAuditLog


class TestSubscriptionLifecycle:
    """Integration tests for complete subscription lifecycle."""

    @pytest.fixture
    async def test_user(self):
        """Create test user for lifecycle tests."""
        return Mock(
            id=100,
            email="lifecycle@example.com",
            full_name="Test User",
            stripe_customer_id=None,
            subscription_tier="free"
        )

    @pytest.fixture
    async def auth_headers(self, test_user):
        """Create authenticated headers for test user."""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            return {"Authorization": "Bearer test_token_123"}

    @pytest.mark.asyncio
    async def test_complete_subscription_lifecycle(self, test_user, auth_headers):
        """Test complete subscription lifecycle from signup to cancellation."""
        async with AsyncClient(app=app, base_url="http://test") as ac:

            # Phase 1: Initial signup and checkout
            with patch('stripe.Customer.create') as mock_create_customer:
                mock_create_customer.return_value = Mock(
                    id="cus_lifecycle123",
                    email=test_user.email
                )

                with patch('stripe.checkout.Session.create') as mock_checkout:
                    mock_checkout.return_value = Mock(
                        id="cs_test123",
                        url="https://checkout.stripe.com/test",
                        customer="cus_lifecycle123"
                    )

                    with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                        mock_execute.return_value.scalar_one_or_none.return_value = test_user

                        # Create checkout session
                        response = await ac.post(
                            "/api/subscriptions/checkout-session",
                            headers=auth_headers,
                            json={"plan_id": "premium"}
                        )

                        assert response.status_code == 200
                        data = response.json()
                        assert "checkout_url" in data
                        assert data["customer_id"] == "cus_lifecycle123"

            # Phase 2: Webhook - Subscription created
            webhook_event = {
                "id": "evt_created123",
                "type": "customer.subscription.created",
                "created": int(datetime.now().timestamp()),
                "data": {
                    "object": {
                        "id": "sub_lifecycle123",
                        "customer": "cus_lifecycle123",
                        "status": "active",
                        "current_period_start": int(datetime.now().timestamp()),
                        "current_period_end": int((datetime.now() + timedelta(days=30)).timestamp()),
                        "cancel_at_period_end": False
                    }
                }
            }

            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = webhook_event

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    # Mock finding the user
                    mock_execute.return_value.scalar_one_or_none.side_effect = [
                        None,  # No existing event
                        test_user,  # Find user
                        None  # No existing subscription
                    ]

                    with patch('sqlalchemy.ext.asyncio.AsyncSession.add') as mock_add:
                        response = await ac.post(
                            "/api/webhooks/stripe",
                            headers={"Stripe-Signature": "test_sig"},
                            json=webhook_event
                        )

                        assert response.status_code == 200
                        assert response.json()["event_id"] == "evt_created123"

            # Phase 3: Check subscription status
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_subscription = Mock(
                    id=1,
                    user_id=test_user.id,
                    status="active",
                    plan_id="premium",
                    current_period_end=datetime.now() + timedelta(days=30)
                )
                mock_execute.return_value.scalar_one_or_none.return_value = mock_subscription

                response = await ac.get(
                    "/api/subscriptions/status",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "active"
                assert data["tier"] == "premium"
                assert data["features"]["export_enabled"] is True

            # Phase 4: Payment failure and dunning
            payment_failed_event = {
                "id": "evt_failed123",
                "type": "invoice.payment_failed",
                "created": int(datetime.now().timestamp()),
                "data": {
                    "object": {
                        "id": "inv_failed123",
                        "subscription": "sub_lifecycle123",
                        "amount_due": 999,
                        "attempt_count": 1,
                        "next_payment_attempt": int((datetime.now() + timedelta(days=3)).timestamp())
                    }
                }
            }

            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = payment_failed_event

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    mock_execute.return_value.scalar_one_or_none.side_effect = [
                        None,  # No duplicate event
                        mock_subscription,  # Find subscription
                        test_user  # Find user
                    ]

                    response = await ac.post(
                        "/api/webhooks/stripe",
                        headers={"Stripe-Signature": "test_sig"},
                        json=payment_failed_event
                    )

                    assert response.status_code == 200
                    # Subscription should now be in past_due state

            # Phase 5: Update payment method
            with patch('stripe.PaymentMethod.attach') as mock_attach:
                mock_attach.return_value = Mock(
                    id="pm_new123",
                    card=Mock(
                        brand="visa",
                        last4="4242",
                        exp_month=12,
                        exp_year=2025
                    )
                )

                with patch('stripe.Customer.modify') as mock_modify_customer:
                    mock_modify_customer.return_value = Mock(
                        invoice_settings=Mock(
                            default_payment_method="pm_new123"
                        )
                    )

                    with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                        mock_execute.return_value.scalar_one_or_none.return_value = test_user

                        with patch('sqlalchemy.ext.asyncio.AsyncSession.add') as mock_add:
                            response = await ac.put(
                                "/api/subscriptions/payment-method",
                                headers=auth_headers,
                                json={"payment_method_id": "pm_new123"}
                            )

                            assert response.status_code == 200
                            data = response.json()
                            assert data["last4"] == "4242"
                            assert data["card_brand"] == "visa"

                            # Verify audit log was created
                            mock_add.assert_called()

            # Phase 6: Successful payment retry
            payment_succeeded_event = {
                "id": "evt_succeeded123",
                "type": "invoice.payment_succeeded",
                "created": int(datetime.now().timestamp()),
                "data": {
                    "object": {
                        "id": "inv_succeeded123",
                        "subscription": "sub_lifecycle123",
                        "amount_paid": 999,
                        "status": "paid"
                    }
                }
            }

            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = payment_succeeded_event

                response = await ac.post(
                    "/api/webhooks/stripe",
                    headers={"Stripe-Signature": "test_sig"},
                    json=payment_succeeded_event
                )

                assert response.status_code == 200

            # Phase 7: Cancel subscription
            with patch('stripe.Subscription.modify') as mock_modify_sub:
                mock_modify_sub.return_value = Mock(
                    id="sub_lifecycle123",
                    status="active",
                    cancel_at_period_end=True,
                    current_period_end=int((datetime.now() + timedelta(days=15)).timestamp())
                )

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    mock_execute.return_value.scalar_one_or_none.side_effect = [
                        test_user,
                        mock_subscription
                    ]

                    response = await ac.post(
                        "/api/subscriptions/cancel",
                        headers=auth_headers,
                        json={"immediate": False}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["cancel_at_period_end"] is True
                    assert "will be canceled at the end" in data["message"]

            # Phase 8: Reactivate before cancellation
            with patch('stripe.Subscription.modify') as mock_modify_sub:
                mock_modify_sub.return_value = Mock(
                    id="sub_lifecycle123",
                    status="active",
                    cancel_at_period_end=False
                )

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    mock_execute.return_value.scalar_one_or_none.side_effect = [
                        test_user,
                        mock_subscription
                    ]

                    response = await ac.post(
                        "/api/subscriptions/reactivate",
                        headers=auth_headers
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["cancel_at_period_end"] is False

            # Phase 9: Final cancellation
            subscription_deleted_event = {
                "id": "evt_deleted123",
                "type": "customer.subscription.deleted",
                "created": int(datetime.now().timestamp()),
                "data": {
                    "object": {
                        "id": "sub_lifecycle123",
                        "customer": "cus_lifecycle123",
                        "status": "canceled"
                    }
                }
            }

            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = subscription_deleted_event

                response = await ac.post(
                    "/api/webhooks/stripe",
                    headers={"Stripe-Signature": "test_sig"},
                    json=subscription_deleted_event
                )

                assert response.status_code == 200

            # Phase 10: Verify final state
            with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                mock_execute.return_value.scalar_one_or_none.return_value = None  # No active subscription

                response = await ac.get(
                    "/api/subscriptions/status",
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "no_subscription"
                assert data["tier"] == "free"
                assert data["features"]["export_enabled"] is False

    @pytest.mark.asyncio
    async def test_subscription_with_trial(self, test_user, auth_headers):
        """Test subscription lifecycle with trial period."""
        async with AsyncClient(app=app, base_url="http://test") as ac:

            # Start trial
            trial_start_event = {
                "id": "evt_trial123",
                "type": "customer.subscription.created",
                "created": int(datetime.now().timestamp()),
                "data": {
                    "object": {
                        "id": "sub_trial123",
                        "customer": "cus_trial123",
                        "status": "trialing",
                        "trial_end": int((datetime.now() + timedelta(days=14)).timestamp()),
                        "current_period_end": int((datetime.now() + timedelta(days=14)).timestamp())
                    }
                }
            }

            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = trial_start_event

                response = await ac.post(
                    "/api/webhooks/stripe",
                    headers={"Stripe-Signature": "test_sig"},
                    json=trial_start_event
                )

                assert response.status_code == 200

            # Trial ending notification
            trial_ending_event = {
                "id": "evt_trial_ending123",
                "type": "customer.subscription.trial_will_end",
                "created": int((datetime.now() + timedelta(days=11)).timestamp()),
                "data": {
                    "object": {
                        "id": "sub_trial123",
                        "customer": "cus_trial123",
                        "trial_end": int((datetime.now() + timedelta(days=14)).timestamp())
                    }
                }
            }

            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = trial_ending_event

                response = await ac.post(
                    "/api/webhooks/stripe",
                    headers={"Stripe-Signature": "test_sig"},
                    json=trial_ending_event
                )

                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_subscription_proration_flow(self, test_user, auth_headers):
        """Test subscription upgrade/downgrade with proration."""
        async with AsyncClient(app=app, base_url="http://test") as ac:

            # Simulate subscription upgrade
            with patch('stripe.Subscription.modify') as mock_modify:
                mock_modify.return_value = Mock(
                    id="sub_upgrade123",
                    status="active",
                    items=Mock(data=[
                        Mock(price=Mock(id="price_premium_plus"))
                    ])
                )

                with patch('stripe.Invoice.upcoming') as mock_upcoming:
                    mock_upcoming.return_value = Mock(
                        amount_due=500,  # Prorated amount
                        lines=Mock(data=[
                            Mock(
                                proration=True,
                                amount=500,
                                description="Remaining time on Premium Plus"
                            )
                        ])
                    )

                    response = await ac.post(
                        "/api/subscriptions/upgrade",
                        headers=auth_headers,
                        json={"new_plan": "premium_plus"}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["proration_amount"] == 500
                    assert "upgraded" in data["message"].lower()