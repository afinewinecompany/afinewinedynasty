"""
Integration tests for the complete prospect comparison workflow.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.main import app
from app.db.database import get_db
from app.db.models import Base, User, Prospect, ProspectStats, ScoutingGrades, MLPrediction


# Test database URL (use in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create a test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide the session
    async with async_session() as session:
        yield session

    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_client(test_db):
    """Create a test client with database dependency override."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(test_db):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashedpassword",
        is_active=True,
        subscription_tier="premium"
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
async def sample_prospects_db(test_db):
    """Create sample prospects in the database."""
    prospects = [
        Prospect(
            mlb_id="test001",
            name="Alex Rodriguez",
            position="SS",
            organization="New York Yankees",
            level="AA",
            age=22,
            eta_year=2025,
            draft_year=2022,
            draft_round=1,
            draft_pick=15
        ),
        Prospect(
            mlb_id="test002",
            name="Mike Trout",
            position="OF",
            organization="Los Angeles Angels",
            level="AAA",
            age=24,
            eta_year=2024,
            draft_year=2020,
            draft_round=2,
            draft_pick=42
        ),
        Prospect(
            mlb_id="test003",
            name="Jacob deGrom",
            position="SP",
            organization="New York Mets",
            level="AA",
            age=23,
            eta_year=2025,
            draft_year=2021,
            draft_round=1,
            draft_pick=8
        )
    ]

    for prospect in prospects:
        test_db.add(prospect)

    await test_db.commit()

    # Refresh to get IDs
    for prospect in prospects:
        await test_db.refresh(prospect)

    return prospects


@pytest.fixture
async def sample_stats_db(test_db, sample_prospects_db):
    """Create sample prospect stats in the database."""
    stats = [
        # Stats for Alex Rodriguez (hitter)
        ProspectStats(
            prospect_id=sample_prospects_db[0].id,
            date_recorded="2024-06-01",
            level="AA",
            games=50,
            batting_avg=0.285,
            on_base_pct=0.365,
            slugging_pct=0.485,
            wrc_plus=125,
            strikeout_rate=22.5,
            walk_rate=8.2
        ),
        # Stats for Mike Trout (hitter)
        ProspectStats(
            prospect_id=sample_prospects_db[1].id,
            date_recorded="2024-06-01",
            level="AAA",
            games=45,
            batting_avg=0.315,
            on_base_pct=0.395,
            slugging_pct=0.545,
            wrc_plus=145,
            strikeout_rate=18.5,
            walk_rate=12.1
        ),
        # Stats for Jacob deGrom (pitcher)
        ProspectStats(
            prospect_id=sample_prospects_db[2].id,
            date_recorded="2024-06-01",
            level="AA",
            games=12,
            era=2.45,
            whip=1.05,
            k_per_9=11.2,
            bb_per_9=2.1,
            fip=2.89
        )
    ]

    for stat in stats:
        test_db.add(stat)

    await test_db.commit()
    return stats


@pytest.fixture
async def sample_scouting_grades_db(test_db, sample_prospects_db):
    """Create sample scouting grades in the database."""
    grades = [
        ScoutingGrades(
            prospect_id=sample_prospects_db[0].id,
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
            prospect_id=sample_prospects_db[1].id,
            source="Fangraphs",
            overall=65,
            future_value=70,
            hit=70,
            power=60,
            speed=55,
            field=60,
            arm=60
        ),
        ScoutingGrades(
            prospect_id=sample_prospects_db[2].id,
            source="Fangraphs",
            overall=60,
            future_value=65,
            hit=65,  # Command for pitchers
            power=70,  # Stuff for pitchers
            speed=50,  # Durability
            field=60,  # Control
            arm=55   # Delivery
        )
    ]

    for grade in grades:
        test_db.add(grade)

    await test_db.commit()
    return grades


