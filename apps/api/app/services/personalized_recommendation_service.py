"""
Personalized Recommendation Service

Generates prospect recommendations tailored to team needs, timeline,
and available roster spots based on Fantrax roster analysis.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.db.models import Prospect, ProspectStats, ScoutingGrades
from app.services.roster_analysis_service import RosterAnalysisService
from app.services.fantrax_api_service import FantraxAPIService
from app.core.cache_manager import CacheManager
import json
import logging

logger = logging.getLogger(__name__)

# Initialize cache manager
cache_manager = CacheManager()


class PersonalizedRecommendationService:
    """
    Service for generating personalized prospect recommendations

    Integrates roster analysis with prospect rankings to provide
    targeted recommendations based on team needs and timeline.
    """

    # Trade value tiers based on prospect ranking
    TRADE_VALUE_TIERS = {
        "Elite": (1, 25),
        "High": (26, 75),
        "Medium": (76, 150),
        "Low": (151, 300),
        "Speculative": (301, 500)
    }

    # Timeline to ETA mapping
    TIMELINE_ETA_PREFERENCES = {
        "rebuilding": (2027, 2030),      # Future-focused
        "emerging": (2026, 2028),         # Medium-term
        "balanced": (2025, 2027),         # Flexible
        "competing": (2025, 2026),        # Win-soon
        "win-now": (2025, 2025),          # Immediate help
        "retooling": (2026, 2027)         # Quick rebuild
    }

    def __init__(self, db: AsyncSession, user_id: int):
        """
        Initialize Personalized Recommendation Service

        @param db - Database session for prospect queries
        @param user_id - User ID for roster access

        @since 1.0.0
        """
        self.db = db
        self.user_id = user_id
        self.roster_analysis = RosterAnalysisService(db, user_id)
        self.fantrax_api = FantraxAPIService(db, user_id)

    async def get_recommendations(
        self,
        league_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get personalized prospect recommendations for a league

        @param league_id - Fantrax league ID
        @param limit - Maximum number of recommendations

        @returns List of recommended prospects with fit scores

        @performance
        - Response time: 1-2 seconds
        - Cached for 30 minutes

        @since 1.0.0
        """
        # Check cache first
        cache_key = f"recommendations:{self.user_id}:{league_id}:{limit}"
        cached_recs = await cache_manager.get(cache_key)
        if cached_recs:
            return json.loads(cached_recs)

        # Get team analysis
        analysis = await self.roster_analysis.analyze_team(league_id)

        # Extract key factors for recommendations
        weaknesses = analysis.get("weaknesses", [])
        future_holes = analysis.get("future_holes", [])
        timeline = analysis.get("timeline", "balanced")
        available_spots = analysis.get("available_spots", 0)

        # Get target positions
        target_positions = set(weaknesses)
        for hole in future_holes:
            target_positions.add(hole["position"])

        # If no specific needs, recommend top prospects
        if not target_positions:
            target_positions = set(["SS", "CF", "SP"])  # High-value positions

        # Get ETA range based on timeline
        eta_range = self.TIMELINE_ETA_PREFERENCES.get(timeline, (2025, 2027))

        # Query prospects matching criteria
        prospects = await self._query_matching_prospects(
            list(target_positions),
            eta_range,
            limit * 3  # Get extra for scoring and filtering
        )

        # Score and rank prospects
        scored_prospects = []
        for prospect in prospects:
            fit_score = await self._calculate_fit_score(
                prospect,
                analysis,
                weaknesses,
                future_holes
            )

            if fit_score > 0:  # Only include prospects with positive fit
                scored_prospects.append({
                    "prospect": prospect,
                    "fit_score": fit_score
                })

        # Sort by fit score
        scored_prospects.sort(key=lambda x: x["fit_score"], reverse=True)

        # Format recommendations
        recommendations = []
        for item in scored_prospects[:limit]:
            prospect = item["prospect"]
            fit_score = item["fit_score"]

            recommendation = {
                "prospect_id": prospect.id,
                "name": prospect.name,
                "position": prospect.position,
                "organization": prospect.organization or "N/A",
                "eta_year": prospect.eta_year or datetime.now().year + 2,
                "fit_score": round(fit_score, 1),
                "reason": self._generate_recommendation_reason(
                    prospect,
                    analysis,
                    weaknesses,
                    future_holes
                ),
                "trade_value": self._determine_trade_value(prospect),
                "age": prospect.age
            }
            recommendations.append(recommendation)

        # Cache the results
        await cache_manager.set(
            cache_key,
            json.dumps(recommendations),
            ttl=1800  # 30 minutes cache
        )

        return recommendations

    async def analyze_trade(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a potential trade for value and team fit

        @param trade_data - Trade details including players/picks exchanged

        @returns Trade analysis with recommendations

        @performance
        - Response time: 1-2 seconds
        - Complex valuation calculations

        @since 1.0.0
        """
        league_id = trade_data.get("league_id")
        players_acquiring = trade_data.get("acquiring", [])
        players_giving = trade_data.get("giving", [])

        # Get team analysis for context
        analysis = await self.roster_analysis.analyze_team(league_id)

        # Calculate value of each side
        acquiring_value = await self._calculate_trade_value(players_acquiring)
        giving_value = await self._calculate_trade_value(players_giving)

        # Calculate fit improvement
        fit_improvement = await self._calculate_fit_improvement(
            players_acquiring,
            players_giving,
            analysis
        )

        # Generate recommendation
        value_diff = acquiring_value - giving_value
        recommendation = self._generate_trade_recommendation(
            value_diff,
            fit_improvement,
            analysis["timeline"]
        )

        return {
            "acquiring_value": acquiring_value,
            "giving_value": giving_value,
            "value_difference": value_diff,
            "fit_improvement": fit_improvement,
            "recommendation": recommendation,
            "confidence": self._calculate_confidence(value_diff, fit_improvement),
            "analysis": {
                "timeline_match": self._assess_timeline_match(
                    players_acquiring,
                    analysis["timeline"]
                ),
                "need_addressed": self._check_needs_addressed(
                    players_acquiring,
                    analysis["weaknesses"]
                ),
                "roster_impact": self._assess_roster_impact(
                    players_acquiring,
                    players_giving,
                    analysis
                )
            }
        }

    async def _query_matching_prospects(
        self,
        positions: List[str],
        eta_range: Tuple[int, int],
        limit: int
    ) -> List[Prospect]:
        """
        Query prospects matching position and ETA criteria

        @param positions - Target positions
        @param eta_range - ETA year range (min, max)
        @param limit - Maximum prospects to return

        @returns List of matching prospects

        @since 1.0.0
        """
        stmt = (
            select(Prospect)
            .where(
                and_(
                    Prospect.position.in_(positions),
                    Prospect.eta_year >= eta_range[0],
                    Prospect.eta_year <= eta_range[1]
                )
            )
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        prospects = result.scalars().all()

        return list(prospects)

    async def _calculate_fit_score(
        self,
        prospect: Prospect,
        analysis: Dict[str, Any],
        weaknesses: List[str],
        future_holes: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate how well a prospect fits team needs

        @param prospect - Prospect to evaluate
        @param analysis - Team analysis data
        @param weaknesses - Current weak positions
        @param future_holes - Projected future needs

        @returns Fit score (0-100)

        @since 1.0.0
        """
        score = 0.0

        # Base score for matching current weakness (30 points)
        if prospect.position in weaknesses:
            score += 30.0

        # Score for matching future holes (40 points max)
        for hole in future_holes:
            if hole["position"] == prospect.position:
                # Weight by urgency and severity
                years_until = hole["year"] - datetime.now().year
                urgency_multiplier = max(0.5, 1.5 - (years_until * 0.2))

                severity_scores = {"high": 15, "medium": 10, "low": 5}
                severity_score = severity_scores.get(hole["severity"], 0)

                score += severity_score * urgency_multiplier

        # Score for timeline match (20 points)
        timeline = analysis.get("timeline", "balanced")
        eta_range = self.TIMELINE_ETA_PREFERENCES.get(timeline, (2025, 2027))

        if prospect.eta_year:
            if eta_range[0] <= prospect.eta_year <= eta_range[1]:
                score += 20.0
            elif eta_range[0] - 1 <= prospect.eta_year <= eta_range[1] + 1:
                score += 10.0  # Partial credit for close match

        # Bonus for high-value positions (10 points)
        high_value_positions = ["SS", "CF", "SP", "C"]
        if prospect.position in high_value_positions:
            score += 10.0

        # Get scouting grades to adjust score
        stmt = select(ScoutingGrades).where(
            ScoutingGrades.prospect_id == prospect.id
        ).limit(1)
        result = await self.db.execute(stmt)
        grades = result.scalar_one_or_none()

        if grades:
            # Adjust based on overall grade (±10 points)
            grade_adjustments = {
                "80": 10,
                "70": 7,
                "60": 5,
                "55": 3,
                "50": 0,
                "45": -3,
                "40": -5
            }
            overall_grade = str(grades.overall_future_value)
            score += grade_adjustments.get(overall_grade, 0)

        return min(100.0, max(0.0, score))

    def _generate_recommendation_reason(
        self,
        prospect: Prospect,
        analysis: Dict[str, Any],
        weaknesses: List[str],
        future_holes: List[Dict[str, Any]]
    ) -> str:
        """
        Generate human-readable recommendation reason

        @param prospect - Prospect being recommended
        @param analysis - Team analysis
        @param weaknesses - Current weaknesses
        @param future_holes - Future needs

        @returns Recommendation reason text

        @since 1.0.0
        """
        reasons = []

        # Check current need
        if prospect.position in weaknesses:
            reasons.append(f"fills current {prospect.position} need")

        # Check future need
        for hole in future_holes:
            if hole["position"] == prospect.position:
                reasons.append(f"addresses {hole['year']} {prospect.position} hole")
                break

        # Timeline match
        timeline = analysis.get("timeline", "balanced")
        eta = prospect.eta_year or datetime.now().year + 2

        timeline_messages = {
            "rebuilding": "fits rebuilding timeline",
            "competing": "ready to contribute soon",
            "win-now": "immediate impact potential",
            "emerging": "aligns with team emergence",
            "balanced": "versatile timeline fit",
            "retooling": "helps quick turnaround"
        }
        reasons.append(timeline_messages.get(timeline, "good timeline fit"))

        # High value position
        if prospect.position in ["SS", "CF", "SP", "C"]:
            reasons.append("premium position")

        return ", ".join(reasons).capitalize()

    def _determine_trade_value(self, prospect: Prospect) -> str:
        """
        Determine prospect's trade value tier

        @param prospect - Prospect to evaluate

        @returns Trade value tier

        @since 1.0.0
        """
        # This would ideally use a ranking system
        # For now, use a simple age/ETA based heuristic
        eta = prospect.eta_year or 2027
        age = prospect.age or 22
        current_year = datetime.now().year

        years_away = eta - current_year

        if years_away <= 1 and age <= 23:
            return "High"
        elif years_away <= 2 and age <= 24:
            return "Medium"
        elif years_away <= 3:
            return "Medium"
        else:
            return "Speculative"

    async def _calculate_trade_value(self, players: List[Dict[str, Any]]) -> float:
        """
        Calculate total trade value for a group of players

        @param players - List of players with IDs

        @returns Total trade value score

        @since 1.0.0
        """
        total_value = 0.0

        for player in players:
            if player.get("type") == "prospect":
                # Query prospect from database
                stmt = select(Prospect).where(Prospect.id == player["id"])
                result = await self.db.execute(stmt)
                prospect = result.scalar_one_or_none()

                if prospect:
                    # Simple value calculation
                    eta = prospect.eta_year or datetime.now().year + 2
                    years_away = max(0, eta - datetime.now().year)

                    # Base value decreases with distance
                    base_value = max(10, 100 - (years_away * 15))

                    # Adjust for position
                    position_multipliers = {
                        "SS": 1.2, "CF": 1.2, "C": 1.15,
                        "SP": 1.1, "3B": 1.0, "2B": 0.95,
                        "1B": 0.9, "LF": 0.9, "RF": 0.9,
                        "DH": 0.8, "RP": 0.85
                    }
                    multiplier = position_multipliers.get(prospect.position, 1.0)

                    total_value += base_value * multiplier
            else:
                # Major league player - placeholder value
                total_value += player.get("value", 50)

        return total_value

    async def _calculate_fit_improvement(
        self,
        acquiring: List[Dict[str, Any]],
        giving: List[Dict[str, Any]],
        analysis: Dict[str, Any]
    ) -> float:
        """
        Calculate how much trade improves team fit

        @param acquiring - Players being acquired
        @param giving - Players being given up
        @param analysis - Team analysis

        @returns Fit improvement score (-100 to 100)

        @since 1.0.0
        """
        improvement = 0.0
        weaknesses = analysis.get("weaknesses", [])

        # Check if acquiring addresses weaknesses
        for player in acquiring:
            position = player.get("position")
            if position in weaknesses:
                improvement += 30.0

        # Penalize if giving up strength positions
        strengths = analysis.get("strengths", [])
        for player in giving:
            position = player.get("position")
            if position in strengths:
                improvement -= 20.0

        return improvement

    def _generate_trade_recommendation(
        self,
        value_diff: float,
        fit_improvement: float,
        timeline: str
    ) -> str:
        """
        Generate trade recommendation

        @param value_diff - Value difference (positive = getting more)
        @param fit_improvement - Fit improvement score
        @param timeline - Team timeline

        @returns Recommendation text

        @since 1.0.0
        """
        if value_diff > 20 and fit_improvement > 20:
            return "Strong Accept - Great value and excellent fit"
        elif value_diff > 20:
            return "Accept - Good value gain"
        elif fit_improvement > 30:
            return "Accept - Significantly improves team fit"
        elif value_diff > 0 and fit_improvement > 0:
            return "Lean Accept - Slight overall improvement"
        elif abs(value_diff) < 10 and abs(fit_improvement) < 10:
            return "Neutral - Even trade, personal preference"
        elif value_diff < -20 and fit_improvement < -20:
            return "Strong Reject - Poor value and bad fit"
        elif value_diff < -20:
            return "Reject - Losing too much value"
        elif fit_improvement < -30:
            return "Reject - Hurts team composition"
        else:
            return "Lean Reject - Slight overall loss"

    def _calculate_confidence(self, value_diff: float, fit_improvement: float) -> str:
        """
        Calculate recommendation confidence level

        @param value_diff - Value difference
        @param fit_improvement - Fit improvement

        @returns Confidence level (high, medium, low)

        @since 1.0.0
        """
        total_magnitude = abs(value_diff) + abs(fit_improvement)

        if total_magnitude > 60:
            return "high"
        elif total_magnitude > 30:
            return "medium"
        else:
            return "low"

    def _assess_timeline_match(
        self,
        players: List[Dict[str, Any]],
        timeline: str
    ) -> str:
        """
        Assess if acquired players match team timeline

        @param players - Players being acquired
        @param timeline - Team timeline

        @returns Match assessment

        @since 1.0.0
        """
        # Simplified assessment
        if timeline in ["win-now", "competing"]:
            return "Acquiring MLB-ready players recommended"
        elif timeline == "rebuilding":
            return "Acquiring prospects recommended"
        else:
            return "Flexible timeline allows various approaches"

    def _check_needs_addressed(
        self,
        players: List[Dict[str, Any]],
        weaknesses: List[str]
    ) -> bool:
        """
        Check if trade addresses team needs

        @param players - Players being acquired
        @param weaknesses - Team weaknesses

        @returns True if needs addressed

        @since 1.0.0
        """
        for player in players:
            if player.get("position") in weaknesses:
                return True
        return False

    def _assess_roster_impact(
        self,
        acquiring: List[Dict[str, Any]],
        giving: List[Dict[str, Any]],
        analysis: Dict[str, Any]
    ) -> str:
        """
        Assess overall roster impact

        @param acquiring - Players acquired
        @param giving - Players given up
        @param analysis - Team analysis

        @returns Impact assessment

        @since 1.0.0
        """
        net_players = len(acquiring) - len(giving)

        if net_players > 0:
            return f"Adding {net_players} roster spot(s) - ensure space available"
        elif net_players < 0:
            return f"Opening {abs(net_players)} roster spot(s) for flexibility"
        else:
            return "Neutral roster impact - same number in/out"

    # Story 4.4 Trade Opportunity Methods
    async def identify_trade_opportunities(
        self,
        league_id: str,
        category: str = "all"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Identify trade opportunities (buy-low, sell-high, value arbitrage)

        @param league_id - Fantrax league ID
        @param category - Trade category (all, buy_low, sell_high, arbitrage)

        @returns Trade opportunity recommendations by category

        @performance
        - Response time: 2-3 seconds
        - Cached for 1 hour

        @since 4.4.0
        """
        # Check cache
        cache_key = f"trade_opportunities:{self.user_id}:{league_id}:{category}"
        cached = await cache_manager.get(cache_key)
        if cached:
            return json.loads(cached)

        # Get team analysis
        analysis = await self.roster_analysis.analyze_team(league_id)

        opportunities = {
            "buy_low_candidates": [],
            "sell_high_opportunities": [],
            "value_arbitrage": []
        }

        if category in ["all", "buy_low"]:
            opportunities["buy_low_candidates"] = await self._find_buy_low_candidates(analysis)

        if category in ["all", "sell_high"]:
            opportunities["sell_high_opportunities"] = await self._find_sell_high_opportunities(analysis)

        if category in ["all", "arbitrage"]:
            opportunities["value_arbitrage"] = await self._find_value_arbitrage(analysis)

        # Cache results
        await cache_manager.set(cache_key, json.dumps(opportunities), ttl=3600)

        return opportunities

    async def _find_buy_low_candidates(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find undervalued prospects (buy-low candidates)

        @param analysis - Team analysis with needs

        @returns List of buy-low prospect candidates

        @since 4.4.0
        """
        candidates = []
        weaknesses = analysis.get("weaknesses", [])
        timeline = analysis.get("timeline", "balanced")

        # Query prospects with recent performance dips or injury returns
        stmt = select(Prospect).where(
            Prospect.position.in_(weaknesses) if weaknesses else Prospect.id.isnot(None)
        ).limit(50)

        result = await self.db.execute(stmt)
        prospects = result.scalars().all()

        for prospect in prospects:
            # Detect buy-low signals
            buy_low_score = 0
            reasons = []

            # Recent injury (placeholder - would check injury history)
            if hasattr(prospect, 'injury_status') and prospect.injury_status == "recovering":
                buy_low_score += 30
                reasons.append("Returning from injury")

            # Performance dip (placeholder - would check recent stats trend)
            # For now, use a simple heuristic
            if prospect.overall_grade and prospect.overall_grade < 55:
                buy_low_score += 20
                reasons.append("Recent performance concerns")

            # Age-based value dip
            if prospect.age and prospect.age >= 24:
                buy_low_score += 15
                reasons.append("Age-related discount")

            # Timeline fit for team
            eta_range = self.TIMELINE_ETA_PREFERENCES.get(timeline, (2025, 2027))
            if prospect.eta_year and eta_range[0] <= prospect.eta_year <= eta_range[1]:
                buy_low_score += 20
                reasons.append("Timeline matches team window")

            # Position need match
            if prospect.position in weaknesses:
                buy_low_score += 25
                reasons.append(f"Fills {prospect.position} need")

            if buy_low_score >= 50:
                candidates.append({
                    "prospect_id": prospect.id,
                    "name": prospect.name,
                    "position": prospect.position,
                    "eta_year": prospect.eta_year,
                    "buy_low_score": buy_low_score,
                    "reasons": reasons,
                    "recommendation": "Strong buy-low target" if buy_low_score >= 70 else "Consider buying low"
                })

        # Sort by score
        candidates.sort(key=lambda x: x["buy_low_score"], reverse=True)

        return candidates[:10]

    async def _find_sell_high_opportunities(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find sell-high opportunities (overperforming prospects)

        @param analysis - Team analysis

        @returns List of sell-high candidates from roster

        @since 4.4.0
        """
        opportunities = []
        strengths = analysis.get("strengths", [])

        # Get roster to find owned prospects
        # This would integrate with Fantrax roster data
        # For now, return placeholder structure

        # Logic: Identify prospects on roster who are:
        # 1. Overperforming recent expectations
        # 2. At positions of team strength (surplus)
        # 3. Nearing peak trade value

        # Placeholder return
        return []

    async def _find_value_arbitrage(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find value arbitrage opportunities (team-specific context)

        @param analysis - Team analysis

        @returns List of arbitrage opportunities

        @since 4.4.0
        """
        arbitrage = []
        weaknesses = analysis.get("weaknesses", [])
        strengths = analysis.get("strengths", [])
        competitive_window = analysis.get("competitive_window", {})

        # Find prospects valued differently based on team context
        # Team A rebuilding: undervalues MLB-ready players
        # Team B contending: undervalues distant prospects

        stmt = select(Prospect).limit(30)
        result = await self.db.execute(stmt)
        prospects = result.scalars().all()

        for prospect in prospects:
            arbitrage_score = 0
            strategy = []

            # If team is contending and prospect is distant (undervalued by team)
            if competitive_window.get("window") == "contending":
                if prospect.eta_year and prospect.eta_year > datetime.now().year + 2:
                    arbitrage_score += 25
                    strategy.append("Team undervalues distant ETA - acquire cheap, trade to rebuilder")

            # If team is rebuilding and prospect is MLB-ready (undervalued by team)
            if competitive_window.get("window") == "rebuilding":
                if prospect.eta_year and prospect.eta_year <= datetime.now().year + 1:
                    arbitrage_score += 25
                    strategy.append("Team undervalues MLB-ready - acquire cheap, trade to contender")

            # Position arbitrage: team strength = lower value to team
            if prospect.position in strengths:
                arbitrage_score += 15
                strategy.append(f"Team has {prospect.position} depth - lower value, can trade for need")

            # Position arbitrage: team weakness = higher value to others who are strong there
            if prospect.position in weaknesses:
                arbitrage_score += 20
                strategy.append(f"High value to team, may overpay - shop around for better deal")

            if arbitrage_score >= 40:
                arbitrage.append({
                    "prospect_id": prospect.id,
                    "name": prospect.name,
                    "position": prospect.position,
                    "eta_year": prospect.eta_year,
                    "arbitrage_score": arbitrage_score,
                    "strategy": strategy,
                    "action": "Exploit value difference between teams"
                })

        arbitrage.sort(key=lambda x: x["arbitrage_score"], reverse=True)

        return arbitrage[:10]
