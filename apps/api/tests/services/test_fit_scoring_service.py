"""
Unit tests for FitScoringService

Tests prospect-team fit scoring algorithms including position matching,
timeline alignment, depth impact, and value calculations.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime

from app.services.fit_scoring_service import FitScoringService
from app.db.models import Prospect, MLPrediction


@pytest.fixture
def fit_service(db_session):
    """Create FitScoringService instance"""
    return FitScoringService(db_session)


@pytest.fixture
def sample_prospect():
    """Sample prospect for testing"""
    prospect = Mock(spec=Prospect)
    prospect.id = 1
    prospect.name = "Test Prospect"
    prospect.position = "C"
    prospect.eta_year = datetime.now().year + 1
    prospect.overall_grade = 60
    return prospect


@pytest.fixture
def contending_team_analysis():
    """Team analysis for contending team"""
    return {
        "competitive_window": {
            "window": "contending",
            "confidence": "high"
        },
        "positional_gap_scores": {
            "C": {
                "gap_score": 9,
                "severity": "high",
                "deficit": 2,
                "urgency": "immediate"
            },
            "OF": {
                "gap_score": 2,
                "severity": "low",
                "deficit": 0
            }
        },
        "weaknesses": ["C", "1B"],
        "position_depth": {
            "C": {"active_count": 0},
            "OF": {"active_count": 5}
        }
    }


@pytest.fixture
def rebuilding_team_analysis():
    """Team analysis for rebuilding team"""
    return {
        "competitive_window": {
            "window": "rebuilding",
            "confidence": "high"
        },
        "positional_gap_scores": {
            "SS": {
                "gap_score": 7,
                "severity": "medium",
                "deficit": 1
            }
        },
        "weaknesses": ["SS", "3B"],
        "position_depth": {
            "SS": {"active_count": 1}
        }
    }


class TestCalculateFitScore:
    """Test overall fit score calculation"""

    @pytest.mark.asyncio
    async def test_perfect_fit_contending_team(self, fit_service, sample_prospect, contending_team_analysis, db_session):
        """Perfect fit: catcher for contending team with catcher need"""
        # Mock ML prediction
        ml_pred = Mock(spec=MLPrediction)
        ml_pred.success_probability = 0.85
        ml_pred.confidence_level = "High"

        db_session.execute = AsyncMock(return_value=Mock(
            scalars=Mock(return_value=Mock(first=Mock(return_value=ml_pred)))
        ))

        fit_score = await fit_service.calculate_fit_score(
            sample_prospect,
            contending_team_analysis
        )

        # Should have high overall score
        assert fit_score["overall_score"] >= 7.0
        assert fit_score["fit_rating"] in ["very_good", "excellent"]
        assert "position_fit" in fit_score
        assert "timeline_fit" in fit_score

    @pytest.mark.asyncio
    async def test_poor_fit_wrong_timeline(self, fit_service, rebuilding_team_analysis, db_session):
        """Poor fit: MLB-ready prospect for rebuilding team"""
        prospect = Mock(spec=Prospect)
        prospect.id = 2
        prospect.position = "SS"
        prospect.eta_year = datetime.now().year  # Ready now
        prospect.overall_grade = 55

        db_session.execute = AsyncMock(return_value=Mock(
            scalars=Mock(return_value=Mock(first=Mock(return_value=None)))
        ))

        fit_score = await fit_service.calculate_fit_score(
            prospect,
            rebuilding_team_analysis
        )

        # Timeline mismatch should lower score
        assert fit_score["timeline_fit"] < 8.0


class TestPositionNeedScore:
    """Test position need scoring"""

    def test_high_gap_score(self, fit_service, sample_prospect):
        """High position gap yields high need score"""
        gap_scores = {
            "C": {"gap_score": 10, "severity": "high", "deficit": 3}
        }
        weaknesses = ["C"]

        score = fit_service._calculate_position_need_score(
            sample_prospect,
            gap_scores,
            weaknesses
        )

        # Should be close to max (10 + bonus capped at 10)
        assert score == 10

    def test_no_position_need(self, fit_service, sample_prospect):
        """No position need yields low score"""
        gap_scores = {
            "C": {"gap_score": 0, "severity": "low", "deficit": 0}
        }
        weaknesses = []

        score = fit_service._calculate_position_need_score(
            sample_prospect,
            gap_scores,
            weaknesses
        )

        assert score == 0


class TestTimelineAlignment:
    """Test timeline alignment scoring"""

    def test_contending_immediate_eta(self, fit_service):
        """Contending team wants immediate ETA"""
        prospect = Mock(spec=Prospect)
        prospect.eta_year = datetime.now().year + 1  # Next year

        window = {"window": "contending"}

        score = fit_service._calculate_timeline_alignment_score(prospect, window)

        assert score == 10  # Perfect alignment

    def test_contending_distant_eta(self, fit_service):
        """Contending team doesn't want distant ETA"""
        prospect = Mock(spec=Prospect)
        prospect.eta_year = datetime.now().year + 4  # 4 years away

        window = {"window": "contending"}

        score = fit_service._calculate_timeline_alignment_score(prospect, window)

        assert score < 6  # Poor alignment

    def test_rebuilding_prefers_future(self, fit_service):
        """Rebuilding team wants future prospects"""
        prospect = Mock(spec=Prospect)
        prospect.eta_year = datetime.now().year + 3  # 3 years away

        window = {"window": "rebuilding"}

        score = fit_service._calculate_timeline_alignment_score(prospect, window)

        assert score >= 9  # Good alignment

    def test_rebuilding_not_immediate(self, fit_service):
        """Rebuilding team less interested in MLB-ready"""
        prospect = Mock(spec=Prospect)
        prospect.eta_year = datetime.now().year  # Ready now

        window = {"window": "rebuilding"}

        score = fit_service._calculate_timeline_alignment_score(prospect, window)

        assert score < 10  # Not perfect fit