@pytest.fixture
async def sample_ml_predictions_db(test_db, sample_prospects_db):
    """Create sample ML predictions in the database."""
    predictions = [
        MLPrediction(
            prospect_id=sample_prospects_db[0].id,
            prediction_type="success_rating",
            success_probability=0.72,
            confidence_level="High",
            feature_importance={
                "age": 0.15,
                "level": 0.12,
                "batting_avg": 0.25,
                "on_base_pct": 0.18,
                "slugging_pct": 0.20,
                "overall_grade": 0.10
            },
            narrative="Strong offensive profile with excellent contact skills and developing power.",
            model_version="v2.1"
        ),
        MLPrediction(
            prospect_id=sample_prospects_db[1].id,
            prediction_type="success_rating",
            success_probability=0.85,
            confidence_level="High",
            feature_importance={
                "age": 0.12,
                "level": 0.15,
                "batting_avg": 0.22,
                "on_base_pct": 0.20,
                "slugging_pct": 0.23,
                "overall_grade": 0.08
            },
            narrative="Elite prospect with exceptional hitting ability and power potential.",
            model_version="v2.1"
        ),
        MLPrediction(
            prospect_id=sample_prospects_db[2].id,
            prediction_type="success_rating",
            success_probability=0.78,
            confidence_level="Medium",
            feature_importance={
                "age": 0.14,
                "level": 0.10,
                "era": 0.25,
                "whip": 0.20,
                "k_per_9": 0.23,
                "overall_grade": 0.08
            },
            narrative="High-upside pitcher with excellent strikeout stuff and developing command.",
            model_version="v2.1"
        )
    ]

    for prediction in predictions:
        test_db.add(prediction)

    await test_db.commit()
    return predictions


