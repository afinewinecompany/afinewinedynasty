"""Tests for discovery service business logic."""

import pytest
from datetime import datetime, timedelta
import statistics

from app.services.discovery_service import DiscoveryService
from app.services.breakout_detection_service import BreakoutDetectionService
from app.db.models import Prospect, ProspectStats, ScoutingGrades, MLPrediction


class TestBreakoutDetectionService:
    """Test suite for breakout detection service."""

    @pytest.fixture
    async def prospects_with_time_series(self, db_session):
        """Create prospects with time-series data for breakout analysis."""
        prospects = []

        # Create a prospect with clear improvement trend
        improving_prospect = Prospect(
            mlb_id="improve001",
            name="Improving Player",
            position="SS",
            organization="Test Org",
            level="AA",
            age=20,
            eta_year=2025
        )
        db_session.add(improving_prospect)
        await db_session.flush()
        prospects.append(improving_prospect)

        # Create time-series stats showing improvement
        base_date = datetime.now() - timedelta(days=90)

        # Baseline period (60-90 days ago) - lower performance
        for i in range(6):
            stat_date = base_date + timedelta(days=i * 5)
            stats = ProspectStats(
                prospect_id=improving_prospect.id,
                date_recorded=stat_date.date(),
                season=2024,
                batting_avg=0.240 + (i * 0.005),  # Slight improvement
                on_base_pct=0.300 + (i * 0.003),
                slugging_pct=0.380 + (i * 0.008),
                woba=0.320 + (i * 0.004)
            )
            db_session.add(stats)

        # Recent period (0-30 days ago) - higher performance
        recent_start = base_date + timedelta(days=60)
        for i in range(6):
            stat_date = recent_start + timedelta(days=i * 5)
            stats = ProspectStats(
                prospect_id=improving_prospect.id,
                date_recorded=stat_date.date(),
                season=2024,
                batting_avg=0.290 + (i * 0.008),  # Clear improvement
                on_base_pct=0.340 + (i * 0.006),
                slugging_pct=0.450 + (i * 0.012),
                woba=0.360 + (i * 0.008)
            )
            db_session.add(stats)

        # Create a pitcher with improving ERA
        improving_pitcher = Prospect(
            mlb_id="improve002",
            name="Improving Pitcher",
            position="SP",
            organization="Test Org",
            level="AA",
            age=21,
            eta_year=2025
        )
        db_session.add(improving_pitcher)
        await db_session.flush()
        prospects.append(improving_pitcher)

        # Baseline period - higher ERA (worse)
        for i in range(6):
            stat_date = base_date + timedelta(days=i * 5)
            stats = ProspectStats(
                prospect_id=improving_pitcher.id,
                date_recorded=stat_date.date(),
                season=2024,
                era=4.80 - (i * 0.05),  # Slight improvement
                whip=1.45 - (i * 0.02),
                strikeouts_per_nine=8.5 + (i * 0.1)
            )
            db_session.add(stats)

        # Recent period - lower ERA (better)
        for i in range(6):
            stat_date = recent_start + timedelta(days=i * 5)
            stats = ProspectStats(
                prospect_id=improving_pitcher.id,
                date_recorded=stat_date.date(),
                season=2024,
                era=3.20 - (i * 0.08),  # Clear improvement
                whip=1.15 - (i * 0.03),
                strikeouts_per_nine=10.2 + (i * 0.2)
            )
            db_session.add(stats)

        await db_session.commit()
        return prospects

    async def test_get_breakout_candidates(self, db_session, prospects_with_time_series):
        """Test basic breakout candidate detection."""
        candidates = await BreakoutDetectionService.get_breakout_candidates(
            db=db_session,
            lookback_days=30,
            min_improvement_threshold=0.10,
            limit=10
        )

        assert isinstance(candidates, list)

        # Should find our improving prospects
        candidate_names = [c.prospect.name for c in candidates]
        assert "Improving Player" in candidate_names or "Improving Pitcher" in candidate_names

        # Verify candidate structure
        for candidate in candidates:
            assert hasattr(candidate, 'prospect')
            assert hasattr(candidate, 'breakout_score')
            assert hasattr(candidate, 'improvement_metrics')
            assert hasattr(candidate, 'recent_stats')
            assert hasattr(candidate, 'baseline_stats')

            # Verify score is reasonable
            assert 0 <= candidate.breakout_score <= 100

    async def test_breakout_improvement_calculation(self, db_session, prospects_with_time_series):
        """Test that improvement metrics are calculated correctly."""
        candidates = await BreakoutDetectionService.get_breakout_candidates(
            db=db_session,
            lookback_days=30,
            min_improvement_threshold=0.05,
            limit=10
        )

        improving_player = None
        for candidate in candidates:
            if candidate.prospect.name == "Improving Player":
                improving_player = candidate
                break

        if improving_player:
            metrics = improving_player.improvement_metrics

            # Should detect positive improvement for hitting stats
            if "batting_avg_improvement_rate" in metrics:
                assert metrics["batting_avg_improvement_rate"] > 0

            if "on_base_pct_improvement_rate" in metrics:
                assert metrics["on_base_pct_improvement_rate"] > 0

            # Should have overall positive trend
            assert metrics.get("max_improvement_rate", 0) > 0

    async def test_pitcher_improvement_calculation(self, db_session, prospects_with_time_series):
        """Test that pitcher improvement metrics work correctly."""
        candidates = await BreakoutDetectionService.get_breakout_candidates(
            db=db_session,
            lookback_days=30,
            min_improvement_threshold=0.05,
            limit=10
        )

        improving_pitcher = None
        for candidate in candidates:
            if candidate.prospect.name == "Improving Pitcher":
                improving_pitcher = candidate
                break

        if improving_pitcher:
            metrics = improving_pitcher.improvement_metrics

            # For pitchers, improvement means ERA going down
            if "era_improvement_rate" in metrics:
                assert metrics["era_improvement_rate"] > 0  # Positive because ERA decreased

            if "whip_improvement_rate" in metrics:
                assert metrics["whip_improvement_rate"] > 0

    async def test_insufficient_data_handling(self, db_session):
        """Test handling of prospects with insufficient data."""
        # Create prospect with minimal stats
        prospect = Prospect(
            mlb_id="minimal001",
            name="Minimal Data",
            position="OF",
            organization="Test Org",
            level="A",
            age=19,
            eta_year=2027
        )
        db_session.add(prospect)
        await db_session.flush()

        # Add only one stat (insufficient for trend analysis)
        stats = ProspectStats(
            prospect_id=prospect.id,
            date_recorded=datetime.now().date(),
            season=2024,
            batting_avg=0.300
        )
        db_session.add(stats)
        await db_session.commit()

        candidates = await BreakoutDetectionService.get_breakout_candidates(
            db=db_session,
            lookback_days=30,
            min_improvement_threshold=0.10,
            limit=10
        )

        # Should not include prospect with insufficient data
        candidate_names = [c.prospect.name for c in candidates]
        assert "Minimal Data" not in candidate_names


