"""
Test suite for ChurnPredictionService.

@module test_churn_prediction_service
@since 1.0.0
"""

import pytest
from unittest.mock import AsyncMock
from app.services.churn_prediction_service import ChurnPredictionService


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock()


@pytest.fixture
def churn_service(mock_db):
    """Create ChurnPredictionService instance."""
    return ChurnPredictionService(mock_db)


class TestCalculateChurnRisk:
    """Test suite for calculate_churn_risk."""

    @pytest.mark.asyncio
    async def test_calculate_churn_risk_returns_score(self, churn_service):
        """Test that churn risk score is calculated."""
        risk_score = await churn_service.calculate_churn_risk(user_id=1)

        assert isinstance(risk_score, float)
        assert 0 <= risk_score <= 100

    @pytest.mark.asyncio
    async def test_calculate_churn_risk_bounds(self, churn_service):
        """Test that risk score stays within bounds."""
        risk_score = await churn_service.calculate_churn_risk(user_id=1)

        # Score should never be negative or > 100
        assert risk_score >= 0
        assert risk_score <= 100


class TestGetAtRiskUsers:
    """Test suite for get_at_risk_users."""

    @pytest.mark.asyncio
    async def test_get_at_risk_users_returns_list(self, churn_service):
        """Test that at-risk users list is returned."""
        users = await churn_service.get_at_risk_users(risk_threshold=60)

        assert isinstance(users, list)

    @pytest.mark.asyncio
    async def test_get_at_risk_users_with_different_thresholds(self, churn_service):
        """Test different risk thresholds."""
        high_risk = await churn_service.get_at_risk_users(risk_threshold=80)
        medium_risk = await churn_service.get_at_risk_users(risk_threshold=60)

        assert isinstance(high_risk, list)
        assert isinstance(medium_risk, list)