class TestDepthImpact:
    """Test depth impact scoring"""

    def test_starter_opportunity(self, fit_service, sample_prospect):
        """High deficit = clear starter opportunity"""
        position_depth = {"C": {"active_count": 0}}
        gap_scores = {"C": {"deficit": 2}}

        score = fit_service._calculate_depth_impact_score(
            sample_prospect,
            position_depth,
            gap_scores
        )

        assert score == 10  # Clear starter role

    def test_depth_piece(self, fit_service, sample_prospect):
        """No deficit = depth piece"""
        position_depth = {"C": {"active_count": 3}}
        gap_scores = {"C": {"deficit": 0}}

        score = fit_service._calculate_depth_impact_score(
            sample_prospect,
            position_depth,
            gap_scores
        )

        assert score == 4  # Just a depth piece


class TestQualityScore:
    """Test prospect quality scoring"""

    def test_high_ml_prediction(self, fit_service, sample_prospect):
        """High ML prediction yields high quality score"""
        ml_pred = Mock(spec=MLPrediction)
        ml_pred.success_probability = 0.9
        ml_pred.confidence_level = "High"

        score = fit_service._calculate_quality_score(sample_prospect, ml_pred)

        assert score >= 8.0  # 0.9 * 10 = 9.0

    def test_medium_confidence_ml(self, fit_service, sample_prospect):
        """Medium confidence ML prediction slightly discounted"""
        ml_pred = Mock(spec=MLPrediction)
        ml_pred.success_probability = 0.8
        ml_pred.confidence_level = "Medium"

        score = fit_service._calculate_quality_score(sample_prospect, ml_pred)

        assert score < 8.0  # 0.8 * 10 * 0.9 = 7.2

    def test_fallback_to_overall_grade(self, fit_service):
        """Use overall grade when ML prediction unavailable"""
        prospect = Mock(spec=Prospect)
        prospect.overall_grade = 60

        score = fit_service._calculate_quality_score(prospect, None)

        # (60 - 20) / 6 = 6.67
        assert 6.0 <= score <= 7.0


class TestValueScore:
    """Test value scoring"""

    def test_high_value_fills_need(self, fit_service, sample_prospect):
        """High value when prospect fills urgent need"""
        position_need_score = 9.0
        weaknesses = ["C"]

        score = fit_service._calculate_value_score(
            sample_prospect,
            position_need_score,
            weaknesses
        )

        # (9.0 * 0.7) + 3 = 9.3
        assert score >= 9.0

    def test_lower_value_no_need(self, fit_service, sample_prospect):
        """Lower value when no critical need"""
        position_need_score = 2.0
        weaknesses = ["OF"]  # Not catcher

        score = fit_service._calculate_value_score(
            sample_prospect,
            position_need_score,
            weaknesses
        )

        assert score < 5.0


class TestFitRating:
    """Test fit rating labels"""

    def test_excellent_rating(self, fit_service):
        """Score >= 8.5 = excellent"""
        assert fit_service._get_fit_rating(9.0) == "excellent"
        assert fit_service._get_fit_rating(8.5) == "excellent"

    def test_very_good_rating(self, fit_service):
        """Score 7.0-8.4 = very good"""
        assert fit_service._get_fit_rating(7.5) == "very_good"
        assert fit_service._get_fit_rating(7.0) == "very_good"

    def test_good_rating(self, fit_service):
        """Score 5.5-6.9 = good"""
        assert fit_service._get_fit_rating(6.0) == "good"

    def test_poor_rating(self, fit_service):
        """Score < 4.0 = poor"""
        assert fit_service._get_fit_rating(3.0) == "poor"


class TestLeagueSpecificFit:
    """Test league-specific fit adjustments"""

    @pytest.mark.asyncio
    async def test_catcher_scarcity_boost(self, fit_service, sample_prospect, contending_team_analysis, db_session):
        """Catchers get scarcity boost"""
        db_session.execute = AsyncMock(return_value=Mock(
            scalars=Mock(return_value=Mock(first=Mock(return_value=None)))
        ))

        league_settings = {"scoring_system": "standard"}

        fit_score = await fit_service.calculate_league_specific_fit(
            sample_prospect,
            contending_team_analysis,
            league_settings
        )

        # Should have league adjustments
        assert "league_adjustments" in fit_score
        assert fit_score["league_adjustments"]["position_scarcity"] == "high"

    def test_position_scarcity_assessment(self, fit_service):
        """Assess position scarcity correctly"""
        assert fit_service._assess_position_scarcity("C", {}) == "high"
        assert fit_service._assess_position_scarcity("RP", {}) == "high"
        assert fit_service._assess_position_scarcity("OF", {}) == "low"
        assert fit_service._assess_position_scarcity("SS", {}) == "medium"