class TestDiscoveryService:
    """Test suite for discovery service."""

    @pytest.fixture
    async def prospects_with_ml_predictions(self, db_session):
        """Create prospects with ML predictions for sleeper analysis."""
        prospects = []

        # High confidence, potentially undervalued prospect
        sleeper_prospect = Prospect(
            mlb_id="sleeper001",
            name="Sleeper Prospect",
            position="SS",
            organization="Deep Organization",
            level="A+",
            age=19,
            eta_year=2027
        )
        db_session.add(sleeper_prospect)
        await db_session.flush()
        prospects.append(sleeper_prospect)

        # High confidence ML predictions
        high_confidence_pred = MLPrediction(
            prospect_id=sleeper_prospect.id,
            model_version="test_v1",
            prediction_type="success_rating",
            prediction_value=0.85,
            confidence_score=0.92
        )
        db_session.add(high_confidence_pred)

        war_pred = MLPrediction(
            prospect_id=sleeper_prospect.id,
            model_version="test_v1",
            prediction_type="career_war",
            prediction_value=3.2,
            confidence_score=0.88
        )
        db_session.add(war_pred)

        # Regular prospect with moderate predictions
        regular_prospect = Prospect(
            mlb_id="regular001",
            name="Regular Prospect",
            position="OF",
            organization="Average Organization",
            level="AA",
            age=22,
            eta_year=2025
        )
        db_session.add(regular_prospect)
        await db_session.flush()
        prospects.append(regular_prospect)

        # Moderate ML predictions
        moderate_pred = MLPrediction(
            prospect_id=regular_prospect.id,
            model_version="test_v1",
            prediction_type="success_rating",
            prediction_value=0.65,
            confidence_score=0.72
        )
        db_session.add(moderate_pred)

        await db_session.commit()
        return prospects

    async def test_get_sleeper_prospects(self, db_session, prospects_with_ml_predictions):
        """Test sleeper prospect identification."""
        sleepers = await DiscoveryService.get_sleeper_prospects(
            db=db_session,
            confidence_threshold=0.8,
            consensus_ranking_gap=40,
            limit=10
        )

        assert isinstance(sleepers, list)

        # Should find our high-confidence prospect
        sleeper_names = [s.prospect.name for s in sleepers]
        assert "Sleeper Prospect" in sleeper_names

        # Verify sleeper structure
        for sleeper in sleepers:
            assert hasattr(sleeper, 'prospect')
            assert hasattr(sleeper, 'sleeper_score')
            assert hasattr(sleeper, 'ml_confidence')
            assert hasattr(sleeper, 'consensus_ranking_gap')
            assert hasattr(sleeper, 'undervaluation_factors')
            assert hasattr(sleeper, 'ml_predictions')
            assert hasattr(sleeper, 'market_analysis')

            # Verify confidence meets threshold
            assert sleeper.ml_confidence >= 0.8

            # Verify score is reasonable
            assert 0 <= sleeper.sleeper_score <= 100

    async def test_sleeper_undervaluation_factors(self, db_session, prospects_with_ml_predictions):
        """Test identification of undervaluation factors."""
        sleepers = await DiscoveryService.get_sleeper_prospects(
            db=db_session,
            confidence_threshold=0.8,
            consensus_ranking_gap=30,
            limit=10
        )

        sleeper_prospect = None
        for sleeper in sleepers:
            if sleeper.prospect.name == "Sleeper Prospect":
                sleeper_prospect = sleeper
                break

        if sleeper_prospect:
            factors = sleeper_prospect.undervaluation_factors
            assert isinstance(factors, list)

            # Should identify relevant undervaluation factors
            factor_text = " ".join(factors)
            assert any(keyword in factor_text.lower() for keyword in [
                "young", "confidence", "position", "eta", "level", "organization"
            ])

    async def test_organizational_insights(self, db_session):
        """Test organizational pipeline analysis."""
        # Create prospects from different organizations
        orgs = ["Strong Org", "Weak Org", "Average Org"]
        for i, org in enumerate(orgs):
            for j in range(3 + i):  # Varying numbers of prospects
                prospect = Prospect(
                    mlb_id=f"org{i}_{j}",
                    name=f"Player {i}_{j}",
                    position="SS",
                    organization=org,
                    level="AA",
                    age=20 + j,
                    eta_year=2025 + j
                )
                db_session.add(prospect)

        await db_session.commit()

        insights = await DiscoveryService.get_organizational_insights(
            db=db_session,
            limit=10
        )

        assert isinstance(insights, dict)
        assert "pipeline_rankings" in insights
        assert "competitive_advantages" in insights
        assert "opportunity_analysis" in insights
        assert "analysis_metadata" in insights

        # Verify pipeline rankings structure
        pipeline_rankings = insights["pipeline_rankings"]
        assert isinstance(pipeline_rankings, list)

        for ranking in pipeline_rankings:
            assert "organization" in ranking
            assert "prospect_count" in ranking
            assert "depth_score" in ranking

    async def test_position_scarcity_analysis(self, db_session):
        """Test position scarcity analysis."""
        # Create prospects with varying position distributions
        positions = ["SS", "CF", "1B", "SP", "RP"]
        prospect_counts = [2, 3, 8, 5, 10]  # SS and CF are scarce, 1B and RP are plentiful

        for position, count in zip(positions, prospect_counts):
            for i in range(count):
                prospect = Prospect(
                    mlb_id=f"{position.lower()}{i}",
                    name=f"{position} Player {i}",
                    position=position,
                    organization="Test Org",
                    level="AA",
                    age=20,
                    eta_year=2025
                )
                db_session.add(prospect)

        await db_session.commit()

        scarcity_analysis = await DiscoveryService.get_position_scarcity_analysis(
            db=db_session
        )

        assert isinstance(scarcity_analysis, dict)
        assert "position_supply" in scarcity_analysis
        assert "scarcity_scores" in scarcity_analysis
        assert "dynasty_opportunities" in scarcity_analysis
        assert "scarcity_metadata" in scarcity_analysis

        # Verify position supply data
        position_supply = scarcity_analysis["position_supply"]
        assert "SS" in position_supply
        assert "1B" in position_supply

        # SS should have lower count than 1B
        assert position_supply["SS"]["prospect_count"] < position_supply["1B"]["prospect_count"]

        # Verify scarcity scores
        scarcity_scores = scarcity_analysis["scarcity_scores"]
        assert isinstance(scarcity_scores, dict)

        # SS should have higher scarcity score than 1B
        if "SS" in scarcity_scores and "1B" in scarcity_scores:
            assert scarcity_scores["SS"] > scarcity_scores["1B"]

    async def test_sleeper_ml_analysis(self, db_session, prospects_with_ml_predictions):
        """Test ML prediction analysis for sleeper prospects."""
        sleepers = await DiscoveryService.get_sleeper_prospects(
            db=db_session,
            confidence_threshold=0.85,
            consensus_ranking_gap=30,
            limit=10
        )

        for sleeper in sleepers:
            ml_predictions = sleeper.ml_predictions

            # Should have overall confidence score
            assert "overall_confidence" in ml_predictions
            assert ml_predictions["overall_confidence"] >= 0.85

            # Should have prediction types
            assert "prediction_types" in ml_predictions
            assert isinstance(ml_predictions["prediction_types"], list)

            # Should have individual predictions
            assert "predictions" in ml_predictions
            assert isinstance(ml_predictions["predictions"], dict)

    async def test_market_analysis_structure(self, db_session, prospects_with_ml_predictions):
        """Test market analysis structure for sleeper prospects."""
        sleepers = await DiscoveryService.get_sleeper_prospects(
            db=db_session,
            confidence_threshold=0.8,
            consensus_ranking_gap=30,
            limit=10
        )

        for sleeper in sleepers:
            market_analysis = sleeper.market_analysis

            # Should have required market analysis fields
            assert "ml_vs_consensus_gap" in market_analysis
            assert "ml_confidence_level" in market_analysis
            assert "market_inefficiency_score" in market_analysis
            assert "opportunity_window" in market_analysis
            assert "risk_factors" in market_analysis
            assert "upside_factors" in market_analysis

            # Verify data types
            assert isinstance(market_analysis["ml_vs_consensus_gap"], int)
            assert isinstance(market_analysis["ml_confidence_level"], float)
            assert isinstance(market_analysis["market_inefficiency_score"], float)
            assert isinstance(market_analysis["opportunity_window"], str)
            assert isinstance(market_analysis["risk_factors"], list)
            assert isinstance(market_analysis["upside_factors"], list)

    async def test_service_error_handling(self, db_session):
        """Test service error handling with invalid data."""
        # Test with empty database
        candidates = await BreakoutDetectionService.get_breakout_candidates(
            db=db_session,
            lookback_days=30,
            min_improvement_threshold=0.10,
            limit=10
        )

        # Should return empty list, not error
        assert isinstance(candidates, list)
        assert len(candidates) == 0

        sleepers = await DiscoveryService.get_sleeper_prospects(
            db=db_session,
            confidence_threshold=0.8,
            consensus_ranking_gap=50,
            limit=10
        )

        # Should return empty list, not error
        assert isinstance(sleepers, list)
        assert len(sleepers) == 0