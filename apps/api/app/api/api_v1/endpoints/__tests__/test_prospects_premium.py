"""Tests for premium prospect endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User


class TestPremiumProspectAccess:
    """Test suite for premium prospect access controls."""

    @pytest.mark.asyncio
    async def test_premium_user_gets_500_prospects(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test that premium users can access up to 500 prospects."""
        response = await async_client.get(
            "/api/v1/prospects",
            params={"limit": 500},
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "prospects" in data
        # Should allow up to 500 for premium users
        assert len(data["prospects"]) <= 500

    @pytest.mark.asyncio
    async def test_free_user_limited_to_100_prospects(
        self,
        async_client: AsyncClient,
        free_user_token: str
    ):
        """Test that free users are limited to 100 prospects."""
        response = await async_client.get(
            "/api/v1/prospects",
            params={"limit": 500},  # Request 500 but should get 100
            headers={"Authorization": f"Bearer {free_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "prospects" in data
        # Should be limited to 100 for free users
        assert len(data["prospects"]) <= 100

    @pytest.mark.asyncio
    async def test_premium_user_can_export(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test that premium users can export data."""
        response = await async_client.get(
            "/api/v1/prospects/export/csv",
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        # Should succeed for premium users
        assert response.status_code in [200, 202]

    @pytest.mark.asyncio
    async def test_free_user_cannot_export(
        self,
        async_client: AsyncClient,
        free_user_token: str
    ):
        """Test that free users cannot export data."""
        response = await async_client.get(
            "/api/v1/prospects/export/csv",
            headers={"Authorization": f"Bearer {free_user_token}"}
        )

        # Should be forbidden for free users
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_premium_user_can_compare_multiple(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test that premium users can compare multiple prospects."""
        response = await async_client.get(
            "/api/v1/prospects/compare",
            params={"prospect_ids": "1,2,3,4,5"},  # 5 prospects
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        # Should succeed for premium users
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_free_user_limited_comparisons(
        self,
        async_client: AsyncClient,
        free_user_token: str
    ):
        """Test that free users have limited comparisons."""
        response = await async_client.get(
            "/api/v1/prospects/compare",
            params={"prospect_ids": "1,2,3,4,5"},  # 5 prospects (exceeds limit)
            headers={"Authorization": f"Bearer {free_user_token}"}
        )

        # Should be limited for free users
        assert response.status_code in [400, 403]


class TestPremiumEndpoints:
    """Test suite for premium-only endpoints."""

    @pytest.mark.asyncio
    async def test_advanced_filter_requires_premium(
        self,
        async_client: AsyncClient,
        free_user_token: str
    ):
        """Test that advanced filtering requires premium."""
        response = await async_client.post(
            "/api/v1/premium/advanced-filter",
            json={
                "basic_filters": {"position": ["SS"]},
                "operator": "AND"
            },
            headers={"Authorization": f"Bearer {free_user_token}"}
        )

        assert response.status_code == 403
        assert "premium" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_advanced_filter_works_for_premium(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test that advanced filtering works for premium users."""
        response = await async_client.post(
            "/api/v1/premium/advanced-filter",
            json={
                "basic_filters": {"position": ["SS", "2B"]},
                "stat_filters": {"batting_avg_min": 0.300},
                "operator": "AND"
            },
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "prospects" in data

    @pytest.mark.asyncio
    async def test_batch_compare_premium_only(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test batch comparison for premium users."""
        response = await async_client.post(
            "/api/v1/premium/batch-compare",
            json={
                "prospect_ids": [1, 2, 3],
                "include_stats": True,
                "include_predictions": True
            },
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "prospects" in data
        assert "statistical_comparison" in data

    @pytest.mark.asyncio
    async def test_saved_search_creation_premium_only(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test saved search creation for premium users."""
        response = await async_client.post(
            "/api/v1/premium/saved-searches",
            json={
                "name": "Top SS Prospects",
                "filters": {
                    "basic_filters": {"position": ["SS"]},
                    "operator": "AND"
                },
                "is_public": False
            },
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Top SS Prospects"

    @pytest.mark.asyncio
    async def test_export_data_premium_only(
        self,
        async_client: AsyncClient,
        premium_user_token: str
    ):
        """Test data export for premium users."""
        response = await async_client.post(
            "/api/v1/premium/export",
            json={
                "format": "csv",
                "data_type": "rankings",
                "filters": {}
            },
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )

        assert response.status_code in [200, 202]
        data = response.json()
        assert "filename" in data or "task_id" in data

    @pytest.mark.asyncio
    async def test_historical_data_access_premium_only(
        self,
        async_client: AsyncClient,
        premium_user_token: str,
        free_user_token: str
    ):
        """Test historical data access restriction."""
        # Free user should be denied
        response_free = await async_client.get(
            "/api/v1/prospects/historical/1",
            headers={"Authorization": f"Bearer {free_user_token}"}
        )
        assert response_free.status_code == 403

        # Premium user should have access
        response_premium = await async_client.get(
            "/api/v1/prospects/historical/1",
            headers={"Authorization": f"Bearer {premium_user_token}"}
        )
        assert response_premium.status_code in [200, 404]  # 404 if prospect doesn't exist