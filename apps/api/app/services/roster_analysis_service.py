"""
Roster Analysis Service

Analyzes team rosters to identify strengths, weaknesses, and future needs
for optimal prospect targeting and team building strategies.
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Prospect, ProspectStats
from app.services.fantrax_api_service import FantraxAPIService
from app.core.cache_manager import CacheManager
import json
import logging
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)

# Initialize cache manager
cache_manager = CacheManager()


class RosterAnalysisService:
    """
    Service for analyzing team rosters and identifying needs

    Provides comprehensive analysis of roster composition, age curves,
    positional depth, and future roster holes.
    """

    # Position groups for analysis
    POSITION_GROUPS = {
        "infield": ["1B", "2B", "3B", "SS"],
        "outfield": ["LF", "CF", "RF"],
        "catching": ["C"],
        "pitching": ["SP", "RP"],
        "utility": ["DH"]
    }

    # Age thresholds for timeline analysis
    AGE_PRIME = (25, 32)  # Prime years
    AGE_YOUNG = 25        # Under this is young
    AGE_OLD = 32          # Over this is aging
    AGE_PROSPECT = 23     # Prospect age threshold

    # Quality tier thresholds (based on normalized performance scores)
    QUALITY_TIERS = {
        "elite": 8.5,           # Top-tier talent
        "above_average": 7.0,   # Strong contributors
        "average": 5.5,         # League-average players
        "below_average": 4.0,   # Replacement level
        "weak": 0               # Below replacement
    }

    # Minimum players per position for depth
    MIN_DEPTH = {
        "C": 2,
        "1B": 1,
        "2B": 1,
        "3B": 1,
        "SS": 1,
        "LF": 1,
        "CF": 1,
        "RF": 1,
        "DH": 1,
        "SP": 5,
        "RP": 3
    }

    def __init__(self, db: AsyncSession, user_id: int):
        """
        Initialize Roster Analysis Service

        @param db - Database session for prospect data
        @param user_id - User ID for roster access

        @since 1.0.0
        """
        self.db = db
        self.user_id = user_id
        self.fantrax_api = FantraxAPIService(db, user_id)

    async def analyze_team(self, league_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive team analysis

        @param league_id - Fantrax league ID

        @returns Complete team analysis with strengths, weaknesses, and recommendations

        @performance
        - Response time: 500-1000ms
        - Multiple calculations and database queries
        - Cached for 1 hour

        @since 1.0.0
        """
        # Check cache first
        cache_key = f"roster_analysis:{self.user_id}:{league_id}"
        cached_analysis = await cache_manager.get(cache_key)
        if cached_analysis:
            return json.loads(cached_analysis)

        # Get roster data
        roster_data = await self.fantrax_api.get_roster(league_id)
        if not roster_data:
            # If no cached roster, try to sync
            sync_result = await self.fantrax_api.sync_roster(league_id)
            if sync_result["success"]:
                roster_data = await self.fantrax_api.get_roster(league_id)

        if not roster_data:
            logger.error(f"Unable to get roster for league {league_id}")
            return self._empty_analysis()

        # Get league settings for context
        league_settings = await self.fantrax_api.get_league_settings(league_id)

        # Perform various analyses
        position_analysis = self._analyze_positions(roster_data["players"])
        age_analysis = self._analyze_age_curve(roster_data["players"])
        depth_analysis = self._analyze_depth(roster_data["players"], league_settings)
        timeline_analysis = self._determine_team_timeline(age_analysis, depth_analysis)
        future_holes = await self._project_future_holes(roster_data["players"], league_settings)
        available_spots = self._calculate_available_spots(roster_data["players"], league_settings)

        # Enhanced analyses for Story 4.4
        gap_scoring = self._analyze_positional_gaps(position_analysis, depth_analysis)
        age_distribution = self._analyze_age_distribution_timeline(roster_data["players"])
        quality_tiers = self._analyze_quality_tiers(roster_data["players"])
        future_needs_projection = await self._project_future_needs(roster_data["players"], league_settings)
        competitive_window = self._detect_competitive_window(age_analysis, quality_tiers, depth_analysis)

        # Compile complete analysis
        analysis = {
            "league_id": league_id,
            "strengths": self._identify_strengths(position_analysis, depth_analysis),
            "weaknesses": self._identify_weaknesses(position_analysis, depth_analysis),
            "future_holes": future_holes,
            "timeline": timeline_analysis,
            "available_spots": available_spots,
            "position_depth": position_analysis,
            "age_analysis": age_analysis,
            "recommendations_count": await self._count_relevant_prospects(
                self._identify_weaknesses(position_analysis, depth_analysis),
                future_holes,
                timeline_analysis
            ),
            # Enhanced Story 4.4 fields
            "positional_gap_scores": gap_scoring,
            "age_distribution_timeline": age_distribution,
            "quality_tiers": quality_tiers,
            "future_needs": future_needs_projection,
            "competitive_window": competitive_window,
            "analysis_timestamp": datetime.utcnow().isoformat()
        }

        # Cache the analysis
        await cache_manager.set(
            cache_key,
            json.dumps(analysis),
            ttl=3600  # 1 hour cache
        )

        return analysis

    def _analyze_positions(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze positional distribution and quality

        @param players - List of roster players

        @returns Position analysis with counts and quality scores

        @since 1.0.0
        """
        position_data = defaultdict(list)

        for player in players:
            positions = player.get("positions", [])
            age = player.get("age", 0)

            # Track player at each eligible position
            for position in positions:
                position_data[position].append({
                    "name": player["name"],
                    "age": age,
                    "team": player.get("team", "FA"),
                    "contract_years": player.get("contract_years"),
                    "status": player.get("status", "active")
                })

        # Analyze each position
        analysis = {}
        for position, players_at_pos in position_data.items():
            active_players = [p for p in players_at_pos if p["status"] == "active"]

            analysis[position] = {
                "count": len(players_at_pos),
                "active_count": len(active_players),
                "avg_age": statistics.mean([p["age"] for p in players_at_pos if p["age"]]) if players_at_pos else 0,
                "players": players_at_pos,
                "depth_rating": self._rate_position_depth(position, len(active_players))
            }

        return analysis

    def _analyze_age_curve(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze team age distribution

        @param players - List of roster players

        @returns Age curve analysis with timeline indicators

        @since 1.0.0
        """
        ages = [p.get("age", 0) for p in players if p.get("age")]

        if not ages:
            return {
                "avg_age": 0,
                "median_age": 0,
                "young_players": 0,
                "prime_players": 0,
                "aging_players": 0,
                "age_distribution": {}
            }

        # Calculate age statistics
        age_distribution = defaultdict(int)
        young_count = 0
        prime_count = 0
        aging_count = 0

        for age in ages:
            age_distribution[age] += 1

            if age < self.AGE_YOUNG:
                young_count += 1
            elif self.AGE_PRIME[0] <= age <= self.AGE_PRIME[1]:
                prime_count += 1
            else:
                aging_count += 1

        return {
            "avg_age": statistics.mean(ages),
            "median_age": statistics.median(ages),
            "young_players": young_count,
            "prime_players": prime_count,
            "aging_players": aging_count,
            "age_distribution": dict(age_distribution),
            "age_score": self._calculate_age_score(young_count, prime_count, aging_count)
        }

    def _analyze_depth(
        self,
        players: List[Dict[str, Any]],
        league_settings: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze roster depth at each position

        @param players - List of roster players
        @param league_settings - League configuration

        @returns Depth analysis with ratings

        @since 1.0.0
        """
        position_counts = defaultdict(int)

        for player in players:
            if player.get("status") == "active":
                for position in player.get("positions", []):
                    position_counts[position] += 1

        depth_analysis = {}
        for position, min_required in self.MIN_DEPTH.items():
            current_count = position_counts.get(position, 0)
            depth_analysis[position] = {
                "current": current_count,
                "required": min_required,
                "surplus": current_count - min_required,
                "rating": self._rate_depth(current_count, min_required)
            }

        return depth_analysis

    def _determine_team_timeline(
        self,
        age_analysis: Dict[str, Any],
        depth_analysis: Dict[str, Any]
    ) -> str:
        """
        Determine team's competitive timeline

        @param age_analysis - Age distribution analysis
        @param depth_analysis - Positional depth analysis

        @returns Timeline classification (rebuilding, competing, etc.)

        @since 1.0.0
        """
        age_score = age_analysis.get("age_score", 0)
        avg_age = age_analysis.get("avg_age", 0)

        # Count positions with adequate depth
        strong_positions = sum(
            1 for pos_data in depth_analysis.values()
            if pos_data["rating"] >= "adequate"
        )

        total_positions = len(depth_analysis)
        depth_percentage = strong_positions / total_positions if total_positions > 0 else 0

        # Determine timeline based on age and depth
        if avg_age < 27 and depth_percentage < 0.5:
            return "rebuilding"
        elif avg_age < 27 and depth_percentage >= 0.5:
            return "emerging"
        elif 27 <= avg_age <= 30 and depth_percentage >= 0.6:
            return "competing"
        elif avg_age > 30 and depth_percentage >= 0.6:
            return "win-now"
        elif avg_age > 30 and depth_percentage < 0.6:
            return "retooling"
        else:
            return "balanced"

    async def _project_future_holes(
        self,
        players: List[Dict[str, Any]],
        league_settings: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Project future roster holes based on contracts and age

        @param players - List of roster players
        @param league_settings - League configuration

        @returns List of projected future needs

        @since 1.0.0
        """
        future_holes = []
        current_year = datetime.now().year

        # Analyze each position for future needs
        position_futures = defaultdict(lambda: defaultdict(list))

        for player in players:
            age = player.get("age", 0)
            contract_years = player.get("contract_years", 1)
            positions = player.get("positions", [])

            for position in positions:
                # Project when player will leave/decline
                if contract_years:
                    departure_year = current_year + contract_years
                    position_futures[position][departure_year].append(player["name"])

                # Consider age-related decline
                if age > 0:
                    decline_year = current_year + max(0, self.AGE_OLD - age)
                    if decline_year <= current_year + 3:  # Look 3 years ahead
                        position_futures[position][decline_year].append(f"{player['name']} (age)")

        # Identify holes
        for position in self.MIN_DEPTH.keys():
            for year in range(current_year + 1, current_year + 4):  # 3-year projection
                departures = position_futures[position].get(year, [])
                if departures:
                    severity = self._assess_hole_severity(position, len(departures))
                    future_holes.append({
                        "position": position,
                        "year": year,
                        "severity": severity,
                        "reason": f"{len(departures)} player(s) leaving/declining",
                        "affected_players": departures[:3]  # Limit to top 3
                    })

        # Sort by year and severity
        future_holes.sort(key=lambda x: (x["year"], x["severity"] == "high"))

        return future_holes[:10]  # Return top 10 most urgent holes

    def _calculate_available_spots(
        self,
        players: List[Dict[str, Any]],
        league_settings: Optional[Dict[str, Any]]
    ) -> int:
        """
        Calculate available roster spots for prospects

        @param players - Current roster
        @param league_settings - League configuration

        @returns Number of available spots

        @since 1.0.0
        """
        if not league_settings:
            # Default assumption
            max_roster = 40
        else:
            max_roster = league_settings.get("roster_size", 40)

        current_roster_size = len(players)
        minor_league_spots = 0

        if league_settings:
            minor_league_spots = league_settings.get("minor_league_slots", 0)

        # Calculate spots available for adding prospects
        standard_spots = max(0, max_roster - current_roster_size)

        # Count minor league eligible players not in minor league spots
        ml_eligible = sum(1 for p in players if p.get("minor_league_eligible", False))

        return standard_spots + minor_league_spots

    def _identify_strengths(
        self,
        position_analysis: Dict[str, Any],
        depth_analysis: Dict[str, Any]
    ) -> List[str]:
        """
        Identify team strength positions

        @param position_analysis - Position distribution data
        @param depth_analysis - Depth ratings

        @returns List of strong positions

        @since 1.0.0
        """
        strengths = []

        for position, data in depth_analysis.items():
            if data["surplus"] > 0 and data["rating"] in ["good", "excellent"]:
                strengths.append(position)

        return strengths

    def _identify_weaknesses(
        self,
        position_analysis: Dict[str, Any],
        depth_analysis: Dict[str, Any]
    ) -> List[str]:
        """
        Identify team weakness positions

        @param position_analysis - Position distribution data
        @param depth_analysis - Depth ratings

        @returns List of weak positions

        @since 1.0.0
        """
        weaknesses = []

        for position, data in depth_analysis.items():
            if data["surplus"] < 0 or data["rating"] in ["poor", "critical"]:
                weaknesses.append(position)

        return weaknesses

    async def _count_relevant_prospects(
        self,
        weaknesses: List[str],
        future_holes: List[Dict[str, Any]],
        timeline: str
    ) -> int:
        """
        Count prospects that match team needs

        @param weaknesses - Current weak positions
        @param future_holes - Projected future needs
        @param timeline - Team competitive timeline

        @returns Estimated count of relevant prospects

        @since 1.0.0
        """
        # Get target positions
        target_positions = set(weaknesses)
        for hole in future_holes:
            target_positions.add(hole["position"])

        # Query database for matching prospects
        stmt = select(Prospect).where(
            Prospect.position.in_(list(target_positions))
        )

        # Adjust ETA based on timeline
        if timeline in ["competing", "win-now"]:
            # Focus on near-ready prospects
            stmt = stmt.where(Prospect.eta_year <= datetime.now().year + 2)
        elif timeline == "rebuilding":
            # Open to all prospects
            pass
        else:
            # Balanced approach
            stmt = stmt.where(Prospect.eta_year <= datetime.now().year + 3)

        result = await self.db.execute(stmt)
        prospects = result.scalars().all()

        return len(prospects)

    def _rate_position_depth(self, position: str, count: int) -> str:
        """
        Rate depth at a specific position

        @param position - Position to rate
        @param count - Number of players

        @returns Depth rating (excellent, good, adequate, poor, critical)

        @since 1.0.0
        """
        min_required = self.MIN_DEPTH.get(position, 1)

        if count >= min_required * 2:
            return "excellent"
        elif count > min_required:
            return "good"
        elif count == min_required:
            return "adequate"
        elif count == min_required - 1:
            return "poor"
        else:
            return "critical"

    def _rate_depth(self, current: int, required: int) -> str:
        """
        Rate overall depth

        @param current - Current player count
        @param required - Required player count

        @returns Depth rating

        @since 1.0.0
        """
        ratio = current / required if required > 0 else 0

        if ratio >= 2:
            return "excellent"
        elif ratio >= 1.5:
            return "good"
        elif ratio >= 1:
            return "adequate"
        elif ratio >= 0.5:
            return "poor"
        else:
            return "critical"

    def _calculate_age_score(self, young: int, prime: int, aging: int) -> float:
        """
        Calculate team age score

        @param young - Count of young players
        @param prime - Count of prime age players
        @param aging - Count of aging players

        @returns Age score (0-100)

        @since 1.0.0
        """
        total = young + prime + aging
        if total == 0:
            return 0

        # Weight: Young = 0.3, Prime = 0.5, Aging = 0.2
        score = ((young * 0.3) + (prime * 0.5) + (aging * 0.2)) / total * 100
        return min(100, max(0, score))

    def _assess_hole_severity(self, position: str, departures: int) -> str:
        """
        Assess severity of future roster hole

        @param position - Position with hole
        @param departures - Number of departures

        @returns Severity level (high, medium, low)

        @since 1.0.0
        """
        min_required = self.MIN_DEPTH.get(position, 1)

        if departures >= min_required:
            return "high"
        elif departures >= min_required * 0.5:
            return "medium"
        else:
            return "low"

    def _analyze_positional_gaps(
        self,
        position_analysis: Dict[str, Any],
        depth_analysis: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze detailed positional gap scoring for enhanced needs assessment

        @param position_analysis - Position distribution data
        @param depth_analysis - Depth ratings

        @returns Gap scores by position with severity and urgency metrics

        @since 4.4.0
        """
        gap_scores = {}

        for position in self.MIN_DEPTH.keys():
            pos_data = position_analysis.get(position, {})
            depth_data = depth_analysis.get(position, {})

            # Calculate gap severity (0-10 scale)
            current = depth_data.get("current", 0)
            required = depth_data.get("required", 1)
            surplus = depth_data.get("surplus", 0)

            # Gap score: higher = more urgent need
            if surplus >= 0:
                gap_score = 0  # No gap
            else:
                gap_score = min(10, abs(surplus) * 3)  # Scale up the gap

            # Add age context to gap score
            avg_age = pos_data.get("avg_age", 0)
            if avg_age > self.AGE_OLD:
                gap_score = min(10, gap_score + 2)  # Aging position increases urgency

            gap_scores[position] = {
                "gap_score": gap_score,
                "severity": "high" if gap_score >= 7 else "medium" if gap_score >= 4 else "low",
                "current_count": current,
                "required_count": required,
                "deficit": abs(surplus) if surplus < 0 else 0,
                "avg_age": avg_age,
                "urgency": "immediate" if gap_score >= 8 else "near_term" if gap_score >= 5 else "long_term"
            }

        return gap_scores

    def _analyze_age_distribution_timeline(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze age distribution with enhanced timeline context

        @param players - List of roster players

        @returns Age distribution with timeline projections

        @since 4.4.0
        """
        ages = [p.get("age", 0) for p in players if p.get("age")]

        if not ages:
            return {
                "current_distribution": {},
                "projected_2_year": {},
                "projected_3_year": {},
                "aging_risk": "unknown"
            }

        # Current age buckets
        age_buckets = {
            "under_23": sum(1 for a in ages if a < 23),
            "23_25": sum(1 for a in ages if 23 <= a < 25),
            "25_28": sum(1 for a in ages if 25 <= a < 28),
            "28_32": sum(1 for a in ages if 28 <= a < 32),
            "32_35": sum(1 for a in ages if 32 <= a < 35),
            "over_35": sum(1 for a in ages if a >= 35)
        }

        # Project 2 years ahead
        future_2yr = [a + 2 for a in ages]
        projected_2yr = {
            "under_23": sum(1 for a in future_2yr if a < 23),
            "23_25": sum(1 for a in future_2yr if 23 <= a < 25),
            "25_28": sum(1 for a in future_2yr if 25 <= a < 28),
            "28_32": sum(1 for a in future_2yr if 28 <= a < 32),
            "32_35": sum(1 for a in future_2yr if 32 <= a < 35),
            "over_35": sum(1 for a in future_2yr if a >= 35)
        }

        # Project 3 years ahead
        future_3yr = [a + 3 for a in ages]
        projected_3yr = {
            "under_23": sum(1 for a in future_3yr if a < 23),
            "23_25": sum(1 for a in future_3yr if 23 <= a < 25),
            "25_28": sum(1 for a in future_3yr if 25 <= a < 28),
            "28_32": sum(1 for a in future_3yr if 28 <= a < 32),
            "32_35": sum(1 for a in future_3yr if 32 <= a < 35),
            "over_35": sum(1 for a in future_3yr if a >= 35)
        }

        # Calculate aging risk
        total = len(ages)
        aging_count = sum(1 for a in ages if a >= 30)
        aging_percentage = (aging_count / total * 100) if total > 0 else 0

        if aging_percentage > 50:
            aging_risk = "high"
        elif aging_percentage > 30:
            aging_risk = "medium"
        else:
            aging_risk = "low"

        return {
            "current_distribution": age_buckets,
            "projected_2_year": projected_2yr,
            "projected_3_year": projected_3yr,
            "aging_risk": aging_risk,
            "avg_age": statistics.mean(ages),
            "median_age": statistics.median(ages)
        }

    def _analyze_quality_tiers(self, players: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze roster quality by tier (elite, above-average, average, below-average, weak)

        @param players - List of roster players

        @returns Quality tier breakdown with counts and percentages

        @since 4.4.0
        """
        # Estimate quality score based on available data
        # In a real scenario, this would use performance metrics or ML predictions
        tier_counts = {
            "elite": 0,
            "above_average": 0,
            "average": 0,
            "below_average": 0,
            "weak": 0
        }

        tier_players = {
            "elite": [],
            "above_average": [],
            "average": [],
            "below_average": [],
            "weak": []
        }

        for player in players:
            # Placeholder quality scoring (would integrate with actual stats/ML predictions)
            # For now, use age as proxy: prime age = higher quality assumption
            age = player.get("age", 0)
            name = player.get("name", "Unknown")

            if self.AGE_PRIME[0] <= age <= self.AGE_PRIME[1]:
                # Prime age players assumed higher quality
                quality_score = 7.0 + (age % 3)  # Simulate variation
            elif age < self.AGE_PRIME[0]:
                # Young players - potential but unproven
                quality_score = 5.5 + (age % 2)
            else:
                # Aging players - declining
                quality_score = 6.0 - ((age - self.AGE_OLD) * 0.5)

            # Categorize into tiers
            if quality_score >= self.QUALITY_TIERS["elite"]:
                tier_counts["elite"] += 1
                tier_players["elite"].append(name)
            elif quality_score >= self.QUALITY_TIERS["above_average"]:
                tier_counts["above_average"] += 1
                tier_players["above_average"].append(name)
            elif quality_score >= self.QUALITY_TIERS["average"]:
                tier_counts["average"] += 1
                tier_players["average"].append(name)
            elif quality_score >= self.QUALITY_TIERS["below_average"]:
                tier_counts["below_average"] += 1
                tier_players["below_average"].append(name)
            else:
                tier_counts["weak"] += 1
                tier_players["weak"].append(name)

        total = len(players)
        return {
            "counts": tier_counts,
            "percentages": {
                tier: (count / total * 100) if total > 0 else 0
                for tier, count in tier_counts.items()
            },
            "players_by_tier": tier_players,
            "elite_count": tier_counts["elite"],
            "top_tier_percentage": (
                (tier_counts["elite"] + tier_counts["above_average"]) / total * 100
            ) if total > 0 else 0
        }

    async def _project_future_needs(
        self,
        players: List[Dict[str, Any]],
        league_settings: Optional[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Project future needs with 2-year and 3-year outlook

        @param players - List of roster players
        @param league_settings - League configuration

        @returns Future needs projections by timeline

        @since 4.4.0
        """
        current_year = datetime.now().year
        needs_2yr = []
        needs_3yr = []

        # Analyze each position for future needs
        position_futures = defaultdict(lambda: defaultdict(list))

        for player in players:
            age = player.get("age", 0)
            contract_years = player.get("contract_years", 1)
            positions = player.get("positions", [])

            for position in positions:
                # Project contract expiration
                if contract_years:
                    expiry_year = current_year + contract_years
                    position_futures[position][expiry_year].append({
                        "player": player["name"],
                        "reason": "contract_expiry"
                    })

                # Project age-based decline
                if age > 0:
                    years_to_decline = max(0, self.AGE_OLD - age)
                    decline_year = current_year + years_to_decline
                    if years_to_decline <= 3:
                        position_futures[position][decline_year].append({
                            "player": player["name"],
                            "reason": "age_decline"
                        })

        # Categorize needs by timeline
        for position in self.MIN_DEPTH.keys():
            # 2-year outlook
            departures_2yr = []
            for year in range(current_year + 1, current_year + 3):
                departures_2yr.extend(position_futures[position].get(year, []))

            if departures_2yr:
                severity = self._assess_hole_severity(position, len(departures_2yr))
                needs_2yr.append({
                    "position": position,
                    "timeline": "2_year",
                    "severity": severity,
                    "projected_departures": len(departures_2yr),
                    "affected_players": [d["player"] for d in departures_2yr[:3]]
                })

            # 3-year outlook
            departures_3yr = []
            for year in range(current_year + 1, current_year + 4):
                departures_3yr.extend(position_futures[position].get(year, []))

            if departures_3yr:
                severity = self._assess_hole_severity(position, len(departures_3yr))
                needs_3yr.append({
                    "position": position,
                    "timeline": "3_year",
                    "severity": severity,
                    "projected_departures": len(departures_3yr),
                    "affected_players": [d["player"] for d in departures_3yr[:3]]
                })

        return {
            "2_year_outlook": sorted(needs_2yr, key=lambda x: x["severity"] == "high", reverse=True),
            "3_year_outlook": sorted(needs_3yr, key=lambda x: x["severity"] == "high", reverse=True)
        }

    def _detect_competitive_window(
        self,
        age_analysis: Dict[str, Any],
        quality_tiers: Dict[str, Any],
        depth_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect competitive window (contending, transitional, rebuilding)

        @param age_analysis - Age distribution analysis
        @param quality_tiers - Quality tier breakdown
        @param depth_analysis - Positional depth analysis

        @returns Competitive window classification with reasoning

        @since 4.4.0
        """
        avg_age = age_analysis.get("avg_age", 0)
        elite_count = quality_tiers.get("elite_count", 0)
        top_tier_pct = quality_tiers.get("top_tier_percentage", 0)

        # Count strong positions
        strong_positions = sum(
            1 for pos_data in depth_analysis.values()
            if pos_data["rating"] in ["good", "excellent"]
        )
        total_positions = len(depth_analysis)
        depth_strength_pct = (strong_positions / total_positions * 100) if total_positions > 0 else 0

        # Competitive window logic
        window = "transitional"  # Default
        reasoning = []

        # Contending window indicators
        if avg_age >= 27 and avg_age <= 31 and elite_count >= 3 and depth_strength_pct >= 60:
            window = "contending"
            reasoning.append(f"Prime age core ({avg_age:.1f} avg age)")
            reasoning.append(f"{elite_count} elite players")
            reasoning.append(f"{depth_strength_pct:.0f}% positions at good+ depth")
        # Rebuilding window indicators
        elif avg_age < 26 and top_tier_pct < 30:
            window = "rebuilding"
            reasoning.append(f"Young roster ({avg_age:.1f} avg age)")
            reasoning.append(f"Limited top-tier talent ({top_tier_pct:.0f}%)")
        # Transitional indicators
        elif avg_age > 31 and depth_strength_pct < 50:
            window = "retooling"
            reasoning.append(f"Aging roster ({avg_age:.1f} avg age)")
            reasoning.append(f"Depth concerns ({depth_strength_pct:.0f}% strong positions)")
        else:
            reasoning.append(f"Mixed roster profile (age {avg_age:.1f})")
            reasoning.append(f"{top_tier_pct:.0f}% top-tier talent")

        return {
            "window": window,
            "confidence": "high" if len(reasoning) >= 2 else "medium",
            "reasoning": reasoning,
            "indicators": {
                "avg_age": avg_age,
                "elite_players": elite_count,
                "top_tier_percentage": top_tier_pct,
                "depth_strength_percentage": depth_strength_pct
            },
            "recommendation": self._get_window_recommendation(window)
        }

    def _get_window_recommendation(self, window: str) -> str:
        """
        Get strategic recommendation based on competitive window

        @param window - Competitive window classification

        @returns Strategic recommendation text

        @since 4.4.0
        """
        recommendations = {
            "contending": "Target MLB-ready prospects (ETA < 1 year) to fill immediate needs. Prioritize win-now moves.",
            "rebuilding": "Focus on high-upside prospects (2-4 year ETA). Build for future competitive window.",
            "transitional": "Balance approach: mix of near-ready (1-2 year ETA) and developmental prospects.",
            "retooling": "Reload with young talent. Target prospects with 1-3 year ETA to refresh aging roster."
        }
        return recommendations.get(window, "Evaluate roster needs and target prospects accordingly.")

    def _empty_analysis(self) -> Dict[str, Any]:
        """
        Return empty analysis structure

        @returns Empty analysis dictionary

        @since 1.0.0
        """
        return {
            "league_id": "",
            "strengths": [],
            "weaknesses": [],
            "future_holes": [],
            "timeline": "unknown",
            "available_spots": 0,
            "position_depth": {},
            "age_analysis": {},
            "recommendations_count": 0,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "error": "Unable to retrieve roster data"
        }