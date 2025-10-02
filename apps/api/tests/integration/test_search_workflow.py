"""Integration tests for complete search and discovery workflow."""

import pytest
from httpx import AsyncClient
from fastapi import status
from datetime import datetime, timedelta
import json

from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction, User
from app.core.security import create_access_token


class TestCompleteSearchWorkflow:
    """Test complete search and discovery workflow integration."""

    @pytest.fixture
    async def comprehensive_test_data(self, db_session):
        """Create comprehensive test data for full workflow testing."""
        prospects = []

        # Create diverse prospects for comprehensive testing
        prospect_configs = [
            {
                "mlb_id": "wf001",
                "name": "Elite Shortstop",
                "position": "SS",
                "organization": "Strong Organization",
                "level": "AA",
                "age": 20,
                "eta_year": 2025,
                "is_breakout": True,
                "is_sleeper": False
            },
            {
                "mlb_id": "wf002",
                "name": "Hidden Gem Pitcher",
                "position": "SP",
                "organization": "Deep Farm System",
                "level": "A+",
                "age": 19,
                "eta_year": 2027,
                "is_breakout": False,
                "is_sleeper": True
            },
            {
                "mlb_id": "wf003",
                "name": "Steady Outfielder",
                "position": "CF",
                "organization": "Average Organization",
                "level": "AAA",
                "age": 23,
                "eta_year": 2024,
                "is_breakout": False,
                "is_sleeper": False
            },
            {
                "mlb_id": "wf004",
                "name": "Power Prospect",
                "position": "1B",
                "organization": "Rebuilding Team",
                "level": "AA",
                "age": 21,
                "eta_year": 2025,
                "is_breakout": True,
                "is_sleeper": True
            }
        ]

        for config in prospect_configs:
            prospect = Prospect(
                mlb_id=config["mlb_id"],
                name=config["name"],
                position=config["position"],
                organization=config["organization"],
                level=config["level"],
                age=config["age"],
                eta_year=config["eta_year"]
            )
            db_session.add(prospect)
            await db_session.flush()
            prospects.append(prospect)

            # Create performance stats based on prospect type
            await self._create_prospect_stats(
                db_session, prospect, config["is_breakout"], config["is_sleeper"]
            )

            # Create scouting grades
            await self._create_scouting_grades(
                db_session, prospect, config["is_sleeper"]
            )

            # Create ML predictions
            await self._create_ml_predictions(
                db_session, prospect, config["is_sleeper"]
            )

        await db_session.commit()
        return prospects

    async def _create_prospect_stats(self, db_session, prospect, is_breakout, is_sleeper):
        """Create time-series stats for prospect."""
        base_date = datetime.now() - timedelta(days=90)

        # Create baseline stats (60-90 days ago)
        for i in range(6):
            stat_date = base_date + timedelta(days=i * 5)

            if prospect.position in ['SP', 'RP']:
                # Pitcher stats
                base_era = 4.20 if is_breakout else 3.80
                era_change = -0.05 if is_breakout else 0.02

                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date.date(),
                    season=2024,
                    era=base_era + (i * era_change),
                    whip=1.35 + (i * (-0.02 if is_breakout else 0.01)),
                    strikeouts_per_nine=8.5 + (i * (0.1 if is_breakout else 0.02))
                )
            else:
                # Hitter stats
                base_avg = 0.260 if is_breakout else 0.280
                avg_change = 0.003 if is_breakout else 0.001

                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date.date(),
                    season=2024,
                    batting_avg=base_avg + (i * avg_change),
                    on_base_pct=0.320 + (i * (0.004 if is_breakout else 0.001)),
                    slugging_pct=0.400 + (i * (0.008 if is_breakout else 0.002)),
                    woba=0.330 + (i * (0.005 if is_breakout else 0.001))
                )

            db_session.add(stats)

        # Create recent stats (0-30 days ago)
        recent_start = base_date + timedelta(days=60)
        for i in range(6):
            stat_date = recent_start + timedelta(days=i * 5)

            if prospect.position in ['SP', 'RP']:
                # Significant improvement for breakout candidates
                base_era = 3.20 if is_breakout else 3.75
                era_change = -0.08 if is_breakout else 0.01

                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date.date(),
                    season=2024,
                    era=base_era + (i * era_change),
                    whip=1.15 + (i * (-0.03 if is_breakout else 0.005)),
                    strikeouts_per_nine=10.2 + (i * (0.2 if is_breakout else 0.05))
                )
            else:
                # Significant improvement for breakout candidates
                base_avg = 0.320 if is_breakout else 0.285
                avg_change = 0.008 if is_breakout else 0.001

                stats = ProspectStats(
                    prospect_id=prospect.id,
                    date_recorded=stat_date.date(),
                    season=2024,
                    batting_avg=base_avg + (i * avg_change),
                    on_base_pct=0.380 + (i * (0.008 if is_breakout else 0.002)),
                    slugging_pct=0.520 + (i * (0.015 if is_breakout else 0.003)),
                    woba=0.380 + (i * (0.010 if is_breakout else 0.002))
                )

            db_session.add(stats)

    async def _create_scouting_grades(self, db_session, prospect, is_sleeper):
        """Create scouting grades for prospect."""
        # Sleepers have good underlying grades that might be overlooked
        base_grade = 55 if is_sleeper else 50

        grade = ScoutingGrades(
            prospect_id=prospect.id,
            source="Scout Network",
            overall=base_grade,
            hit=base_grade if prospect.position not in ['SP', 'RP'] else None,
            power=base_grade - 5 if prospect.position not in ['SP', 'RP'] else None,
            future_value=base_grade + 5 if is_sleeper else base_grade,
            risk="Moderate" if is_sleeper else "High"
        )
        db_session.add(grade)

    async def _create_ml_predictions(self, db_session, prospect, is_sleeper):
        """Create ML predictions for prospect."""
        # Sleepers have high ML confidence but may be undervalued
        base_success = 0.80 if is_sleeper else 0.60
        base_confidence = 0.88 if is_sleeper else 0.72

        success_pred = MLPrediction(
            prospect_id=prospect.id,
            model_version="workflow_v1",
            prediction_type="success_rating",
            prediction_value=base_success,
            confidence_score=base_confidence
        )
        db_session.add(success_pred)

        war_pred = MLPrediction(
            prospect_id=prospect.id,
            model_version="workflow_v1",
            prediction_type="career_war",
            prediction_value=2.8 if is_sleeper else 1.8,
            confidence_score=base_confidence - 0.05
        )
        db_session.add(war_pred)

    @pytest.fixture
    async def auth_headers(self, test_user):
        """Create authentication headers for API requests."""
        access_token = create_access_token(subject=test_user.email)
        return {"Authorization": f"Bearer {access_token}"}

    async def test_complete_discovery_workflow(
        self, client: AsyncClient, auth_headers, comprehensive_test_data, test_user
    ):
        """Test complete discovery workflow from search to saved searches."""

        # 1. Start with advanced search to find prospects
        search_data = {
            "positions": ["SS", "SP", "CF", "1B"],
            "min_age": 18,
            "max_age": 25,
            "page": 1,
            "size": 10
        }

        search_response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert search_response.status_code == status.HTTP_200_OK
        search_results = search_response.json()
        assert search_results["total_count"] >= 4
        assert len(search_results["prospects"]) >= 4

        # 2. Save this search for future use
        saved_search_data = {
            "search_name": "Young Prospects Search",
            "search_criteria": {
                "basic": {
                    "positions": ["SS", "SP", "CF", "1B"],
                    "min_age": 18,
                    "max_age": 25
                }
            }
        }

        save_response = await client.post(
            "/api/search/saved",
            json=saved_search_data,
            headers=auth_headers
        )

        assert save_response.status_code == status.HTTP_200_OK
        saved_search = save_response.json()
        assert saved_search["search_name"] == "Young Prospects Search"

        # 3. Get breakout candidates
        breakout_response = await client.get(
            "/api/discovery/breakout-candidates",
            params={
                "lookback_days": 30,
                "min_improvement_threshold": 0.15,
                "limit": 10
            },
            headers=auth_headers
        )

        assert breakout_response.status_code == status.HTTP_200_OK
        breakout_candidates = breakout_response.json()

        # Should find our breakout prospects
        breakout_names = [c["name"] for c in breakout_candidates]
        assert "Elite Shortstop" in breakout_names or "Power Prospect" in breakout_names

        # 4. Get sleeper prospects
        sleeper_response = await client.get(
            "/api/discovery/sleeper-prospects",
            params={
                "confidence_threshold": 0.75,
                "consensus_ranking_gap": 30,
                "limit": 10
            },
            headers=auth_headers
        )

        assert sleeper_response.status_code == status.HTTP_200_OK
        sleeper_prospects = sleeper_response.json()

        # Should find our sleeper prospects
        sleeper_names = [s["name"] for s in sleeper_prospects]
        assert "Hidden Gem Pitcher" in sleeper_names or "Power Prospect" in sleeper_names

        # 5. Track prospect views
        for prospect in search_results["prospects"][:2]:
            track_response = await client.post(
                "/api/search/track-view",
                params={
                    "prospect_id": prospect["id"],
                    "view_duration": 45
                },
                headers=auth_headers
            )
            assert track_response.status_code == status.HTTP_200_OK

        # 6. Get search history
        history_response = await client.get(
            "/api/search/history",
            headers=auth_headers
        )

        assert history_response.status_code == status.HTTP_200_OK
        search_history = history_response.json()
        assert len(search_history) >= 1

        # 7. Get recently viewed prospects
        viewed_response = await client.get(
            "/api/search/recently-viewed",
            headers=auth_headers
        )

        assert viewed_response.status_code == status.HTTP_200_OK
        recently_viewed = viewed_response.json()
        assert len(recently_viewed) >= 2

        # 8. Get complete discovery dashboard
        dashboard_response = await client.get(
            "/api/discovery/dashboard",
            params={
                "lookback_days": 30,
                "confidence_threshold": 0.7,
                "limit_per_category": 5
            },
            headers=auth_headers
        )

        assert dashboard_response.status_code == status.HTTP_200_OK
        dashboard = dashboard_response.json()

        # Verify dashboard structure
        assert "breakout_candidates" in dashboard
        assert "sleeper_prospects" in dashboard
        assert "organizational_insights" in dashboard
        assert "position_scarcity" in dashboard
        assert "discovery_metadata" in dashboard

        # 9. Get saved searches to verify persistence
        saved_searches_response = await client.get(
            "/api/search/saved",
            headers=auth_headers
        )

        assert saved_searches_response.status_code == status.HTTP_200_OK
        saved_searches = saved_searches_response.json()
        assert len(saved_searches) >= 1
        assert any(s["search_name"] == "Young Prospects Search" for s in saved_searches)

    async def test_search_personalization_workflow(
        self, client: AsyncClient, auth_headers, comprehensive_test_data
    ):
        """Test search personalization through user interactions."""

        # 1. Perform initial search
        search_data = {
            "positions": ["SS"],
            "min_age": 19,
            "max_age": 22
        }

        search_response = await client.post(
            "/api/search/advanced",
            json=search_data,
            headers=auth_headers
        )

        assert search_response.status_code == status.HTTP_200_OK
        results = search_response.json()

        # 2. Track multiple views to build interaction history
        if results["prospects"]:
            prospect_id = results["prospects"][0]["id"]

            # Track multiple views with different durations
            for duration in [30, 60, 90]:
                await client.post(
                    "/api/search/track-view",
                    params={"prospect_id": prospect_id, "view_duration": duration},
                    headers=auth_headers
                )

        # 3. Perform similar searches to build search patterns
        similar_searches = [
            {"positions": ["SS", "2B"], "min_age": 18, "max_age": 23},
            {"positions": ["SS"], "min_overall_grade": 50},
            {"positions": ["SS"], "min_success_probability": 0.7}
        ]

        for search in similar_searches:
            await client.post(
                "/api/search/advanced",
                json=search,
                headers=auth_headers
            )

        # 4. Verify search history captures patterns
        history_response = await client.get(
            "/api/search/history",
            headers=auth_headers
        )

        assert history_response.status_code == status.HTTP_200_OK
        history = history_response.json()
        assert len(history) >= 4  # Initial + 3 similar searches

        # Verify SS position appears frequently in history
        ss_searches = sum(1 for h in history
                         if h["search_criteria"] and
                         h["search_criteria"].get("basic", {}).get("positions") and
                         "SS" in h["search_criteria"]["basic"]["positions"])
        assert ss_searches >= 3

    async def test_cross_feature_integration(
        self, client: AsyncClient, auth_headers, comprehensive_test_data
    ):
        """Test integration between different search and discovery features."""

        # 1. Search for prospects with statistical criteria
        stat_search = {
            "min_batting_avg": 0.300,
            "min_on_base_pct": 0.350,
            "positions": ["SS", "CF"]
        }

        stat_response = await client.post(
            "/api/search/advanced",
            json=stat_search,
            headers=auth_headers
        )

        assert stat_response.status_code == status.HTTP_200_OK

        # 2. Search for prospects with scouting criteria
        scout_search = {
            "min_overall_grade": 50,
            "min_future_value": 55,
            "risk_levels": ["Moderate"]
        }

        scout_response = await client.post(
            "/api/search/advanced",
            json=scout_search,
            headers=auth_headers
        )

        assert scout_response.status_code == status.HTTP_200_OK

        # 3. Search for prospects with ML criteria
        ml_search = {
            "min_success_probability": 0.75,
            "min_confidence_score": 0.8,
            "prediction_types": ["success_rating"]
        }

        ml_response = await client.post(
            "/api/search/advanced",
            json=ml_search,
            headers=auth_headers
        )

        assert ml_response.status_code == status.HTTP_200_OK

        # 4. Combine all criteria in one advanced search
        combined_search = {
            "positions": ["SS", "SP", "1B"],
            "min_age": 19,
            "max_age": 22,
            "min_batting_avg": 0.280,
            "min_overall_grade": 50,
            "min_success_probability": 0.70,
            "sort_by": "relevance"
        }

        combined_response = await client.post(
            "/api/search/advanced",
            json=combined_search,
            headers=auth_headers
        )

        assert combined_response.status_code == status.HTTP_200_OK
        combined_results = combined_response.json()

        # Verify metadata shows all filter types were applied
        metadata = combined_results["search_metadata"]
        assert metadata["applied_filters"]["statistical"] is True
        assert metadata["applied_filters"]["scouting"] is True
        assert metadata["applied_filters"]["ml_predictions"] is True
        assert metadata["applied_filters"]["basic_filters"] is True

        # 5. Save the comprehensive search
        save_combined = {
            "search_name": "Comprehensive Multi-Criteria Search",
            "search_criteria": {
                "statistical": {"min_batting_avg": 0.280},
                "basic": {"positions": ["SS", "SP", "1B"], "min_age": 19, "max_age": 22},
                "scouting": {"min_overall_grade": 50},
                "ml": {"min_success_probability": 0.70}
            }
        }

        save_response = await client.post(
            "/api/search/saved",
            json=save_combined,
            headers=auth_headers
        )

        assert save_response.status_code == status.HTTP_200_OK

        # 6. Verify the complex search can be retrieved and used
        saved_searches = await client.get("/api/search/saved", headers=auth_headers)
        assert saved_searches.status_code == status.HTTP_200_OK

        saved_list = saved_searches.json()
        comprehensive_search = next(
            (s for s in saved_list if s["search_name"] == "Comprehensive Multi-Criteria Search"),
            None
        )
        assert comprehensive_search is not None
        assert "statistical" in comprehensive_search["search_criteria"]
        assert "scouting" in comprehensive_search["search_criteria"]
        assert "ml" in comprehensive_search["search_criteria"]

    async def test_error_handling_in_workflow(
        self, client: AsyncClient, auth_headers
    ):
        """Test error handling throughout the complete workflow."""

        # 1. Test invalid search parameters
        invalid_search = {"min_batting_avg": 2.0}  # Invalid value
        response = await client.post(
            "/api/search/advanced",
            json=invalid_search,
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # 2. Test saving search with duplicate name
        search_data = {
            "search_name": "Test Search",
            "search_criteria": {"basic": {"positions": ["SS"]}}
        }

        # First save should succeed
        response1 = await client.post(
            "/api/search/saved",
            json=search_data,
            headers=auth_headers
        )
        assert response1.status_code == status.HTTP_200_OK

        # Second save with same name should fail
        response2 = await client.post(
            "/api/search/saved",
            json=search_data,
            headers=auth_headers
        )
        assert response2.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Test accessing non-existent saved search
        response = await client.get(
            "/api/search/saved/99999",
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

        # 4. Test discovery endpoints with extreme parameters
        response = await client.get(
            "/api/discovery/breakout-candidates",
            params={"min_improvement_threshold": 0.99},  # Unrealistic threshold
            headers=auth_headers
        )
        assert response.status_code == status.HTTP_200_OK
        # Should return empty or very few results, not error

        # 5. Test tracking view for non-existent prospect
        response = await client.post(
            "/api/search/track-view",
            params={"prospect_id": 99999},
            headers=auth_headers
        )
        # Should handle gracefully (exact behavior depends on implementation)