"""Tests for discovery API endpoints."""

import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta, date
import json

from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction, User
from app.core.security import create_access_token


class TestDiscoveryEndpoints:
    """Test suite for discovery API endpoints."""

    @pytest.fixture
    async def test_prospects_with_stats(self, db_session):
        """Create test prospects with varied statistical data for discovery testing."""
        prospects = []

        # Create prospects with different performance patterns
        prospect_data = [
            {
                "mlb_id": "disc001",
                "name": "Breakout Candidate",
                "position": "SS",
                "organization": "Test Org A",
                "level": "AA",
                "age": 20,
                "eta_year": 2025
            },
            {
                "mlb_id": "disc002",
                "name": "Sleeper Prospect",
                "position": "SP",
                "organization": "Test Org B",
                "level": "A+",
                "age": 19,
                "eta_year": 2026
            },
            {
                "mlb_id": "disc003",
                "name": "Steady Performer",
                "position": "CF",
                "organization": "Test Org C",
                "level": "AAA",
                "age": 22,
                "eta_year": 2024
            }
        ]

        for i, data in enumerate(prospect_data):
            prospect = Prospect(**data)
            db_session.add(prospect)
            await db_session.flush()
            prospects.append(prospect)

            # Create time-series stats to simulate performance trends
            base_date = datetime.now() - timedelta(days=90)

            for j in range(10):  # 10 data points over 90 days
                stat_date = base_date + timedelta(days=j * 9)

                if i == 0:  # Breakout candidate - improving stats
                    batting_avg = 0.250 + (j * 0.008)  # Improving batting average
                    on_base_pct = 0.300 + (j * 0.006)
                    slugging_pct = 0.400 + (j * 0.010)
                elif i == 1:  # Pitcher with improving ERA (lower is better)
                    era = 4.50 - (j * 0.15)  # Improving ERA
                    whip = 1.40 - (j * 0.02)
                    k9 = 8.0 + (j * 0.2)
                    batting_avg = None
                    on_base_pct = None
                    slugging_pct = None
                else:  # Steady performer
                    batting_avg = 0.285 + (j * 0.001)  # Minimal change
                    on_base_pct = 0.345 + (j * 0.001)
                    slugging_pct = 0.455 + (j * 0.002)

                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date.date(),
                    season=2024,
                    games_played=10,
                    at_bats=40,
                    hits=int(40 * (batting_avg or 0.250)),
                    batting_avg=batting_avg,
                    on_base_pct=on_base_pct,
                    slugging_pct=slugging_pct,
                    era=era if i == 1 else None,
                    whip=whip if i == 1 else None,
                    strikeouts_per_nine=k9 if i == 1 else None,
                    woba=0.340 if batting_avg else None
                )
                db_session.add(stats)

            # Add scouting grades
            grade = ScoutingGrades(
                prospect_id=prospect.id,
                source="Test Scout",
                overall=50 + i * 5,  # Varying grades
                hit=45 + i * 3 if prospect.position not in ['SP', 'RP'] else None,
                power=40 + i * 5 if prospect.position not in ['SP', 'RP'] else None,
                future_value=50 + i * 5,
                risk="Moderate"
            )
            db_session.add(grade)

            # Add ML predictions with varying confidence
            prediction = MLPrediction(
                prospect_id=prospect.id,
                model_version="test_v1",
                prediction_type="success_rating",
                prediction_value=0.60 + i * 0.1,  # Varying success ratings
                confidence_score=0.75 + i * 0.05  # Varying confidence
            )
            db_session.add(prediction)

            # Add career WAR prediction
            war_prediction = MLPrediction(
                prospect_id=prospect.id,
                model_version="test_v1",
                prediction_type="career_war",
                prediction_value=2.0 + i * 0.8,
                confidence_score=0.70 + i * 0.05
            )
            db_session.add(war_prediction)

        await db_session.commit()
        return prospects

    @pytest.fixture
    async def auth_headers(self, test_user):
        """Create authentication headers for API requests."""
        access_token = create_access_token(subject=test_user.email)
        return {"Authorization": f"Bearer {access_token}"}

    async def test_get_breakout_candidates(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test getting breakout candidates."""
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 30,
                "min_improvement_threshold": 0.05,
                "limit": 10
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)

        # Verify response structure for each candidate
        for candidate in data:
            assert "prospect_id" in candidate
            assert "mlb_id" in candidate
            assert "name" in candidate
            assert "position" in candidate
            assert "breakout_score" in candidate
            assert "improvement_metrics" in candidate
            assert "statistical_significance" in candidate
            assert "recent_stats_summary" in candidate
            assert "baseline_stats_summary" in candidate
            assert "trend_indicators" in candidate

            # Verify breakout score is in valid range
            assert 0 <= candidate["breakout_score"] <= 100

            # Verify trend indicators structure
            assert "trend_consistency" in candidate["trend_indicators"]
            assert "max_improvement_rate" in candidate["trend_indicators"]
            assert "avg_improvement_rate" in candidate["trend_indicators"]

    async def test_get_breakout_candidates_with_parameters(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test breakout candidates with different parameters."""
        # Test with stricter improvement threshold
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 60,
                "min_improvement_threshold": 0.15,
                "limit": 5
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 5

        # Test with different lookback period
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 14,
                "min_improvement_threshold": 0.05,
                "limit": 25
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.json(), list)

    async def test_get_sleeper_prospects(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test getting sleeper prospects."""
        response = await client.get(
            "/api/discovery/sleeper-prospects",
            params={
                "confidence_threshold": 0.7,
                "consensus_ranking_gap": 30,
                "limit": 10
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data, list)

        # Verify response structure for each sleeper
        for sleeper in data:
            assert "prospect_id" in sleeper
            assert "mlb_id" in sleeper
            assert "name" in sleeper
            assert "position" in sleeper
            assert "sleeper_score" in sleeper
            assert "ml_confidence" in sleeper
            assert "consensus_ranking_gap" in sleeper
            assert "undervaluation_factors" in sleeper
            assert "ml_predictions" in sleeper
            assert "market_analysis" in sleeper

            # Verify sleeper score is in valid range
            assert 0 <= sleeper["sleeper_score"] <= 100

            # Verify ML confidence is in valid range
            assert 0 <= sleeper["ml_confidence"] <= 1

            # Verify undervaluation factors is a list
            assert isinstance(sleeper["undervaluation_factors"], list)

    async def test_get_sleeper_prospects_with_parameters(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test sleeper prospects with different parameters."""
        # Test with higher confidence threshold
        response = await client.get(
            "/api/discovery/sleeper-prospects",
            params={
                "confidence_threshold": 0.85,
                "consensus_ranking_gap": 20,
                "limit": 5
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) <= 5

        # Verify all sleepers meet confidence threshold
        for sleeper in data:
            assert sleeper["ml_confidence"] >= 0.85

    async def test_get_discovery_dashboard(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test getting the complete discovery dashboard."""
        response = await client.get(
            "/api/discovery/dashboard",
            params={
                "lookback_days": 30,
                "confidence_threshold": 0.7,
                "limit_per_category": 5
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify main dashboard sections
        assert "breakout_candidates" in data
        assert "sleeper_prospects" in data
        assert "organizational_insights" in data
        assert "position_scarcity" in data
        assert "discovery_metadata" in data

        # Verify breakout candidates section
        assert isinstance(data["breakout_candidates"], list)
        assert len(data["breakout_candidates"]) <= 5

        # Verify sleeper prospects section
        assert isinstance(data["sleeper_prospects"], list)
        assert len(data["sleeper_prospects"]) <= 5

        # Verify organizational insights structure
        org_insights = data["organizational_insights"]
        assert "pipeline_rankings" in org_insights
        assert "competitive_advantages" in org_insights
        assert "opportunity_analysis" in org_insights
        assert "analysis_metadata" in org_insights

        # Verify position scarcity structure
        pos_scarcity = data["position_scarcity"]
        assert "position_supply" in pos_scarcity
        assert "scarcity_scores" in pos_scarcity
        assert "dynasty_opportunities" in pos_scarcity
        assert "scarcity_metadata" in pos_scarcity

        # Verify discovery metadata
        metadata = data["discovery_metadata"]
        assert "analysis_date" in metadata
        assert "lookback_days" in metadata
        assert "confidence_threshold" in metadata
        assert "total_breakout_candidates" in metadata
        assert "total_sleeper_prospects" in metadata

    async def test_discovery_endpoints_validation(self, client: AsyncClient, auth_headers):
        """Test discovery endpoints parameter validation."""
        # Invalid lookback days
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={"lookback_days": 400},  # Too high
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid confidence threshold
        response = await client.get(
            "/api/discovery/sleeper-prospects",
            params={"confidence_threshold": 1.5},  # Too high
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid limit
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={"limit": 150},  # Too high
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_discovery_unauthorized(self, client: AsyncClient):
        """Test discovery endpoints without authentication."""
        response = await client.get("/api/discovery/breakout-candidates")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = await client.get("/api/discovery/sleeper-prospects")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        response = await client.get("/api/discovery/dashboard")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_discovery_empty_results(self, client: AsyncClient, auth_headers):
        """Test discovery endpoints with criteria that return no results."""
        # Very high improvement threshold that no prospects will meet
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 30,
                "min_improvement_threshold": 0.99,  # 99% improvement - unrealistic
                "limit": 10
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        # May be empty or very few results

        # Very high confidence threshold for sleepers
        response = await client.get(
            "/api/discovery/sleeper-prospects",
            params={
                "confidence_threshold": 0.99,  # 99% confidence - very high
                "consensus_ranking_gap": 200,  # Very large gap
                "limit": 10
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    async def test_discovery_caching(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test that discovery results are properly cached."""
        # First request
        response1 = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 30,
                "min_improvement_threshold": 0.05,
                "limit": 10
            },
            headers=auth_headers
        )

        assert response1.status_code == status.HTTP_200_OK

        # Second identical request (should hit cache)
        response2 = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 30,
                "min_improvement_threshold": 0.05,
                "limit": 10
            },
            headers=auth_headers
        )

        assert response2.status_code == status.HTTP_200_OK

        # Results should be identical
        assert response1.json() == response2.json()

    async def test_prospect_performance_analysis(self, client: AsyncClient, auth_headers, test_prospects_with_stats):
        """Test that performance analysis correctly identifies trends."""
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 60,
                "min_improvement_threshold": 0.02,
                "limit": 25
            },
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Look for the prospect we specifically designed to have improving stats
        breakout_candidate = None
        for candidate in data:
            if candidate["name"] == "Breakout Candidate":
                breakout_candidate = candidate
                break

        if breakout_candidate:
            # Should have positive improvement metrics
            improvement_metrics = breakout_candidate["improvement_metrics"]

            # Verify some improvement was detected
            if "batting_avg_improvement_rate" in improvement_metrics:
                assert improvement_metrics["batting_avg_improvement_rate"] >= 0

            # Verify trend consistency is reasonable
            trend_indicators = breakout_candidate["trend_indicators"]
            assert 0 <= trend_indicators["trend_consistency"] <= 1