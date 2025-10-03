"""
Unit tests for PersonalizedRecommendationService

Tests prospect-team fit scoring, timeline alignment, trade value analysis,
and recommendation generation logic.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.personalized_recommendation_service import PersonalizedRecommendationService


@pytest.fixture
def recommendation_service():
    """Create PersonalizedRecommendationService instance"""
    return PersonalizedRecommendationService()


@pytest.fixture
def rebuilding_analysis():
    """Team analysis for rebuilding team"""
    return {
        "timeline": "rebuilding",
        "average_age": 23.5,
        "needs": [
            {"position": "C", "priority": "high"},
            {"position": "OF", "priority": "medium"},
        ],
        "strengths": ["1B", "SS"],
        "weaknesses": ["C", "3B"],
        "future_holes": [
            {"position": "OF", "timeline": "2-3 years", "reason": "aging"}
        ],
        "roster_spots": {
            "available": 5,
            "minor_league_available": 3
        }
    }


@pytest.fixture
def contending_analysis():
    """Team analysis for contending team"""
    return {
        "timeline": "contending",
        "average_age": 28.2,
        "needs": [
            {"position": "C", "priority": "high"},
        ],
        "strengths": ["OF", "1B", "3B"],
        "weaknesses": ["C"],
        "future_holes": [],
        "roster_spots": {
            "available": 1,
            "minor_league_available": 0
        }
    }


@pytest.fixture
def sample_prospects():
    """Sample prospect data for testing"""
    return [
        {
            "id": "prospect1",
            "name": "Elite Catching Prospect",
            "position": "C",
            "overall_rating": 95,
            "eta": "2026",
            "age": 20,
            "ceiling": "All-Star",
            "floor": "Starter"
        },
        {
            "id": "prospect2",
            "name": "MLB-Ready Catcher",
            "position": "C",
            "overall_rating": 82,
            "eta": "2025",
            "age": 23,
            "ceiling": "Starter",
            "floor": "Backup"
        },
        {
            "id": "prospect3",
            "name": "Toolsy Outfielder",
            "position": "OF",
            "overall_rating": 88,
            "eta": "2027",
            "age": 19,
            "ceiling": "Star",
            "floor": "Role Player"
        },
        {
            "id": "prospect4",
            "name": "Injured 3B Prospect",
            "position": "3B",
            "overall_rating": 78,
            "eta": "2028",
            "age": 21,
            "injury_risk": "high",
            "ceiling": "Starter",
            "floor": "Bust"
        },
    ]


class TestGetRecommendations:
    """Test recommendation generation"""

    @pytest.mark.asyncio
    async def test_get_recommendations_rebuilding_team(self, recommendation_service, rebuilding_analysis, sample_prospects):
        """Generate recommendations for rebuilding team"""
        recommendations = await recommendation_service.get_recommendations(
            team_analysis=rebuilding_analysis,
            prospects=sample_prospects,
            limit=10
        )

        # Should return recommendations
        assert len(recommendations) > 0
        assert all("prospect" in rec for rec in recommendations)
        assert all("fit_score" in rec for rec in recommendations)
        assert all("reason" in rec for rec in recommendations)

    @pytest.mark.asyncio
    async def test_get_recommendations_contending_team(self, recommendation_service, contending_analysis, sample_prospects):
        """Generate recommendations for contending team"""
        recommendations = await recommendation_service.get_recommendations(
            team_analysis=contending_analysis,
            prospects=sample_prospects,
            limit=10
        )

        # Contending team should prefer MLB-ready prospects
        assert len(recommendations) > 0

        # MLB-ready catcher should score higher than distant prospects
        mlb_ready = next((r for r in recommendations if r["prospect"]["id"] == "prospect2"), None)
        toolsy_of = next((r for r in recommendations if r["prospect"]["id"] == "prospect3"), None)

        if mlb_ready and toolsy_of:
            assert mlb_ready["fit_score"] > toolsy_of["fit_score"]

    @pytest.mark.asyncio
    async def test_recommendations_sorted_by_fit(self, recommendation_service, rebuilding_analysis, sample_prospects):
        """Recommendations should be sorted by fit score descending"""
        recommendations = await recommendation_service.get_recommendations(
            team_analysis=rebuilding_analysis,
            prospects=sample_prospects,
            limit=10
        )

        fit_scores = [rec["fit_score"] for rec in recommendations]
        assert fit_scores == sorted(fit_scores, reverse=True)

    @pytest.mark.asyncio
    async def test_recommendations_limit(self, recommendation_service, rebuilding_analysis, sample_prospects):
        """Respect limit parameter"""
        recommendations = await recommendation_service.get_recommendations(
            team_analysis=rebuilding_analysis,
            prospects=sample_prospects,
            limit=2
        )

        assert len(recommendations) <= 2


class TestCalculateFitScore:
    """Test prospect-team fit scoring algorithm"""

    @pytest.mark.asyncio
    async def test_fit_score_position_need_match(self, recommendation_service, rebuilding_analysis):
        """High fit score for prospect matching position need"""
        catcher_prospect = {
            "id": "p1",
            "position": "C",
            "overall_rating": 85,
            "eta": "2026",
            "age": 21
        }

        fit_score = await recommendation_service._calculate_fit_score(
            prospect=catcher_prospect,
            team_analysis=rebuilding_analysis
        )

        # Catcher is high-priority need, should score well
        assert fit_score > 70

    @pytest.mark.asyncio
    async def test_fit_score_no_position_need(self, recommendation_service, rebuilding_analysis):
        """Lower fit score for prospect at strength position"""
        first_base_prospect = {
            "id": "p1",
            "position": "1B",
            "overall_rating": 85,
            "eta": "2026",
            "age": 21
        }

        fit_score = await recommendation_service._calculate_fit_score(
            prospect=first_base_prospect,
            team_analysis=rebuilding_analysis
        )

        # 1B is a strength, fit score should be lower
        assert fit_score < 70

    @pytest.mark.asyncio
    async def test_fit_score_timeline_alignment_rebuilding(self, recommendation_service, rebuilding_analysis):
        """High fit for distant ETA with rebuilding team"""
        distant_prospect = {
            "id": "p1",
            "position": "OF",
            "overall_rating": 90,
            "eta": "2028",
            "age": 19
        }

        fit_score = await recommendation_service._calculate_fit_score(
            prospect=distant_prospect,
            team_analysis=rebuilding_analysis
        )

        # Rebuilding team can wait for elite talent
        assert fit_score > 60

    @pytest.mark.asyncio
    async def test_fit_score_timeline_alignment_contending(self, recommendation_service, contending_analysis):
        """Lower fit for distant ETA with contending team"""
        distant_prospect = {
            "id": "p1",
            "position": "C",
            "overall_rating": 95,
            "eta": "2028",
            "age": 19
        }

        fit_score = await recommendation_service._calculate_fit_score(
            prospect=distant_prospect,
            team_analysis=contending_analysis
        )

        # Contending team needs immediate help
        assert fit_score < 50

    @pytest.mark.asyncio
    async def test_fit_score_mlb_ready_contending(self, recommendation_service, contending_analysis):
        """High fit for MLB-ready prospect with contending team"""
        mlb_ready = {
            "id": "p1",
            "position": "C",
            "overall_rating": 80,
            "eta": "2025",
            "age": 23
        }

        fit_score = await recommendation_service._calculate_fit_score(
            prospect=mlb_ready,
            team_analysis=contending_analysis
        )

        # MLB-ready prospect filling need on contender = great fit
        assert fit_score > 80

    @pytest.mark.asyncio
    async def test_fit_score_overall_rating_impact(self, recommendation_service, rebuilding_analysis):
        """Higher rated prospects score better"""
        elite_prospect = {
            "id": "p1",
            "position": "C",
            "overall_rating": 95,
            "eta": "2026",
            "age": 20
        }

        average_prospect = {
            "id": "p2",
            "position": "C",
            "overall_rating": 70,
            "eta": "2026",
            "age": 20
        }

        elite_score = await recommendation_service._calculate_fit_score(elite_prospect, rebuilding_analysis)
        average_score = await recommendation_service._calculate_fit_score(average_prospect, rebuilding_analysis)

        assert elite_score > average_score


class TestGenerateRecommendationReason:
    """Test recommendation explanation generation"""

    @pytest.mark.asyncio
    async def test_generate_reason_position_need(self, recommendation_service, rebuilding_analysis):
        """Generate reason explaining position need"""
        prospect = {
            "id": "p1",
            "name": "Test Prospect",
            "position": "C",
            "overall_rating": 85,
            "eta": "2026"
        }

        reason = await recommendation_service._generate_recommendation_reason(
            prospect=prospect,
            team_analysis=rebuilding_analysis,
            fit_score=85
        )

        # Should mention position need
        assert "C" in reason or "catcher" in reason.lower()

    @pytest.mark.asyncio
    async def test_generate_reason_timeline_alignment(self, recommendation_service, rebuilding_analysis):
        """Generate reason explaining timeline fit"""
        prospect = {
            "id": "p1",
            "name": "Test Prospect",
            "position": "OF",
            "overall_rating": 90,
            "eta": "2027"
        }

        reason = await recommendation_service._generate_recommendation_reason(
            prospect=prospect,
            team_analysis=rebuilding_analysis,
            fit_score=80
        )

        # Should mention timeline or rebuild
        assert any(word in reason.lower() for word in ["timeline", "rebuild", "2027", "future"])

    @pytest.mark.asyncio
    async def test_generate_reason_complete_information(self, recommendation_service, rebuilding_analysis):
        """Recommendation reason should be informative"""
        prospect = {
            "id": "p1",
            "name": "Elite Catcher",
            "position": "C",
            "overall_rating": 95,
            "eta": "2026",
            "ceiling": "All-Star"
        }

        reason = await recommendation_service._generate_recommendation_reason(
            prospect=prospect,
            team_analysis=rebuilding_analysis,
            fit_score=92
        )

        # Should be a non-empty string with useful info
        assert len(reason) > 20
        assert isinstance(reason, str)


class TestAnalyzeTrade:
    """Test trade value analysis"""

    @pytest.mark.asyncio
    async def test_analyze_trade_value_calculation(self, recommendation_service, rebuilding_analysis):
        """Calculate trade value for prospects"""
        prospects_to_receive = [
            {"id": "p1", "overall_rating": 90, "position": "C", "eta": "2026"}
        ]

        prospects_to_give = [
            {"id": "p2", "overall_rating": 75, "position": "OF", "eta": "2027"}
        ]

        trade_analysis = await recommendation_service.analyze_trade(
            team_analysis=rebuilding_analysis,
            prospects_to_receive=prospects_to_receive,
            prospects_to_give=prospects_to_give
        )

        assert "value_to_receive" in trade_analysis
        assert "value_to_give" in trade_analysis
        assert "net_value" in trade_analysis
        assert "fit_improvement" in trade_analysis
        assert "recommendation" in trade_analysis

    @pytest.mark.asyncio
    async def test_analyze_trade_positive_value(self, recommendation_service, rebuilding_analysis):
        """Recommend accepting positive value trades"""
        prospects_to_receive = [
            {"id": "p1", "overall_rating": 95, "position": "C", "eta": "2026", "age": 20}
        ]

        prospects_to_give = [
            {"id": "p2", "overall_rating": 70, "position": "1B", "eta": "2027", "age": 21}
        ]

        trade_analysis = await recommendation_service.analyze_trade(
            team_analysis=rebuilding_analysis,
            prospects_to_receive=prospects_to_receive,
            prospects_to_give=prospects_to_give
        )

        # Receiving higher-rated prospect at need position = positive value
        assert trade_analysis["net_value"] > 0
        assert "accept" in trade_analysis["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_analyze_trade_negative_value(self, recommendation_service, rebuilding_analysis):
        """Recommend rejecting negative value trades"""
        prospects_to_receive = [
            {"id": "p1", "overall_rating": 70, "position": "1B", "eta": "2027", "age": 22}
        ]

        prospects_to_give = [
            {"id": "p2", "overall_rating": 90, "position": "C", "eta": "2026", "age": 20}
        ]

        trade_analysis = await recommendation_service.analyze_trade(
            team_analysis=rebuilding_analysis,
            prospects_to_receive=prospects_to_receive,
            prospects_to_give=prospects_to_give
        )

        # Giving up better prospect at need position = negative value
        assert trade_analysis["net_value"] < 0
        assert "reject" in trade_analysis["recommendation"].lower() or "decline" in trade_analysis["recommendation"].lower()

    @pytest.mark.asyncio
    async def test_analyze_trade_fit_improvement(self, recommendation_service, rebuilding_analysis):
        """Calculate fit improvement from trade"""
        prospects_to_receive = [
            {"id": "p1", "overall_rating": 85, "position": "C", "eta": "2026", "age": 21}  # Need position
        ]

        prospects_to_give = [
            {"id": "p2", "overall_rating": 85, "position": "1B", "eta": "2026", "age": 21}  # Strength position
        ]

        trade_analysis = await recommendation_service.analyze_trade(
            team_analysis=rebuilding_analysis,
            prospects_to_receive=prospects_to_receive,
            prospects_to_give=prospects_to_give
        )

        # Equal ratings but better position fit = positive fit improvement
        assert trade_analysis["fit_improvement"] > 0


class TestCalculateTradeValue:
    """Test trade value calculation"""

    @pytest.mark.asyncio
    async def test_calculate_value_single_prospect(self, recommendation_service, rebuilding_analysis):
        """Calculate value for single prospect"""
        prospect = {
            "id": "p1",
            "overall_rating": 85,
            "position": "C",
            "eta": "2026",
            "age": 21
        }

        value = await recommendation_service._calculate_trade_value(
            prospect=prospect,
            team_analysis=rebuilding_analysis
        )

        assert value > 0
        assert isinstance(value, (int, float))

    @pytest.mark.asyncio
    async def test_higher_rating_higher_value(self, recommendation_service, rebuilding_analysis):
        """Higher rated prospects have higher trade value"""
        elite = {"id": "p1", "overall_rating": 95, "position": "C", "eta": "2026", "age": 20}
        good = {"id": "p2", "overall_rating": 80, "position": "C", "eta": "2026", "age": 20}

        elite_value = await recommendation_service._calculate_trade_value(elite, rebuilding_analysis)
        good_value = await recommendation_service._calculate_trade_value(good, rebuilding_analysis)

        assert elite_value > good_value


class TestCalculateFitImprovement:
    """Test fit improvement calculation"""

    @pytest.mark.asyncio
    async def test_fit_improvement_position_upgrade(self, recommendation_service, rebuilding_analysis):
        """Positive fit improvement when trading for need position"""
        receiving = [{"id": "p1", "overall_rating": 85, "position": "C", "eta": "2026", "age": 21}]
        giving = [{"id": "p2", "overall_rating": 85, "position": "1B", "eta": "2026", "age": 21}]

        improvement = await recommendation_service._calculate_fit_improvement(
            prospects_to_receive=receiving,
            prospects_to_give=giving,
            team_analysis=rebuilding_analysis
        )

        # Trading strength (1B) for need (C) = improvement
        assert improvement > 0

    @pytest.mark.asyncio
    async def test_fit_improvement_negative(self, recommendation_service, rebuilding_analysis):
        """Negative fit improvement when trading away need position"""
        receiving = [{"id": "p1", "overall_rating": 85, "position": "1B", "eta": "2026", "age": 21}]
        giving = [{"id": "p2", "overall_rating": 85, "position": "C", "eta": "2026", "age": 21}]

        improvement = await recommendation_service._calculate_fit_improvement(
            prospects_to_receive=receiving,
            prospects_to_give=giving,
            team_analysis=rebuilding_analysis
        )

        # Trading need (C) for strength (1B) = negative improvement
        assert improvement < 0


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_empty_prospects_list(self, recommendation_service, rebuilding_analysis):
        """Handle empty prospects list"""
        recommendations = await recommendation_service.get_recommendations(
            team_analysis=rebuilding_analysis,
            prospects=[],
            limit=10
        )

        assert recommendations == []

    @pytest.mark.asyncio
    async def test_missing_prospect_fields(self, recommendation_service, rebuilding_analysis):
        """Handle prospects with missing fields gracefully"""
        incomplete_prospect = {
            "id": "p1",
            "name": "Incomplete Prospect",
            # Missing position, rating, eta
        }

        # Should not crash
        try:
            fit_score = await recommendation_service._calculate_fit_score(
                prospect=incomplete_prospect,
                team_analysis=rebuilding_analysis
            )
            assert isinstance(fit_score, (int, float))
        except KeyError:
            # Acceptable to raise KeyError for required fields
            pass

    @pytest.mark.asyncio
    async def test_zero_limit(self, recommendation_service, rebuilding_analysis, sample_prospects):
        """Handle limit=0"""
        recommendations = await recommendation_service.get_recommendations(
            team_analysis=rebuilding_analysis,
            prospects=sample_prospects,
            limit=0
        )

        assert recommendations == []
