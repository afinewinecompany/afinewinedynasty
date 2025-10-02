"""
Tests for prospect comparison API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import Mock, patch, AsyncMock

from app.main import app
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction, User


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=AsyncSession)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return User(
        id=1,
        email="test@example.com",
        is_active=True,
        subscription_tier="premium"
    )


@pytest.fixture
def sample_prospects():
    """Sample prospect data for testing."""
    return [
        Prospect(
            id=1,
            mlb_id="test1",
            name="John Smith",
            position="SS",
            organization="Team A",
            level="AA",
            age=22,
            eta_year=2025,
            draft_year=2022,
            draft_round=1
        ),
        Prospect(
            id=2,
            mlb_id="test2",
            name="Mike Johnson",
            position="OF",
            organization="Team B",
            level="AAA",
            age=24,
            eta_year=2024,
            draft_year=2020,
            draft_round=3
        )
    ]


@pytest.fixture
def sample_stats():
    """Sample prospect stats for testing."""
    return [
        ProspectStats(
            id=1,
            prospect_id=1,
            date_recorded="2024-06-01",
            level="AA",
            batting_avg=0.285,
            on_base_pct=0.365,
            slugging_pct=0.485,
            wrc_plus=125,
            strikeout_rate=22.5,
            walk_rate=8.2
        ),
        ProspectStats(
            id=2,
            prospect_id=2,
            date_recorded="2024-06-01",
            level="AAA",
            batting_avg=0.305,
            on_base_pct=0.385,
            slugging_pct=0.525,
            wrc_plus=135,
            strikeout_rate=18.5,
            walk_rate=10.1
        )
    ]


@pytest.fixture
def sample_scouting_grades():
    """Sample scouting grades for testing."""
    return [
        ScoutingGrades(
            id=1,
            prospect_id=1,
            source="Fangraphs",
            overall=55,
            future_value=60,
            hit=60,
            power=50,
            speed=65,
            field=55,
            arm=55
        ),
        ScoutingGrades(
            id=2,
            prospect_id=2,
            source="Fangraphs",
            overall=60,
            future_value=65,
            hit=65,
            power=55,
            speed=50,
            field=60,
            arm=60
        )
    ]


@pytest.fixture
def sample_ml_predictions():
    """Sample ML predictions for testing."""
    return [
        MLPrediction(
            id=1,
            prospect_id=1,
            prediction_type="success_rating",
            success_probability=0.72,
            confidence_level="High",
            feature_importance={"age": 0.15, "level": 0.12, "batting_avg": 0.25},
            narrative="Strong offensive profile with good contact skills",
            model_version="v2.1"
        ),
        MLPrediction(
            id=2,
            prospect_id=2,
            prediction_type="success_rating",
            success_probability=0.68,
            confidence_level="Medium",
            feature_importance={"age": 0.18, "level": 0.14, "batting_avg": 0.22},
            narrative="Solid all-around prospect with power upside",
            model_version="v2.1"
        )
    ]


class TestProspectComparison:
    """Test prospect comparison endpoints."""

    @pytest.mark.asyncio
    async def test_compare_prospects_success(self, client, mock_db, mock_user,
                                           sample_prospects, sample_stats,
                                           sample_scouting_grades, sample_ml_predictions):
        """Test successful prospect comparison."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            with patch('app.api.deps.get_db', return_value=mock_db):
                with patch('app.services.prospect_comparisons_service.ProspectComparisonsService._get_prospect_with_features') as mock_get_features:
                    # Mock the prospect features data
                    mock_get_features.side_effect = [
                        {
                            "prospect": sample_prospects[0],
                            "latest_stats": sample_stats[0],
                            "scouting_grade": sample_scouting_grades[0],
                            "ml_prediction": sample_ml_predictions[0],
                            "features": [22, 4, 0.285, 0.365, 0.485, 125, 22.5, 8.2, 0, 0, 0, 0, 55, 60, 0.72]
                        },
                        {
                            "prospect": sample_prospects[1],
                            "latest_stats": sample_stats[1],
                            "scouting_grade": sample_scouting_grades[1],
                            "ml_prediction": sample_ml_predictions[1],
                            "features": [24, 5, 0.305, 0.385, 0.525, 135, 18.5, 10.1, 0, 0, 0, 0, 60, 65, 0.68]
                        }
                    ]

                    with patch('app.core.cache_manager.cache_manager.get_cached_features', return_value=None):
                        with patch('app.core.cache_manager.cache_manager.cache_prospect_features') as mock_cache:
                            response = client.get(
                                "/api/prospects/compare",
                                params={
                                    "prospect_ids": "1,2",
                                    "include_stats": "true",
                                    "include_predictions": "true",
                                    "include_analogs": "true"
                                },
                                headers={"Authorization": "Bearer test_token"}
                            )

                            assert response.status_code == 200
                            data = response.json()

                            assert data["prospect_ids"] == [1, 2]
                            assert len(data["prospects"]) == 2
                            assert data["comparison_metadata"]["prospects_count"] == 2

                            # Verify prospect data structure
                            prospect = data["prospects"][0]
                            assert prospect["name"] == "John Smith"
                            assert prospect["position"] == "SS"
                            assert "dynasty_metrics" in prospect
                            assert "stats" in prospect

    def test_compare_prospects_invalid_ids(self, client, mock_user):
        """Test comparison with invalid prospect IDs."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            response = client.get(
                "/api/prospects/compare",
                params={"prospect_ids": "invalid,ids"},
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 400
            assert "Invalid prospect ID format" in response.json()["detail"]

    def test_compare_prospects_insufficient_count(self, client, mock_user):
        """Test comparison with insufficient prospect count."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            response = client.get(
                "/api/prospects/compare",
                params={"prospect_ids": "1"},
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 400
            assert "Must compare between 2-4 prospects" in response.json()["detail"]

    def test_compare_prospects_too_many(self, client, mock_user):
        """Test comparison with too many prospects."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            response = client.get(
                "/api/prospects/compare",
                params={"prospect_ids": "1,2,3,4,5"},
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 400
            assert "Must compare between 2-4 prospects" in response.json()["detail"]

    def test_compare_prospects_not_found(self, client, mock_user, mock_db):
        """Test comparison with non-existent prospects."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            with patch('app.api.deps.get_db', return_value=mock_db):
                with patch('app.services.prospect_comparisons_service.ProspectComparisonsService._get_prospect_with_features', return_value=None):
                    response = client.get(
                        "/api/prospects/compare",
                        params={"prospect_ids": "999,998"},
                        headers={"Authorization": "Bearer test_token"}
                    )

                    assert response.status_code == 404
                    assert "not found" in response.json()["detail"]

    def test_compare_prospects_cached_result(self, client, mock_user, mock_db):
        """Test comparison returns cached result when available."""
        cached_data = {
            "prospect_ids": [1, 2],
            "prospects": [],
            "comparison_metadata": {"prospects_count": 2}
        }

        with patch('app.api.deps.get_current_user', return_value=mock_user):
            with patch('app.api.deps.get_db', return_value=mock_db):
                with patch('app.core.cache_manager.cache_manager.get_cached_features', return_value=cached_data):
                    response = client.get(
                        "/api/prospects/compare",
                        params={"prospect_ids": "1,2"},
                        headers={"Authorization": "Bearer test_token"}
                    )

                    assert response.status_code == 200
                    assert response.json() == cached_data

    @pytest.mark.asyncio
    async def test_get_comparison_analogs(self, client, mock_user, mock_db, sample_prospects):
        """Test historical analogs endpoint."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            with patch('app.api.deps.get_db', return_value=mock_db):
                with patch('app.services.prospect_comparisons_service.ProspectComparisonsService._get_prospect_with_features') as mock_get_features:
                    with patch('app.services.prospect_comparisons_service.ProspectComparisonsService._find_historical_similar') as mock_find_similar:
                        mock_get_features.return_value = {
                            "prospect": sample_prospects[0],
                            "features": []
                        }
                        mock_find_similar.return_value = [
                            {
                                "player_name": "Francisco Lindor",
                                "similarity_score": 0.875,
                                "age_at_similar_level": 22,
                                "mlb_outcome": {
                                    "reached_mlb": True,
                                    "peak_war": 41.4,
                                    "all_star_appearances": 4
                                }
                            }
                        ]

                        response = client.get(
                            "/api/prospects/compare/analogs",
                            params={"prospect_ids": "1", "limit": "3"},
                            headers={"Authorization": "Bearer test_token"}
                        )

                        assert response.status_code == 200
                        data = response.json()

                        assert "prospect_analogs" in data
                        assert data["metadata"]["analogs_per_prospect"] == 3

    def test_export_comparison_pdf(self, client, mock_user):
        """Test PDF export functionality."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            with patch('app.services.export_service.ExportService.validate_export_access'):
                with patch('app.services.export_service.ExportService.generate_comparison_pdf', return_value=b"pdf_content"):
                    with patch('app.api.api_v1.endpoints.prospects.compare_prospects') as mock_compare:
                        mock_compare.return_value = {"prospects": []}

                        response = client.post(
                            "/api/prospects/compare/export",
                            data={"prospect_ids": "1,2", "format": "pdf"},
                            headers={"Authorization": "Bearer test_token"}
                        )

                        assert response.status_code == 200
                        data = response.json()

                        assert data["format"] == "pdf"
                        assert "download_url" in data
                        assert "filename" in data

    def test_export_comparison_csv(self, client, mock_user):
        """Test CSV export functionality."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            with patch('app.services.export_service.ExportService.validate_export_access'):
                with patch('app.services.export_service.ExportService.generate_comparison_csv', return_value="csv,content"):
                    with patch('app.api.api_v1.endpoints.prospects.compare_prospects') as mock_compare:
                        mock_compare.return_value = {"prospects": []}

                        response = client.post(
                            "/api/prospects/compare/export",
                            data={"prospect_ids": "1,2", "format": "csv"},
                            headers={"Authorization": "Bearer test_token"}
                        )

                        assert response.status_code == 200
                        data = response.json()

                        assert data["format"] == "csv"
                        assert "download_url" in data
                        assert "filename" in data

    def test_export_comparison_invalid_format(self, client, mock_user):
        """Test export with invalid format."""
        with patch('app.api.deps.get_current_user', return_value=mock_user):
            response = client.post(
                "/api/prospects/compare/export",
                data={"prospect_ids": "1,2", "format": "invalid"},
                headers={"Authorization": "Bearer test_token"}
            )

            assert response.status_code == 422  # Validation error


class TestProspectComparisonService:
    """Test prospect comparison service functionality."""

    @pytest.mark.asyncio
    async def test_compare_multiple_prospects(self, mock_db):
        """Test multi-prospect comparison service method."""
        from app.services.prospect_comparisons_service import ProspectComparisonsService

        with patch.object(ProspectComparisonsService, '_get_prospect_with_features') as mock_get_features:
            with patch('app.core.cache_manager.cache_manager.get_cached_features', return_value=None):
                with patch('app.core.cache_manager.cache_manager.cache_prospect_features') as mock_cache:
                    mock_get_features.side_effect = [
                        {"prospect": Mock(id=1, name="Test 1"), "features": [1, 2, 3]},
                        {"prospect": Mock(id=2, name="Test 2"), "features": [2, 3, 4]}
                    ]

                    result = await ProspectComparisonsService.compare_multiple_prospects(
                        mock_db, [1, 2], include_analytics=True
                    )

                    assert result["prospect_ids"] == [1, 2]
                    assert len(result["comparison_matrix"]) == 1  # One pairwise comparison
                    assert "group_analytics" in result

    @pytest.mark.asyncio
    async def test_compare_multiple_prospects_invalid_count(self, mock_db):
        """Test service validation for invalid prospect count."""
        from app.services.prospect_comparisons_service import ProspectComparisonsService

        with pytest.raises(ValueError, match="Must compare between 2-4 prospects"):
            await ProspectComparisonsService.compare_multiple_prospects(mock_db, [1])

        with pytest.raises(ValueError, match="Must compare between 2-4 prospects"):
            await ProspectComparisonsService.compare_multiple_prospects(mock_db, [1, 2, 3, 4, 5])

    def test_similarity_calculation(self):
        """Test similarity calculation between prospects."""
        from app.services.prospect_comparisons_service import ProspectComparisonsService
        import numpy as np

        features1 = np.array([22, 4, 0.285, 0.365, 0.485, 125, 22.5, 8.2, 0, 0, 0, 0, 55, 60, 0.72])
        features2 = np.array([24, 5, 0.305, 0.385, 0.525, 135, 18.5, 10.1, 0, 0, 0, 0, 60, 65, 0.68])

        similarity = ProspectComparisonsService._calculate_similarity(features1, features2)

        assert 0 <= similarity <= 1
        assert isinstance(similarity, float)

    def test_matching_features_identification(self):
        """Test identification of matching features between prospects."""
        from app.services.prospect_comparisons_service import ProspectComparisonsService
        import numpy as np

        features1 = np.array([22, 4, 0.285, 0.365, 0.485, 125, 22.5, 8.2, 0, 0, 0, 0, 55, 60, 0.72])
        features2 = np.array([22, 4, 0.290, 0.370, 0.490, 120, 23.0, 8.0, 0, 0, 0, 0, 55, 60, 0.70])

        matching = ProspectComparisonsService._get_matching_features(features1, features2)

        assert isinstance(matching, list)
        # Should find age and level as matching (exactly the same)
        assert "age" in matching
        assert "level" in matching


if __name__ == "__main__":
    pytest.main([__file__])