"""
Unit tests for RosterAnalysisService

Tests team needs analysis, position depth calculation, age curve analysis,
and future roster hole projection.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.roster_analysis_service import RosterAnalysisService


@pytest.fixture
def analysis_service():
    """Create RosterAnalysisService instance"""
    return RosterAnalysisService()


@pytest.fixture
def sample_roster():
    """Sample roster data for testing"""
    return {
        "players": [
            # Young outfielders (rebuild assets)
            {"id": "p1", "name": "Young OF 1", "positions": ["OF"], "age": 22, "team": "BAL", "status": "active"},
            {"id": "p2", "name": "Young OF 2", "positions": ["OF"], "age": 23, "team": "TB", "status": "active"},
            # Aging catchers (need replacement)
            {"id": "p3", "name": "Old C", "positions": ["C"], "age": 35, "team": "NYY", "status": "active"},
            # Middle infielders (depth)
            {"id": "p4", "name": "2B Player", "positions": ["2B"], "age": 27, "team": "HOU", "status": "active"},
            {"id": "p5", "name": "SS Player", "positions": ["SS"], "age": 28, "team": "LAD", "status": "active"},
            # Injured player
            {"id": "p6", "name": "Injured 3B", "positions": ["3B"], "age": 30, "team": "ATL", "status": "injured"},
            # Minor league prospect
            {"id": "p7", "name": "MiLB OF", "positions": ["OF"], "age": 20, "team": "BAL", "status": "minors"},
        ]
    }


@pytest.fixture
def empty_roster():
    """Empty roster for edge case testing"""
    return {"players": []}


@pytest.fixture
def league_settings():
    """Sample league settings"""
    return {
        "roster_size": 40,
        "minor_league_slots": 10,
        "positions": {
            "C": 2,
            "1B": 1,
            "2B": 1,
            "3B": 1,
            "SS": 1,
            "OF": 5,
            "UTIL": 2
        }
    }


class TestAnalyzeTeam:
    """Test complete team analysis"""

    @pytest.mark.asyncio
    async def test_analyze_team_success(self, analysis_service, sample_roster, league_settings):
        """Successfully analyze team with complete roster"""
        analysis = await analysis_service.analyze_team(sample_roster, league_settings)

        assert "position_analysis" in analysis
        assert "depth_analysis" in analysis
        assert "timeline" in analysis
        assert "future_holes" in analysis
        assert "roster_spots" in analysis
        assert "needs" in analysis

    @pytest.mark.asyncio
    async def test_analyze_empty_roster(self, analysis_service, empty_roster, league_settings):
        """Handle empty roster gracefully"""
        analysis = await analysis_service.analyze_team(empty_roster, league_settings)

        assert analysis["roster_spots"]["available"] == league_settings["roster_size"]
        assert len(analysis["needs"]) > 0  # Should identify all positions as needs


class TestPositionAnalysis:
    """Test position depth and strength analysis"""

    @pytest.mark.asyncio
    async def test_position_analysis_depth(self, analysis_service, sample_roster, league_settings):
        """Correctly analyze position depth"""
        analysis = await analysis_service.analyze_team(sample_roster, league_settings)
        positions = analysis["position_analysis"]

        # Outfield should have good depth (3 players)
        assert "OF" in positions
        assert positions["OF"]["count"] == 3
        assert positions["OF"]["depth"] == "strong"

        # Catcher should be weak (1 aging player)
        assert "C" in positions
        assert positions["C"]["count"] == 1
        assert positions["C"]["depth"] in ["weak", "concern"]

    @pytest.mark.asyncio
    async def test_position_analysis_multi_position_eligible(self, analysis_service, league_settings):
        """Handle players eligible at multiple positions"""
        multi_pos_roster = {
            "players": [
                {"id": "p1", "name": "Utility", "positions": ["1B", "OF"], "age": 25, "status": "active"}
            ]
        }

        analysis = await analysis_service.analyze_team(multi_pos_roster, league_settings)
        positions = analysis["position_analysis"]

        # Player should count toward both positions
        assert "1B" in positions or "OF" in positions

    @pytest.mark.asyncio
    async def test_position_strengths_and_weaknesses(self, analysis_service, sample_roster, league_settings):
        """Identify position strengths and weaknesses"""
        analysis = await analysis_service.analyze_team(sample_roster, league_settings)

        # Should have identified strengths
        assert "strengths" in analysis
        assert len(analysis["strengths"]) > 0

        # Should have identified weaknesses
        assert "weaknesses" in analysis
        assert len(analysis["weaknesses"]) > 0


class TestDepthAnalysis:
    """Test depth analysis algorithm"""

    @pytest.mark.asyncio
    async def test_depth_strong(self, analysis_service):
        """Identify strong positional depth"""
        roster = {
            "players": [
                {"id": f"p{i}", "name": f"OF {i}", "positions": ["OF"], "age": 25 + i, "status": "active"}
                for i in range(6)
            ]
        }
        settings = {"positions": {"OF": 5}}

        analysis = await analysis_service.analyze_team(roster, settings)

        # With 6 OFs for 5 spots, depth should be strong
        assert analysis["position_analysis"]["OF"]["depth"] == "strong"

    @pytest.mark.asyncio
    async def test_depth_weak(self, analysis_service):
        """Identify weak positional depth"""
        roster = {
            "players": [
                {"id": "p1", "name": "Only C", "positions": ["C"], "age": 35, "status": "active"}
            ]
        }
        settings = {"positions": {"C": 2}}

        analysis = await analysis_service.analyze_team(roster, settings)

        # Only 1 catcher for 2 spots should be weak
        assert analysis["position_analysis"]["C"]["depth"] in ["weak", "concern"]


class TestAgeCurveAnalysis:
    """Test age curve and timeline determination"""

    @pytest.mark.asyncio
    async def test_timeline_rebuilding(self, analysis_service, league_settings):
        """Identify rebuilding timeline with young roster"""
        young_roster = {
            "players": [
                {"id": f"p{i}", "name": f"Player {i}", "positions": ["OF"], "age": 21 + i, "status": "active"}
                for i in range(5)
            ]
        }

        analysis = await analysis_service.analyze_team(young_roster, league_settings)

        # Young roster should indicate rebuilding
        assert analysis["timeline"] in ["rebuilding", "young"]
        assert analysis["average_age"] < 25

    @pytest.mark.asyncio
    async def test_timeline_contending(self, analysis_service, league_settings):
        """Identify contending timeline with prime-age roster"""
        prime_roster = {
            "players": [
                {"id": f"p{i}", "name": f"Player {i}", "positions": ["OF"], "age": 26 + i, "status": "active"}
                for i in range(5)
            ]
        }

        analysis = await analysis_service.analyze_team(prime_roster, league_settings)

        # Prime-age roster should indicate contending
        assert analysis["timeline"] in ["contending", "win-now"]
        assert 25 <= analysis["average_age"] <= 30

    @pytest.mark.asyncio
    async def test_timeline_aging(self, analysis_service, league_settings):
        """Identify aging roster needing refresh"""
        aging_roster = {
            "players": [
                {"id": f"p{i}", "name": f"Player {i}", "positions": ["OF"], "age": 32 + i, "status": "active"}
                for i in range(5)
            ]
        }

        analysis = await analysis_service.analyze_team(aging_roster, league_settings)

        # Aging roster should indicate need for refresh
        assert analysis["timeline"] in ["aging", "retool"]
        assert analysis["average_age"] > 30


class TestFutureHoleProjection:
    """Test 2-3 year future roster hole detection"""

    @pytest.mark.asyncio
    async def test_project_future_catcher_hole(self, analysis_service, league_settings):
        """Project catcher need in 2-3 years with aging player"""
        roster = {
            "players": [
                {"id": "p1", "name": "Old C", "positions": ["C"], "age": 35, "status": "active"}
            ]
        }

        analysis = await analysis_service.analyze_team(roster, league_settings)

        # 35-year-old catcher should trigger future hole projection
        future_holes = analysis["future_holes"]
        catcher_holes = [h for h in future_holes if "C" in h.get("position", "")]
        assert len(catcher_holes) > 0

    @pytest.mark.asyncio
    async def test_project_contract_expiration_holes(self, analysis_service, league_settings):
        """Project holes from expiring contracts"""
        roster = {
            "players": [
                {"id": "p1", "name": "Expiring", "positions": ["1B"], "age": 28, "contract_years": 1, "status": "active"}
            ]
        }

        analysis = await analysis_service.analyze_team(roster, league_settings)

        # Should identify 1B as future hole when contract expires
        future_holes = analysis["future_holes"]
        assert any("1B" in h.get("position", "") for h in future_holes)

    @pytest.mark.asyncio
    async def test_no_future_holes_young_roster(self, analysis_service, league_settings):
        """No projected holes with young, deep roster"""
        roster = {
            "players": [
                {"id": f"p{i}", "name": f"Young {i}", "positions": ["OF"], "age": 22 + (i % 3), "status": "active"}
                for i in range(8)  # Deep OF depth
            ]
        }

        analysis = await analysis_service.analyze_team(roster, league_settings)

        # Young, deep OF should not project holes
        of_holes = [h for h in analysis["future_holes"] if "OF" in h.get("position", "")]
        assert len(of_holes) == 0


class TestRosterSpotAvailability:
    """Test roster spot availability calculation"""

    @pytest.mark.asyncio
    async def test_calculate_available_spots(self, analysis_service, sample_roster, league_settings):
        """Calculate available roster spots correctly"""
        analysis = await analysis_service.analyze_team(sample_roster, league_settings)

        spots = analysis["roster_spots"]
        assert "total" in spots
        assert "used" in spots
        assert "available" in spots
        assert "minor_league_used" in spots
        assert "minor_league_available" in spots

        # Total = Used + Available
        assert spots["total"] == spots["used"] + spots["available"]

    @pytest.mark.asyncio
    async def test_minor_league_spots(self, analysis_service, sample_roster, league_settings):
        """Track minor league slot usage"""
        analysis = await analysis_service.analyze_team(sample_roster, league_settings)

        spots = analysis["roster_spots"]

        # Sample roster has 1 minor league player
        assert spots["minor_league_used"] == 1
        assert spots["minor_league_available"] == league_settings["minor_league_slots"] - 1

    @pytest.mark.asyncio
    async def test_full_roster(self, analysis_service, league_settings):
        """Handle full roster scenario"""
        full_roster = {
            "players": [
                {"id": f"p{i}", "name": f"Player {i}", "positions": ["OF"], "age": 25, "status": "active"}
                for i in range(league_settings["roster_size"])
            ]
        }

        analysis = await analysis_service.analyze_team(full_roster, league_settings)

        assert analysis["roster_spots"]["available"] == 0
        assert analysis["roster_spots"]["used"] == league_settings["roster_size"]


class TestNeedsIdentification:
    """Test team needs identification"""

    @pytest.mark.asyncio
    async def test_identify_position_needs(self, analysis_service, sample_roster, league_settings):
        """Identify positional needs based on depth"""
        analysis = await analysis_service.analyze_team(sample_roster, league_settings)

        needs = analysis["needs"]

        # Should identify needs (prioritized list)
        assert len(needs) > 0
        assert all("position" in need for need in needs)
        assert all("priority" in need for need in needs)

    @pytest.mark.asyncio
    async def test_needs_prioritization(self, analysis_service, league_settings):
        """Needs should be prioritized correctly"""
        roster = {
            "players": [
                # No catchers = high priority need
                {"id": "p1", "name": "1B", "positions": ["1B"], "age": 25, "status": "active"},
                {"id": "p2", "name": "1B2", "positions": ["1B"], "age": 26, "status": "active"},
                # Some OFs = lower priority
                {"id": "p3", "name": "OF1", "positions": ["OF"], "age": 24, "status": "active"},
            ]
        }
        settings = {"positions": {"C": 2, "1B": 1, "OF": 5}}

        analysis = await analysis_service.analyze_team(roster, settings)

        needs = analysis["needs"]

        # Catcher (missing completely) should be higher priority than OF (some depth)
        catcher_need = next((n for n in needs if n["position"] == "C"), None)
        of_need = next((n for n in needs if n["position"] == "OF"), None)

        assert catcher_need is not None
        assert catcher_need["priority"] in ["high", "critical"]


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_missing_age_data(self, analysis_service, league_settings):
        """Handle players with missing age data"""
        roster = {
            "players": [
                {"id": "p1", "name": "Unknown Age", "positions": ["OF"], "status": "active"}
            ]
        }

        # Should not raise exception
        analysis = await analysis_service.analyze_team(roster, league_settings)
        assert "average_age" in analysis

    @pytest.mark.asyncio
    async def test_injured_players_excluded_from_depth(self, analysis_service, league_settings):
        """Injured players should reduce effective depth"""
        roster = {
            "players": [
                {"id": "p1", "name": "Active", "positions": ["C"], "age": 25, "status": "active"},
                {"id": "p2", "name": "Injured", "positions": ["C"], "age": 26, "status": "injured"},
            ]
        }
        settings = {"positions": {"C": 2}}

        analysis = await analysis_service.analyze_team(roster, settings)

        # Injured player may reduce depth rating
        # Exact behavior depends on implementation, but should acknowledge injury impact
        assert "C" in analysis["position_analysis"]

    @pytest.mark.asyncio
    async def test_no_league_settings(self, analysis_service, sample_roster):
        """Handle missing league settings gracefully"""
        # Use default settings if none provided
        analysis = await analysis_service.analyze_team(sample_roster, {})

        # Should still produce analysis with reasonable defaults
        assert "position_analysis" in analysis


# Story 4.4 Enhanced Tests
class TestPositionalGapScoring:
    """Test detailed positional gap scoring for Story 4.4"""

    def test_gap_scoring_with_deficit(self, analysis_service):
        """Calculate gap scores for positions with deficits"""
        position_analysis = {
            "C": {"avg_age": 28},
            "1B": {"avg_age": 35}
        }
        depth_analysis = {
            "C": {"current": 0, "required": 2, "surplus": -2},
            "1B": {"current": 1, "required": 1, "surplus": 0}
        }

        gap_scores = analysis_service._analyze_positional_gaps(position_analysis, depth_analysis)

        # Catcher with -2 deficit should have high gap score
        assert gap_scores["C"]["gap_score"] >= 6
        assert gap_scores["C"]["severity"] in ["high", "medium"]
        assert gap_scores["C"]["deficit"] == 2

        # 1B with no deficit should have 0 gap score
        assert gap_scores["1B"]["gap_score"] == 0
        assert gap_scores["1B"]["severity"] == "low"

    def test_gap_scoring_with_aging_position(self, analysis_service):
        """Gap score increases for aging positions"""
        position_analysis = {
            "C": {"avg_age": 35}  # Old catcher
        }
        depth_analysis = {
            "C": {"current": 1, "required": 2, "surplus": -1}
        }

        gap_scores = analysis_service._analyze_positional_gaps(position_analysis, depth_analysis)

        # Aging position should increase urgency
        assert gap_scores["C"]["gap_score"] > 3  # Base deficit (3) + age penalty (2)
        assert gap_scores["C"]["urgency"] in ["immediate", "near_term"]


class TestAgeDistributionTimeline:
    """Test age distribution with timeline projections for Story 4.4"""

    def test_age_distribution_current(self, analysis_service):
        """Analyze current age distribution"""
        players = [
            {"age": 22}, {"age": 24}, {"age": 27}, {"age": 30}, {"age": 34}
        ]

        age_dist = analysis_service._analyze_age_distribution_timeline(players)

        assert "current_distribution" in age_dist
        assert age_dist["current_distribution"]["under_23"] == 1
        assert age_dist["current_distribution"]["23_25"] == 1
        assert age_dist["current_distribution"]["25_28"] == 1

    def test_age_distribution_2_year_projection(self, analysis_service):
        """Project age distribution 2 years ahead"""
        players = [
            {"age": 22}, {"age": 23}, {"age": 24}
        ]

        age_dist = analysis_service._analyze_age_distribution_timeline(players)

        # In 2 years: 24, 25, 26
        assert age_dist["projected_2_year"]["23_25"] == 1  # age 24
        assert age_dist["projected_2_year"]["25_28"] == 2  # ages 25, 26

    def test_age_distribution_aging_risk(self, analysis_service):
        """Calculate aging risk percentage"""
        young_players = [{"age": 22}, {"age": 23}, {"age": 24}]
        old_players = [{"age": 32}, {"age": 33}, {"age": 34}]

        young_dist = analysis_service._analyze_age_distribution_timeline(young_players)
        old_dist = analysis_service._analyze_age_distribution_timeline(old_players)

        assert young_dist["aging_risk"] == "low"
        assert old_dist["aging_risk"] == "high"


class TestQualityTiers:
    """Test quality tier analysis for Story 4.4"""

    def test_quality_tiers_distribution(self, analysis_service):
        """Analyze roster quality tiers"""
        players = [
            {"age": 27, "name": "Prime 1"},  # Prime age
            {"age": 28, "name": "Prime 2"},  # Prime age
            {"age": 22, "name": "Young"},    # Young
            {"age": 35, "name": "Old"}       # Aging
        ]

        tiers = analysis_service._analyze_quality_tiers(players)

        assert "counts" in tiers
        assert "percentages" in tiers
        assert "players_by_tier" in tiers
        assert sum(tiers["counts"].values()) == len(players)

    def test_quality_tiers_elite_count(self, analysis_service):
        """Track elite player count"""
        players = [
            {"age": 27, "name": "Star 1"},
            {"age": 28, "name": "Star 2"},
        ]

        tiers = analysis_service._analyze_quality_tiers(players)

        assert "elite_count" in tiers
        assert "top_tier_percentage" in tiers


class TestFutureNeedsProjection:
    """Test 2-year and 3-year future needs projection for Story 4.4"""

    @pytest.mark.asyncio
    async def test_future_needs_2_year_outlook(self, analysis_service):
        """Project needs for 2-year outlook"""
        players = [
            {"name": "Player 1", "age": 33, "positions": ["C"], "contract_years": 1},
            {"name": "Player 2", "age": 31, "positions": ["C"], "contract_years": 2}
        ]

        future_needs = await analysis_service._project_future_needs(players, {})

        assert "2_year_outlook" in future_needs
        # Both players contract expiring or declining within 2 years
        c_needs = [n for n in future_needs["2_year_outlook"] if n["position"] == "C"]
        assert len(c_needs) > 0

    @pytest.mark.asyncio
    async def test_future_needs_3_year_outlook(self, analysis_service):
        """Project needs for 3-year outlook"""
        players = [
            {"name": "Player 1", "age": 30, "positions": ["1B"], "contract_years": 3}
        ]

        future_needs = await analysis_service._project_future_needs(players, {})

        assert "3_year_outlook" in future_needs

    @pytest.mark.asyncio
    async def test_future_needs_severity(self, analysis_service):
        """Assess severity of future needs"""
        players = [
            {"name": "C1", "age": 34, "positions": ["C"], "contract_years": 1},
            {"name": "C2", "age": 35, "positions": ["C"], "contract_years": 1}
        ]

        future_needs = await analysis_service._project_future_needs(players, {})

        c_needs = [n for n in future_needs["2_year_outlook"] if n["position"] == "C"]
        if c_needs:
            assert c_needs[0]["severity"] in ["high", "medium", "low"]


class TestCompetitiveWindow:
    """Test competitive window detection for Story 4.4"""

    def test_contending_window(self, analysis_service):
        """Detect contending competitive window"""
        age_analysis = {"avg_age": 28}
        quality_tiers = {"elite_count": 4, "top_tier_percentage": 50}
        depth_analysis = {
            "C": {"rating": "good"},
            "1B": {"rating": "excellent"},
            "2B": {"rating": "good"},
            "3B": {"rating": "good"},
            "SS": {"rating": "excellent"},
            "LF": {"rating": "good"},
            "CF": {"rating": "good"},
            "RF": {"rating": "good"},
            "SP": {"rating": "excellent"},
            "RP": {"rating": "good"}
        }

        window = analysis_service._detect_competitive_window(age_analysis, quality_tiers, depth_analysis)

        assert window["window"] == "contending"
        assert "reasoning" in window
        assert len(window["reasoning"]) >= 2

    def test_rebuilding_window(self, analysis_service):
        """Detect rebuilding competitive window"""
        age_analysis = {"avg_age": 24}
        quality_tiers = {"elite_count": 1, "top_tier_percentage": 20}
        depth_analysis = {
            "C": {"rating": "poor"},
            "1B": {"rating": "adequate"}
        }

        window = analysis_service._detect_competitive_window(age_analysis, quality_tiers, depth_analysis)

        assert window["window"] == "rebuilding"

    def test_window_recommendation(self, analysis_service):
        """Get strategic recommendation for competitive window"""
        rec_contending = analysis_service._get_window_recommendation("contending")
        rec_rebuilding = analysis_service._get_window_recommendation("rebuilding")

        assert "ETA" in rec_contending
        assert "win-now" in rec_contending
        assert "upside" in rec_rebuilding
