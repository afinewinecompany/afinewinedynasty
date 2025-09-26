"""
Test suite for enhanced prospect profile endpoints.
Tests the comprehensive prospect profile API functionality including
SHAP explanations, comparisons, and caching.
"""

import pytest
import json
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch, MagicMock

from app.main import app
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction, User
from app.core.cache_manager import cache_manager


@pytest.mark.asyncio
class TestProspectProfileEndpoints:
    """Test class for prospect profile endpoints."""

    @pytest.fixture(autouse=True)
    async def setup_test_data(self, db_session, test_user):
        """Set up test data for each test."""
        self.test_user = test_user

        # Create test prospect
        self.test_prospect = Prospect(
            id=1,
            mlb_id="test123",
            name="Test Player",
            position="SS",
            organization="Yankees",
            level="AA",
            age=21,
            eta_year=2025,
            draft_year=2022,
            draft_round=1,
            draft_pick=15
        )
        db_session.add(self.test_prospect)

        # Create test stats
        self.test_stats = ProspectStats(
            prospect_id=1,
            level="AA",
            games=50,
            batting_avg=0.285,
            on_base_pct=0.365,
            slugging_pct=0.445,
            home_runs=12,
            rbi=45,
            stolen_bases=8,
            strikeout_rate=22.5,
            walk_rate=9.2,
            woba=0.350,
            wrc_plus=115,
            date_recorded="2024-09-01"
        )
        db_session.add(self.test_stats)

        # Create test scouting grades
        self.test_scouting = ScoutingGrades(
            prospect_id=1,
            source="Fangraphs",
            overall=60,
            future_value=55,
            hit=55,
            power=60,
            speed=50,
            field=55,
            arm=60,
            updated_at="2024-09-01T00:00:00"
        )
        db_session.add(self.test_scouting)

        # Create test ML prediction
        self.test_ml_prediction = MLPrediction(
            prospect_id=1,
            prediction_type="success_rating",
            success_probability=0.75,
            confidence_level="High",
            feature_importance=json.dumps({
                "top_positive_features": [
                    {"feature": "batting_avg", "shap_value": 0.12, "feature_value": 0.285},
                    {"feature": "age", "shap_value": 0.08, "feature_value": 21}
                ],
                "top_negative_features": [
                    {"feature": "strikeout_rate", "shap_value": -0.05, "feature_value": 22.5}
                ],
                "expected_value": 0.45,
                "total_shap_contribution": 0.30,
                "prediction_score": 0.75
            }),
            narrative="Strong hitting prospect with good power potential.",
            model_version="v2.1.0",
            generated_at="2024-09-01T00:00:00"
        )
        db_session.add(self.test_ml_prediction)

        await db_session.commit()

    async def test_get_prospect_profile_comprehensive(self, client: AsyncClient, auth_headers):
        """Test getting comprehensive prospect profile."""
        response = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check basic prospect data
        assert data["prospect"]["id"] == 1
        assert data["prospect"]["name"] == "Test Player"
        assert data["prospect"]["position"] == "SS"
        assert data["prospect"]["organization"] == "Yankees"

        # Check stats data
        assert "stats" in data
        assert data["stats"]["history"]["total_records"] > 0

        # Check ML prediction data
        assert "ml_prediction" in data
        assert data["ml_prediction"]["success_probability"] == 0.75
        assert data["ml_prediction"]["confidence_level"] == "High"
        assert "shap_explanation" in data["ml_prediction"]

        # Check scouting grades
        assert "scouting_grades" in data
        assert len(data["scouting_grades"]) == 1
        assert data["scouting_grades"][0]["source"] == "Fangraphs"
        assert data["scouting_grades"][0]["overall"] == 60

        # Check dynasty metrics
        assert "dynasty_metrics" in data
        assert "dynasty_score" in data["dynasty_metrics"]

    async def test_get_prospect_profile_with_filters(self, client: AsyncClient, auth_headers):
        """Test getting prospect profile with optional filters."""
        response = await client.get(
            "/api/prospects/1/profile?include_stats=false&include_comparisons=false",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have basic prospect data
        assert "prospect" in data

        # Should not have stats or comparisons
        assert "stats" not in data
        assert "comparisons" not in data

        # Should still have ML prediction and scouting
        assert "ml_prediction" in data
        assert "scouting_grades" in data

    async def test_get_prospect_stats_history(self, client: AsyncClient, auth_headers):
        """Test getting prospect stats history."""
        response = await client.get(
            "/api/prospects/1/stats",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["prospect_id"] == 1
        assert data["total_records"] > 0
        assert "by_level" in data
        assert "by_season" in data
        assert "aggregations" in data
        assert "latest_stats" in data

    async def test_get_prospect_stats_history_with_filters(self, client: AsyncClient, auth_headers):
        """Test getting prospect stats history with level and season filters."""
        response = await client.get(
            "/api/prospects/1/stats?level=AA&season=2024&limit=10",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["prospect_id"] == 1
        # Should respect the filters applied

    async def test_get_prospect_comparisons(self, client: AsyncClient, auth_headers):
        """Test getting prospect comparisons."""
        with patch('app.services.prospect_comparisons_service.ProspectComparisonsService.find_similar_prospects') as mock_comparisons:
            mock_comparisons.return_value = {
                "prospect_id": 1,
                "prospect_name": "Test Player",
                "current_comparisons": [
                    {
                        "prospect": {"id": 2, "name": "Similar Player", "organization": "Red Sox"},
                        "similarity_score": 0.85,
                        "matching_features": ["age", "position", "batting_avg"]
                    }
                ],
                "historical_comparisons": []
            }

            response = await client.get(
                "/api/prospects/1/comparisons?limit=5&include_historical=true",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["prospect_id"] == 1
            assert "current_comparisons" in data
            assert len(data["current_comparisons"]) == 1

    async def test_get_organizational_context(self, client: AsyncClient, auth_headers):
        """Test getting organizational context."""
        with patch('app.services.prospect_comparisons_service.ProspectComparisonsService.get_organizational_context') as mock_context:
            mock_context.return_value = {
                "prospect_id": 1,
                "organization": "Yankees",
                "position": "SS",
                "organizational_depth": {
                    "total_at_position": 3,
                    "prospects_ahead": 1,
                    "prospects_behind": 1
                },
                "blocked_status": False
            }

            response = await client.get(
                "/api/prospects/1/organizational-context",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["prospect_id"] == 1
            assert data["organization"] == "Yankees"
            assert "organizational_depth" in data

    async def test_get_injury_history(self, client: AsyncClient, auth_headers):
        """Test getting injury history (placeholder endpoint)."""
        response = await client.get(
            "/api/prospects/1/injury-history",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["prospect_id"] == 1
        assert data["current_status"] == "Healthy"
        assert "injury_history" in data

    async def test_prospect_profile_not_found(self, client: AsyncClient, auth_headers):
        """Test getting profile for non-existent prospect."""
        response = await client.get(
            "/api/prospects/99999/profile",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_prospect_profile_caching(self, client: AsyncClient, auth_headers):
        """Test that prospect profile responses are cached."""
        # Clear cache first
        await cache_manager.clear_all()

        # First request should hit database
        response1 = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second request should hit cache
        with patch('app.services.prospect_stats_service.ProspectStatsService.get_stats_history') as mock_stats:
            response2 = await client.get(
                "/api/prospects/1/profile",
                headers=auth_headers
            )
            assert response2.status_code == status.HTTP_200_OK

            # Stats service should not be called on cached request
            mock_stats.assert_not_called()

    async def test_rate_limiting(self, client: AsyncClient, auth_headers):
        """Test rate limiting on prospect endpoints."""
        # This test would need to be implemented based on your rate limiting setup
        # For now, just test that endpoints respond correctly
        response = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK

    async def test_prospect_profile_authentication_required(self, client: AsyncClient):
        """Test that authentication is required for prospect profile endpoints."""
        response = await client.get("/api/prospects/1/profile")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.parametrize("include_stats,include_predictions,include_comparisons,include_scouting", [
        (True, True, True, True),
        (False, False, False, False),
        (True, False, True, False),
        (False, True, False, True)
    ])
    async def test_prospect_profile_optional_includes(
        self, client: AsyncClient, auth_headers,
        include_stats, include_predictions, include_comparisons, include_scouting
    ):
        """Test prospect profile with different include parameters."""
        params = {
            "include_stats": str(include_stats).lower(),
            "include_predictions": str(include_predictions).lower(),
            "include_comparisons": str(include_comparisons).lower(),
            "include_scouting": str(include_scouting).lower()
        }

        response = await client.get(
            "/api/prospects/1/profile",
            params=params,
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check that included/excluded sections match parameters
        assert ("stats" in data) == include_stats
        assert ("ml_prediction" in data) == include_predictions
        assert ("comparisons" in data) == include_comparisons
        assert ("scouting_grades" in data) == include_scouting

    async def test_multi_level_aggregation(self, client: AsyncClient, auth_headers):
        """Test multi-level statistical aggregation."""
        with patch('app.services.prospect_stats_service.ProspectStatsService.get_multi_level_aggregation') as mock_agg:
            mock_agg.return_value = [
                {
                    "level": "AA",
                    "level_rank": 3,
                    "games": 50,
                    "batting": {"avg": 0.285, "obp": 0.365, "slg": 0.445},
                    "date_range": {"first": "2024-04-01", "last": "2024-09-01"}
                }
            ]

            response = await client.get(
                "/api/prospects/1/stats",
                headers=auth_headers
            )

            assert response.status_code == status.HTTP_200_OK
            mock_agg.assert_called_once()

    async def test_error_handling_in_profile_endpoint(self, client: AsyncClient, auth_headers):
        """Test error handling in profile endpoint when services fail."""
        with patch('app.services.prospect_stats_service.ProspectStatsService.get_stats_history') as mock_stats:
            mock_stats.side_effect = Exception("Database error")

            response = await client.get(
                "/api/prospects/1/profile",
                headers=auth_headers
            )

            # Should still return 200 but without stats data
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "prospect" in data  # Basic data should still be there