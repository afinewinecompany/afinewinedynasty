"""
Test suite for admin subscription endpoints.

Tests admin-only endpoints for subscription management, metrics, and customer support.
"""

import pytest
from httpx import AsyncClient
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import json

from app.main import app
from app.db.models import User, Subscription, SubscriptionEvent, Invoice


class TestAdminSubscriptionEndpoints:
    """Test suite for admin subscription management endpoints."""

    @pytest.fixture
    async def admin_user(self):
        """Create admin user fixture."""
        return Mock(
            id=1,
            email="admin@example.com",
            is_admin=True,
            subscription_tier="admin"
        )

    @pytest.fixture
    async def regular_user(self):
        """Create regular user fixture."""
        return Mock(
            id=2,
            email="user@example.com",
            is_admin=False,
            subscription_tier="premium"
        )

    @pytest.fixture
    async def admin_headers(self, admin_user):
        """Create headers with admin JWT token."""
        with patch('app.api.deps.get_current_user', return_value=admin_user):
            return {"Authorization": "Bearer admin_token_123"}

    @pytest.fixture
    async def user_headers(self, regular_user):
        """Create headers with regular user JWT token."""
        with patch('app.api.deps.get_current_user', return_value=regular_user):
            return {"Authorization": "Bearer user_token_123"}

    @pytest.mark.asyncio
    async def test_get_subscription_metrics_as_admin(self, admin_headers):
        """Test admin can access subscription metrics."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    # Mock metrics data
                    mock_execute.return_value.scalar_one_or_none.side_effect = [
                        100,  # Total active subscriptions
                        9990,  # Total MRR (in cents)
                        5,    # Churned this month
                        95    # Active last month
                    ]

                    response = await ac.get(
                        "/api/admin/subscriptions",
                        headers=admin_headers
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["total_active"] == 100
                    assert data["monthly_recurring_revenue"] == 999.0
                    assert data["churn_rate"] == 5.26  # (5/95)*100

    @pytest.mark.asyncio
    async def test_get_subscription_metrics_as_non_admin(self, user_headers):
        """Test non-admin cannot access subscription metrics."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.side_effect = Exception("Admin access required")

                response = await ac.get(
                    "/api/admin/subscriptions",
                    headers=user_headers
                )

                assert response.status_code == 403
                assert "Admin access required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_user_subscription_details(self, admin_headers):
        """Test admin can get specific user's subscription details."""
        target_user_id = 123

        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    # Mock user and subscription data
                    mock_user = Mock(
                        id=target_user_id,
                        email="customer@example.com",
                        subscription_tier="premium"
                    )
                    mock_subscription = Mock(
                        id=10,
                        user_id=target_user_id,
                        status="active",
                        plan_id="premium",
                        current_period_end=datetime.now() + timedelta(days=15)
                    )
                    mock_invoices = [
                        Mock(id=1, amount_paid=999, status="paid"),
                        Mock(id=2, amount_paid=999, status="paid")
                    ]

                    mock_execute.return_value.scalar_one_or_none.side_effect = [
                        mock_user,
                        mock_subscription
                    ]
                    mock_execute.return_value.scalars.return_value.all.return_value = mock_invoices

                    response = await ac.get(
                        f"/api/admin/subscriptions/{target_user_id}",
                        headers=admin_headers
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["user"]["email"] == "customer@example.com"
                    assert data["subscription"]["status"] == "active"
                    assert len(data["recent_invoices"]) == 2

    @pytest.mark.asyncio
    async def test_apply_refund(self, admin_headers):
        """Test admin can apply refund to subscription."""
        target_user_id = 123

        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('stripe.Refund.create') as mock_refund:
                    mock_refund.return_value = Mock(
                        id="re_test123",
                        amount=999,
                        status="succeeded",
                        charge="ch_test123"
                    )

                    with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                        mock_invoice = Mock(
                            id=1,
                            stripe_invoice_id="inv_test123",
                            amount_paid=999
                        )
                        mock_execute.return_value.scalar_one_or_none.return_value = mock_invoice

                        response = await ac.post(
                            f"/api/admin/subscriptions/{target_user_id}/refund",
                            headers=admin_headers,
                            json={
                                "invoice_id": "inv_test123",
                                "amount": 999,
                                "reason": "Customer request"
                            }
                        )

                        assert response.status_code == 200
                        data = response.json()
                        assert data["refund_id"] == "re_test123"
                        assert data["amount"] == 999
                        assert data["status"] == "succeeded"

    @pytest.mark.asyncio
    async def test_extend_trial(self, admin_headers):
        """Test admin can extend trial period."""
        target_user_id = 123

        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('stripe.Subscription.modify') as mock_modify:
                    new_trial_end = datetime.now() + timedelta(days=7)
                    mock_modify.return_value = Mock(
                        id="sub_test123",
                        status="trialing",
                        trial_end=int(new_trial_end.timestamp())
                    )

                    with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                        mock_subscription = Mock(
                            id=10,
                            stripe_subscription_id="sub_test123",
                            status="trialing"
                        )
                        mock_execute.return_value.scalar_one_or_none.return_value = mock_subscription

                        response = await ac.post(
                            f"/api/admin/subscriptions/{target_user_id}/extend-trial",
                            headers=admin_headers,
                            json={"days": 7}
                        )

                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] == "trialing"
                        assert "trial_end" in data

    @pytest.mark.asyncio
    async def test_get_subscription_events(self, admin_headers):
        """Test admin can view subscription event audit trail."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    mock_events = [
                        Mock(
                            id=1,
                            subscription_id=10,
                            event_type="created",
                            created_at=datetime.now() - timedelta(days=30),
                            metadata={"plan": "premium"}
                        ),
                        Mock(
                            id=2,
                            subscription_id=10,
                            event_type="payment_succeeded",
                            created_at=datetime.now() - timedelta(days=1),
                            metadata={"amount": 999}
                        )
                    ]
                    mock_execute.return_value.scalars.return_value.all.return_value = mock_events

                    response = await ac.get(
                        "/api/admin/subscriptions/events",
                        headers=admin_headers,
                        params={"limit": 50, "offset": 0}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert len(data["events"]) == 2
                    assert data["events"][0]["event_type"] == "created"
                    assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_admin_metrics_calculation(self, admin_headers):
        """Test correct calculation of subscription metrics."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('sqlalchemy.ext.asyncio.AsyncSession.execute') as mock_execute:
                    # Mock different subscription counts and revenues
                    mock_execute.return_value.mappings.return_value.all.return_value = [
                        {"status": "active", "count": 80, "revenue": 7992},
                        {"status": "trialing", "count": 20, "revenue": 0},
                        {"status": "past_due", "count": 5, "revenue": 499}
                    ]

                    response = await ac.get(
                        "/api/admin/subscriptions/metrics",
                        headers=admin_headers
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["total_subscriptions"] == 105
                    assert data["active_subscriptions"] == 80
                    assert data["trialing_subscriptions"] == 20
                    assert data["past_due_subscriptions"] == 5
                    assert data["total_mrr"] == 8491  # 7992 + 499

    @pytest.mark.asyncio
    async def test_admin_customer_support_actions(self, admin_headers):
        """Test admin customer support actions."""
        target_user_id = 123

        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                # Test pause subscription
                with patch('stripe.Subscription.modify') as mock_modify:
                    mock_modify.return_value = Mock(
                        id="sub_test123",
                        status="paused",
                        pause_collection=Mock(behavior="void")
                    )

                    response = await ac.post(
                        f"/api/admin/subscriptions/{target_user_id}/pause",
                        headers=admin_headers,
                        json={"reason": "Payment issue resolution"}
                    )

                    assert response.status_code == 200
                    assert response.json()["status"] == "paused"

                # Test resume subscription
                with patch('stripe.Subscription.modify') as mock_modify:
                    mock_modify.return_value = Mock(
                        id="sub_test123",
                        status="active",
                        pause_collection=None
                    )

                    response = await ac.post(
                        f"/api/admin/subscriptions/{target_user_id}/resume",
                        headers=admin_headers
                    )

                    assert response.status_code == 200
                    assert response.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_admin_audit_logging(self, admin_headers):
        """Test admin actions are properly logged."""
        target_user_id = 123

        async with AsyncClient(app=app, base_url="http://test") as ac:
            with patch('app.api.deps.require_admin_access') as mock_admin:
                mock_admin.return_value = Mock(id=1, is_admin=True)

                with patch('sqlalchemy.ext.asyncio.AsyncSession.add') as mock_add:
                    with patch('stripe.Refund.create') as mock_refund:
                        mock_refund.return_value = Mock(
                            id="re_test123",
                            amount=500,
                            status="succeeded"
                        )

                        response = await ac.post(
                            f"/api/admin/subscriptions/{target_user_id}/refund",
                            headers=admin_headers,
                            json={"amount": 500, "reason": "Goodwill refund"}
                        )

                        # Verify audit event was created
                        mock_add.assert_called()
                        audit_event = mock_add.call_args[0][0]
                        assert hasattr(audit_event, 'event_type')
                        assert audit_event.event_type == "admin_refund"
                        assert audit_event.metadata["admin_id"] == 1
                        assert audit_event.metadata["amount"] == 500

    @pytest.mark.asyncio
    async def test_admin_authorization_checks(self):
        """Test proper authorization checks for admin endpoints."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test without authentication
            response = await ac.get("/api/admin/subscriptions")
            assert response.status_code == 401

            # Test with regular user token
            with patch('app.api.deps.get_current_user') as mock_user:
                mock_user.return_value = Mock(
                    email="user@example.com",
                    is_admin=False
                )

                with patch('app.api.deps.require_admin_access') as mock_admin:
                    mock_admin.side_effect = Exception("Forbidden")

                    response = await ac.get(
                        "/api/admin/subscriptions",
                        headers={"Authorization": "Bearer user_token"}
                    )

                    assert response.status_code == 403