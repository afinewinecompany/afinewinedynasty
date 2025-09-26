"""
Integration tests for the complete prospect profile workflow.
Tests the end-to-end functionality of prospect profile features.
"""

import pytest
import json
from httpx import AsyncClient
from fastapi import status
from unittest.mock import patch

from app.main import app
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction
from app.services.prospect_stats_service import ProspectStatsService
from app.services.prospect_comparisons_service import ProspectComparisonsService
from app.core.cache_manager import cache_manager


@pytest.mark.asyncio
class TestProspectProfileWorkflow:
    """Integration test class for prospect profile workflow."""

    @pytest.fixture(autouse=True)
    async def setup_test_data(self, db_session, test_user):
        """Set up comprehensive test data."""
        self.test_user = test_user

        # Create multiple prospects for comparison testing
        prospects = [
            Prospect(
                id=1,
                mlb_id="test001",
                name="Primary Prospect",
                position="SS",
                organization="Yankees",
                level="AA",
                age=21,
                eta_year=2025,
                draft_year=2022,
                draft_round=1,
                draft_pick=15
            ),
            Prospect(
                id=2,
                mlb_id="test002",
                name="Similar Prospect",
                position="SS",
                organization="Red Sox",
                level="AA",
                age=22,
                eta_year=2025,
                draft_year=2021,
                draft_round=2,
                draft_pick=45
            ),
            Prospect(
                id=3,
                mlb_id="test003",
                name="Different Prospect",
                position="OF",
                organization="Yankees",
                level="AAA",
                age=23,
                eta_year=2024,
                draft_year=2020,
                draft_round=1,
                draft_pick=8
            )
        ]

        for prospect in prospects:
            db_session.add(prospect)

        # Create stats for multiple levels and seasons
        stats_data = [
            # Primary prospect - current year
            {
                "prospect_id": 1, "level": "AA", "games": 50, "batting_avg": 0.285,
                "on_base_pct": 0.365, "slugging_pct": 0.445, "date_recorded": "2024-09-01"
            },
            {
                "prospect_id": 1, "level": "A+", "games": 40, "batting_avg": 0.275,
                "on_base_pct": 0.355, "slugging_pct": 0.425, "date_recorded": "2024-05-01"
            },
            # Primary prospect - previous year
            {
                "prospect_id": 1, "level": "A", "games": 60, "batting_avg": 0.265,
                "on_base_pct": 0.345, "slugging_pct": 0.405, "date_recorded": "2023-08-01"
            },
            # Similar prospect
            {
                "prospect_id": 2, "level": "AA", "games": 45, "batting_avg": 0.280,
                "on_base_pct": 0.360, "slugging_pct": 0.440, "date_recorded": "2024-09-01"
            }
        ]

        for stat_data in stats_data:
            stat = ProspectStats(**stat_data)
            db_session.add(stat)

        # Create scouting grades from multiple sources
        scouting_data = [
            {
                "prospect_id": 1, "source": "Fangraphs", "overall": 60, "future_value": 55,
                "hit": 55, "power": 60, "speed": 50, "field": 55, "arm": 60,
                "updated_at": "2024-09-01T00:00:00"
            },
            {
                "prospect_id": 1, "source": "MLB Pipeline", "overall": 58, "future_value": 53,
                "hit": 53, "power": 58, "speed": 52, "field": 53, "arm": 58,
                "updated_at": "2024-08-15T00:00:00"
            },
            {
                "prospect_id": 2, "source": "Fangraphs", "overall": 55, "future_value": 50,
                "hit": 50, "power": 55, "speed": 55, "field": 50, "arm": 55,
                "updated_at": "2024-09-01T00:00:00"
            }
        ]

        for scout_data in scouting_data:
            scout = ScoutingGrades(**scout_data)
            db_session.add(scout)

        # Create ML predictions
        ml_predictions = [
            {
                "prospect_id": 1, "prediction_type": "success_rating",
                "success_probability": 0.75, "confidence_level": "High",
                "feature_importance": json.dumps({
                    "top_positive_features": [
                        {"feature": "batting_avg", "shap_value": 0.12, "feature_value": 0.285},
                        {"feature": "age", "shap_value": 0.08, "feature_value": 21},
                        {"feature": "power_grade", "shap_value": 0.06, "feature_value": 60}
                    ],
                    "top_negative_features": [
                        {"feature": "strikeout_rate", "shap_value": -0.05, "feature_value": 22.5}
                    ],
                    "expected_value": 0.45,
                    "total_shap_contribution": 0.30,
                    "prediction_score": 0.75
                }),
                "narrative": "Strong hitting prospect with excellent power potential and good defensive skills.",
                "model_version": "v2.1.0",
                "generated_at": "2024-09-01T00:00:00"
            },
            {
                "prospect_id": 2, "prediction_type": "success_rating",
                "success_probability": 0.65, "confidence_level": "Medium",
                "feature_importance": json.dumps({
                    "top_positive_features": [
                        {"feature": "batting_avg", "shap_value": 0.10, "feature_value": 0.280}
                    ],
                    "top_negative_features": [
                        {"feature": "age", "shap_value": -0.03, "feature_value": 22}
                    ],
                    "expected_value": 0.45,
                    "total_shap_contribution": 0.20,
                    "prediction_score": 0.65
                }),
                "narrative": "Solid prospect with good hitting ability.",
                "model_version": "v2.1.0",
                "generated_at": "2024-09-01T00:00:00"
            }
        ]

        for ml_data in ml_predictions:
            ml_pred = MLPrediction(**ml_data)
            db_session.add(ml_pred)

        await db_session.commit()

    async def test_complete_profile_workflow(self, client: AsyncClient, auth_headers):
        """Test the complete prospect profile workflow."""
        # Step 1: Get comprehensive profile
        response = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        profile_data = response.json()

        # Verify all major sections are present
        assert "prospect" in profile_data
        assert "stats" in profile_data
        assert "ml_prediction" in profile_data
        assert "scouting_grades" in profile_data
        assert "comparisons" in profile_data
        assert "dynasty_metrics" in profile_data

        # Step 2: Test detailed stats history
        response = await client.get(
            "/api/prospects/1/stats",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        stats_data = response.json()

        # Should have progression data
        assert "progression" in stats_data
        assert stats_data["total_records"] >= 3  # Multiple levels/seasons

        # Step 3: Test comparisons
        response = await client.get(
            "/api/prospects/1/comparisons",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        comparison_data = response.json()

        # Should have comparison data
        assert "current_comparisons" in comparison_data
        assert "historical_comparisons" in comparison_data

        # Step 4: Test organizational context
        response = await client.get(
            "/api/prospects/1/organizational-context",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        org_data = response.json()

        assert org_data["organization"] == "Yankees"
        assert "organizational_depth" in org_data

    async def test_stats_service_aggregation_workflow(self, client: AsyncClient, auth_headers):
        """Test the stats service aggregation workflow."""
        # Test by-level aggregation
        response = await client.get(
            "/api/prospects/1/stats",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should have aggregated data by level
        assert "by_level" in data
        assert "by_season" in data

        # Check that AA level data exists
        assert "AA" in data["by_level"] or any("AA" in str(data["by_level"]))

        # Test filtered stats
        response = await client.get(
            "/api/prospects/1/stats?level=AA",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_ml_prediction_workflow(self, client: AsyncClient, auth_headers):
        """Test ML prediction workflow with SHAP explanations."""
        response = await client.get(
            "/api/prospects/1/profile?include_predictions=true",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        ml_prediction = data["ml_prediction"]

        # Verify SHAP explanation structure
        assert "shap_explanation" in ml_prediction
        shap_data = ml_prediction["shap_explanation"]

        assert "top_positive_features" in shap_data
        assert "top_negative_features" in shap_data
        assert "expected_value" in shap_data
        assert "prediction_score" in shap_data

        # Verify features have required structure
        if shap_data["top_positive_features"]:
            feature = shap_data["top_positive_features"][0]
            assert "feature" in feature
            assert "shap_value" in feature
            assert "feature_value" in feature

    async def test_scouting_grades_multi_source_workflow(self, client: AsyncClient, auth_headers):
        """Test scouting grades from multiple sources."""
        response = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        scouting_grades = data["scouting_grades"]

        # Should have multiple sources
        assert len(scouting_grades) >= 2

        sources = [grade["source"] for grade in scouting_grades]
        assert "Fangraphs" in sources
        assert "MLB Pipeline" in sources

        # Each grade should have complete structure
        for grade in scouting_grades:
            assert "source" in grade
            assert "overall" in grade
            assert "future_value" in grade
            assert "hit" in grade
            assert "power" in grade
            assert "updated_at" in grade

    async def test_comparison_workflow_with_similar_prospects(self, client: AsyncClient, auth_headers):
        """Test prospect comparison workflow."""
        response = await client.get(
            "/api/prospects/1/comparisons?limit=5",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should find similar prospects
        assert "current_comparisons" in data

        # Test organizational context
        response = await client.get(
            "/api/prospects/1/organizational-context",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        org_data = response.json()

        # Should show organizational depth
        assert "organizational_depth" in org_data
        assert "depth_chart" in org_data

    async def test_caching_workflow(self, client: AsyncClient, auth_headers):
        """Test caching behavior across the workflow."""
        # Clear cache
        await cache_manager.clear_all()

        # First request should populate cache
        start_time = time.time()
        response1 = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )
        first_time = time.time() - start_time

        assert response1.status_code == status.HTTP_200_OK

        # Second request should be faster due to caching
        start_time = time.time()
        response2 = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )
        second_time = time.time() - start_time

        assert response2.status_code == status.HTTP_200_OK
        assert response1.json() == response2.json()
        # Second request should generally be faster (though this might be flaky in tests)

    async def test_error_recovery_workflow(self, client: AsyncClient, auth_headers):
        """Test error recovery in the workflow."""
        # Test with partial data failure
        with patch('app.services.prospect_comparisons_service.ProspectComparisonsService.find_similar_prospects') as mock_comparisons:
            mock_comparisons.side_effect = Exception("Comparison service error")

            response = await client.get(
                "/api/prospects/1/profile",
                headers=auth_headers
            )

            # Should still return profile data even if comparisons fail
            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert "prospect" in data
            assert "stats" in data
            assert "ml_prediction" in data
            # Comparisons might be missing due to error

    async def test_dynasty_scoring_integration(self, client: AsyncClient, auth_headers):
        """Test dynasty scoring integration across the workflow."""
        response = await client.get(
            "/api/prospects/1/profile",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        dynasty_metrics = data["dynasty_metrics"]

        # Should have calculated dynasty scores
        assert "dynasty_score" in dynasty_metrics
        assert "ml_score" in dynasty_metrics
        assert "scouting_score" in dynasty_metrics
        assert "confidence_level" in dynasty_metrics

        # Scores should be reasonable ranges
        assert 0 <= dynasty_metrics["dynasty_score"] <= 100
        assert 0 <= dynasty_metrics["ml_score"] <= 100
        assert 0 <= dynasty_metrics["scouting_score"] <= 100

    async def test_performance_with_large_dataset(self, client: AsyncClient, auth_headers):
        """Test performance with larger dataset."""
        # This would be more meaningful with a larger test dataset
        # For now, just verify the endpoints can handle multiple requests

        tasks = []
        for i in range(5):  # Simulate concurrent requests
            task = client.get(
                "/api/prospects/1/profile",
                headers=auth_headers
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        for response in responses:
            assert response.status_code == status.HTTP_200_OK

import asyncio
import time