class TestComparisonWorkflowIntegration:
    """Integration tests for the complete comparison workflow."""

    @pytest.mark.asyncio
    async def test_complete_hitter_comparison_workflow(
        self, test_client, test_user, sample_prospects_db,
        sample_stats_db, sample_scouting_grades_db, sample_ml_predictions_db
    ):
        """Test complete workflow for comparing hitters."""
        # Mock authentication
        with patch('app.api.deps.get_current_user', return_value=test_user):
            # Get the first two prospects (both hitters)
            prospect_ids = f"{sample_prospects_db[0].id},{sample_prospects_db[1].id}"

            # Test comparison endpoint
            response = test_client.get(
                "/api/prospects/compare",
                params={
                    "prospect_ids": prospect_ids,
                    "include_stats": "true",
                    "include_predictions": "true",
                    "include_analogs": "true"
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert "prospect_ids" in data
            assert "prospects" in data
            assert "comparison_metadata" in data
            assert len(data["prospects"]) == 2

            # Verify prospect data
            for prospect in data["prospects"]:
                assert "dynasty_metrics" in prospect
                assert "stats" in prospect
                assert "ml_prediction" in prospect
                assert "scouting_grades" in prospect

                # Verify batting stats (not pitching)
                stats = prospect["stats"]
                assert "batting_avg" in stats
                assert "on_base_pct" in stats
                assert "slugging_pct" in stats
                assert "era" not in stats  # Should not have pitching stats

            # Verify ML comparison analysis
            if "ml_comparison" in data:
                ml_comp = data["ml_comparison"]
                assert "prediction_comparison" in ml_comp

            # Verify statistical comparison
            if "statistical_comparison" in data:
                stat_comp = data["statistical_comparison"]
                assert "metric_leaders" in stat_comp

    @pytest.mark.asyncio
    async def test_complete_pitcher_comparison_workflow(
        self, test_client, test_user, sample_prospects_db,
        sample_stats_db, sample_scouting_grades_db, sample_ml_predictions_db
    ):
        """Test complete workflow for comparing pitchers."""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            # Compare pitcher with hitter to test mixed positions
            prospect_ids = f"{sample_prospects_db[1].id},{sample_prospects_db[2].id}"

            response = test_client.get(
                "/api/prospects/compare",
                params={
                    "prospect_ids": prospect_ids,
                    "include_stats": "true",
                    "include_predictions": "true",
                    "include_analogs": "true"
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify mixed position comparison works
            assert len(data["prospects"]) == 2

            # Check that each prospect has appropriate stats
            for prospect in data["prospects"]:
                if prospect["position"] == "SP":
                    # Pitcher should have pitching stats
                    stats = prospect["stats"]
                    assert "era" in stats
                    assert "whip" in stats
                    assert "k_per_9" in stats
                elif prospect["position"] == "OF":
                    # Hitter should have batting stats
                    stats = prospect["stats"]
                    assert "batting_avg" in stats
                    assert "on_base_pct" in stats

    @pytest.mark.asyncio
    async def test_comparison_caching_workflow(
        self, test_client, test_user, sample_prospects_db,
        sample_stats_db, sample_scouting_grades_db, sample_ml_predictions_db
    ):
        """Test that comparison results are properly cached."""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            prospect_ids = f"{sample_prospects_db[0].id},{sample_prospects_db[1].id}"

            # First request - should compute and cache
            response1 = test_client.get(
                "/api/prospects/compare",
                params={"prospect_ids": prospect_ids}
            )

            assert response1.status_code == 200
            data1 = response1.json()

            # Second request - should use cache (verify by checking response time)
            response2 = test_client.get(
                "/api/prospects/compare",
                params={"prospect_ids": prospect_ids}
            )

            assert response2.status_code == 200
            data2 = response2.json()

            # Results should be identical
            assert data1["prospect_ids"] == data2["prospect_ids"]
            assert len(data1["prospects"]) == len(data2["prospects"])

    @pytest.mark.asyncio
    async def test_analog_comparison_workflow(
        self, test_client, test_user, sample_prospects_db
    ):
        """Test historical analog comparison workflow."""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            prospect_ids = f"{sample_prospects_db[0].id},{sample_prospects_db[1].id}"

            response = test_client.get(
                "/api/prospects/compare/analogs",
                params={
                    "prospect_ids": prospect_ids,
                    "limit": "3"
                }
            )

            assert response.status_code == 200
            data = response.json()

            assert "prospect_analogs" in data
            assert "metadata" in data
            assert data["metadata"]["analogs_per_prospect"] == 3

            # Verify structure for each prospect
            for analog_data in data["prospect_analogs"]:
                assert "prospect_id" in analog_data
                assert "prospect_name" in analog_data
                assert "historical_analogs" in analog_data

    @pytest.mark.asyncio
    async def test_export_workflow(
        self, test_client, test_user, sample_prospects_db,
        sample_stats_db, sample_scouting_grades_db, sample_ml_predictions_db
    ):
        """Test comparison export workflow."""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            with patch('app.services.export_service.ExportService.validate_export_access'):
                with patch('app.services.export_service.ExportService.generate_comparison_csv', return_value="csv,data"):
                    prospect_ids = f"{sample_prospects_db[0].id},{sample_prospects_db[1].id}"

                    response = test_client.post(
                        "/api/prospects/compare/export",
                        data={
                            "prospect_ids": prospect_ids,
                            "format": "csv"
                        }
                    )

                    assert response.status_code == 200
                    data = response.json()

                    assert data["format"] == "csv"
                    assert "download_url" in data
                    assert "filename" in data
                    assert "generated_at" in data

    @pytest.mark.asyncio
    async def test_performance_comparison_workflow(
        self, test_client, test_user, sample_prospects_db,
        sample_stats_db, sample_scouting_grades_db, sample_ml_predictions_db
    ):
        """Test that comparison workflow performs within acceptable limits."""
        import time

        with patch('app.api.deps.get_current_user', return_value=test_user):
            prospect_ids = f"{sample_prospects_db[0].id},{sample_prospects_db[1].id},{sample_prospects_db[2].id}"

            start_time = time.time()

            response = test_client.get(
                "/api/prospects/compare",
                params={
                    "prospect_ids": prospect_ids,
                    "include_stats": "true",
                    "include_predictions": "true",
                    "include_analogs": "true"
                }
            )

            end_time = time.time()
            response_time = end_time - start_time

            assert response.status_code == 200

            # Verify performance requirement (< 2 seconds)
            assert response_time < 2.0, f"Response took {response_time:.2f} seconds, expected < 2.0"

            # Verify data completeness for 3-prospect comparison
            data = response.json()
            assert len(data["prospects"]) == 3

    @pytest.mark.asyncio
    async def test_error_handling_workflow(
        self, test_client, test_user
    ):
        """Test error handling throughout the comparison workflow."""
        with patch('app.api.deps.get_current_user', return_value=test_user):
            # Test with non-existent prospects
            response = test_client.get(
                "/api/prospects/compare",
                params={"prospect_ids": "999,998"}
            )

            assert response.status_code == 404

            # Test with invalid format
            response = test_client.get(
                "/api/prospects/compare",
                params={"prospect_ids": "invalid,format"}
            )

            assert response.status_code == 400

            # Test with insufficient prospects
            response = test_client.get(
                "/api/prospects/compare",
                params={"prospect_ids": "1"}
            )

            assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__])