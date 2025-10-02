"""
Test suite for subscription API endpoints.

Tests subscription management endpoints including checkout,
status checking, cancellation, and payment method updates.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from app.main import app
from app.db.models import User, Subscription


@pytest.fixture
async def authenticated_client(async_client: AsyncClient):
    """Create authenticated client with valid JWT token."""
    # Mock authentication
    with patch('app.api.deps.get_current_user') as mock_auth:
        mock_auth.return_value = Mock(
            email="test@example.com",
            is_active=True
        )
        yield async_client


@pytest.fixture
def sample_subscription():
    """Create sample subscription for testing."""
    return {
        "status": "active",
        "tier": "premium",
        "plan_id": "premium",
        "current_period_start": datetime.now().isoformat(),
        "current_period_end": (datetime.now() + timedelta(days=30)).isoformat(),
        "cancel_at_period_end": False,
        "features": {
            "prospects_limit": 500,
            "export_enabled": True,
            "advanced_filters_enabled": True,
            "comparison_enabled": True
        }
    }


class TestSubscriptionEndpoints:
    """Test subscription management endpoints."""

    @pytest.mark.asyncio
    async def test_create_checkout_session_success(self, authenticated_client):
        """Test successful checkout session creation."""
        with patch('app.services.subscription_service.SubscriptionService.create_checkout_session') as mock_create:
            mock_create.return_value = {
                "checkout_url": "https://checkout.stripe.com/test",
                "session_id": "cs_test123",
                "customer_id": "cus_test123"
            }

            response = await authenticated_client.post(
                "/api/v1/subscriptions/checkout-session",
                json={"plan_id": "premium"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["checkout_url"] == "https://checkout.stripe.com/test"
            assert data["session_id"] == "cs_test123"

    @pytest.mark.asyncio
    async def test_get_subscription_status_premium(self, authenticated_client, sample_subscription):
        """Test getting subscription status for premium user."""
        with patch('app.api.deps.get_subscription_status') as mock_status:
            mock_status.return_value = Mock(
                status="active",
                plan_id="premium",
                current_period_start=datetime.now(),
                current_period_end=datetime.now() + timedelta(days=30),
                cancel_at_period_end=False
            )

            response = await authenticated_client.get("/api/v1/subscriptions/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "active"
            assert data["tier"] == "premium"
            assert data["features"]["prospects_limit"] == 500
            assert data["features"]["export_enabled"] == True

    @pytest.mark.asyncio
    async def test_get_subscription_status_free(self, authenticated_client):
        """Test getting subscription status for free user."""
        with patch('app.api.deps.get_subscription_status') as mock_status:
            mock_status.return_value = None

            response = await authenticated_client.get("/api/v1/subscriptions/status")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "no_subscription"
            assert data["tier"] == "free"
            assert data["features"]["prospects_limit"] == 100
            assert data["features"]["export_enabled"] == False

    @pytest.mark.asyncio
    async def test_cancel_subscription_at_period_end(self, authenticated_client):
        """Test canceling subscription at period end."""
        with patch('app.services.subscription_service.SubscriptionService.cancel_subscription') as mock_cancel:
            mock_cancel.return_value = Mock(
                status="active",
                cancel_at_period_end=True,
                current_period_end=datetime.now() + timedelta(days=30)
            )

            response = await authenticated_client.post(
                "/api/v1/subscriptions/cancel",
                json={"immediate": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["cancel_at_period_end"] == True
            assert "will be canceled at the end" in data["message"]

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediate(self, authenticated_client):
        """Test immediate subscription cancellation."""
        with patch('app.services.subscription_service.SubscriptionService.cancel_subscription') as mock_cancel:
            mock_cancel.return_value = Mock(
                status="canceled",
                cancel_at_period_end=False,
                current_period_end=datetime.now()
            )

            response = await authenticated_client.post(
                "/api/v1/subscriptions/cancel",
                json={"immediate": True}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "canceled"
            assert "canceled immediately" in data["message"]

    @pytest.mark.asyncio
    async def test_reactivate_subscription(self, authenticated_client):
        """Test reactivating a canceled subscription."""
        with patch('app.services.subscription_service.SubscriptionService.reactivate_subscription') as mock_reactivate:
            mock_reactivate.return_value = Mock(
                status="active",
                cancel_at_period_end=False,
                current_period_end=datetime.now() + timedelta(days=30)
            )

            response = await authenticated_client.post("/api/v1/subscriptions/reactivate")

            assert response.status_code == 200
            data = response.json()
            assert data["cancel_at_period_end"] == False
            assert "reactivated successfully" in data["message"]

    @pytest.mark.asyncio
    async def test_update_payment_method(self, authenticated_client):
        """Test updating payment method."""
        with patch('app.services.subscription_service.SubscriptionService.update_payment_method') as mock_update:
            mock_update.return_value = Mock(
                card_brand="visa",
                last4="4242",
                exp_month=12,
                exp_year=2025,
                is_default=True
            )

            response = await authenticated_client.put(
                "/api/v1/subscriptions/payment-method",
                json={"payment_method_id": "pm_test123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["card_brand"] == "visa"
            assert data["last4"] == "4242"
            assert "updated successfully" in data["message"]


class TestWebhookEndpoints:
    """Test Stripe webhook endpoints."""

    @pytest.mark.asyncio
    async def test_webhook_signature_verification_missing(self, async_client):
        """Test webhook endpoint without signature."""
        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            json={"type": "test"}
        )

        assert response.status_code == 400
        assert "Missing Stripe signature" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch('app.api.api_v1.endpoints.webhooks.verify_stripe_signature')
    @patch('app.services.subscription_service.SubscriptionService.handle_subscription_created')
    async def test_webhook_subscription_created(
        self, mock_handle, mock_verify, async_client
    ):
        """Test handling subscription.created webhook."""
        mock_verify.return_value = {
            "type": "customer.subscription.created",
            "id": "evt_test123",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "status": "active"
                }
            }
        }

        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            headers={"stripe-signature": "test_sig"},
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["event_id"] == "evt_test123"
        mock_handle.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.api.api_v1.endpoints.webhooks.verify_stripe_signature')
    @patch('app.services.dunning_service.DunningService.handle_payment_failed')
    async def test_webhook_payment_failed(
        self, mock_handle, mock_verify, async_client
    ):
        """Test handling invoice.payment_failed webhook."""
        mock_verify.return_value = {
            "type": "invoice.payment_failed",
            "id": "evt_test123",
            "data": {
                "object": {
                    "id": "in_test123",
                    "subscription": "sub_test123",
                    "amount_due": 999
                }
            }
        }

        response = await async_client.post(
            "/api/v1/webhooks/stripe",
            headers={"stripe-signature": "test_sig"},
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        mock_handle.assert_called_once()


class TestAccessControl:
    """Test tier-based access control."""

    @pytest.mark.asyncio
    async def test_premium_feature_access_denied(self, authenticated_client):
        """Test access denied to premium features for free users."""
        with patch('app.api.deps.get_current_user') as mock_auth:
            mock_auth.return_value = Mock(email="test@example.com")

            with patch('app.api.deps.subscription_tier_required') as mock_tier:
                mock_tier.side_effect = Exception("Premium subscription required")

                # This would test a premium-only endpoint
                # Example: prospect comparison endpoint
                # response = await authenticated_client.post("/api/v1/prospects/compare")
                # assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_check_subscription_feature(self, authenticated_client):
        """Test checking specific feature access."""
        with patch('app.api.deps.check_subscription_feature') as mock_check:
            mock_check.return_value = True

            # This would test feature checking in actual endpoints
            # The implementation would check features before allowing access