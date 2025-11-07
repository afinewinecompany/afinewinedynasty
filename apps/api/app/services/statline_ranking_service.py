"""
Statline Ranking Service

Provides in-season statistical rankings using composite scores from MILB data.
Focuses on discipline and power scores as primary ranking metrics.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func, and_
import numpy as np
import logging

logger = logging.getLogger(__name__)


class StatlineRankingService:
    """
    Service for calculating in-season prospect rankings based on composite scores.
    Uses simplified queries focusing on discipline and power metrics.
    """

    # Age adjustment factors (negative means younger is better)
    AGE_LEVEL_ADJUSTMENTS = {
        "AAA": {"avg_age": 24.5, "factor": -0.05},
        "AA": {"avg_age": 23.0, "factor": -0.08},
        "A+": {"avg_age": 21.5, "factor": -0.10},
        "A": {"avg_age": 20.5, "factor": -0.12},
        "ROK": {"avg_age": 18.5, "factor": -0.15}
    }

    def __init__(self, db: AsyncSession):
        """Initialize the ranking service."""
        self.db = db

    async def calculate_statline_rankings(
        self,
        level: Optional[str] = None,
        min_plate_appearances: int = 100,
        season: int = 2025,
        include_pitch_data: bool = True
    ) -> List[Dict]:
        """
        Calculate statline rankings using composite discipline and power scores.

        Args:
            level: Optional level filter (AAA, AA, A+, A, ROK)
            min_plate_appearances: Minimum PAs to qualify
            season: Season to analyze
            include_pitch_data: Whether to include pitch-level metrics

        Returns:
            List of ranked prospects with composite scores
        """
        logger.info(f"Calculating Statline rankings for {season} season using composite scores")

        # Primary approach: Get all players with 2025 MILB pitch data
        players_data = []
        if include_pitch_data:
            logger.info("Primary: Fetching all players with 2025 MILB pitch data")
            try:
                players_data = await self._get_all_players_with_pitch_data(
                    level, min_plate_appearances, season
                )
                logger.info(f"Found {len(players_data)} players with pitch data")
            except Exception as e:
                logger.error(f"Error fetching pitch data: {e}")

        # Fallback 1: Try enhanced composite scores query
        if not players_data:
            logger.info("Fallback 1: Trying enhanced composite scores query")
            try:
                players_data = await self._get_players_with_composite_scores(
                    level, min_plate_appearances, season
                )
                if players_data:
                    logger.info(f"Found {len(players_data)} players with composite scores")
            except Exception as e:
                logger.warning(f"Could not get composite scores: {e}")

        # Fallback 2: Try prospect_stats table
        if not players_data:
            logger.info("Fallback 2: Trying prospect_stats table")
            players_data = await self._get_players_from_prospect_stats(
                level, min_plate_appearances
            )
            if players_data:
                logger.info(f"Found {len(players_data)} players from prospect_stats")

        # Fallback 3: Emergency - get ANY prospects
        if not players_data:
            logger.warning("Fallback 3: Emergency - getting all prospects with default scores")
            players_data = await self._emergency_fallback_all_prospects()

        if not players_data:
            logger.error("All approaches failed - no players found")
            return []

        logger.info(f"Found {len(players_data)} qualified players")

        # Step 3: Calculate rankings based on composite scores
        for player in players_data:
            # Get all three component scores
            discipline = player.get('discipline_score', 50)
            power = player.get('power_score', 50)
            contact = player.get('contact_score', 50)

            # Calculate overall score with all three components
            # Discipline: 40%, Power: 35%, Contact: 25%
            player['overall_score'] = (discipline * 0.40) + (power * 0.35) + (contact * 0.25)

            # Add age adjustment
            age_adj = self._calculate_age_adjustment(player)
            player['age_adjustment'] = age_adj
            player['adjusted_score'] = player['overall_score'] * (1 + age_adj)

        # Step 4: Sort and rank
        players_data.sort(key=lambda x: x['adjusted_score'], reverse=True)

        for i, player in enumerate(players_data):
            player['rank'] = i + 1

            # Add letter grades for visual display
            player['discipline_grade'] = self._score_to_grade(player.get('discipline_score', 50))
            player['power_grade'] = self._score_to_grade(player.get('power_score', 50))
            player['contact_grade'] = self._score_to_grade(player.get('contact_score', 50))
            player['overall_grade'] = self._score_to_grade(player['overall_score'])

        return players_data

    async def _get_all_players_with_pitch_data(
        self,
        level: Optional[str],
        min_pa: int,
        season: int
    ) -> List[Dict]:
        """Get ALL players with 2025 MILB pitch data - maximally inclusive."""

        # Very inclusive query - get EVERYONE with pitch data
        base_query = """
        WITH player_pitch_stats AS (
            -- Get all players who have ANY pitch data in 2025
            SELECT
                bp.mlb_batter_id,
                bp.mlb_batter_id as name,  -- Use ID for now, will join with prospects table
                bp.level,
                COUNT(DISTINCT bp.game_pk) as games,
                COUNT(*) as total_pitches,

                -- Calculate plate appearances (unique game + at_bat combinations)
                COUNT(DISTINCT CASE
                    WHEN bp.is_final_pitch = true
                    THEN bp.game_pk || '_' || bp.at_bat_index
                END) as total_pa,

                -- Basic counting stats using pa_result descriptions
                SUM(CASE WHEN bp.is_final_pitch AND LOWER(bp.pa_result) LIKE '%single%' THEN 1 ELSE 0 END) as singles,
                SUM(CASE WHEN bp.is_final_pitch AND LOWER(bp.pa_result) LIKE '%double%' THEN 1 ELSE 0 END) as doubles,
                SUM(CASE WHEN bp.is_final_pitch AND LOWER(bp.pa_result) LIKE '%triple%' THEN 1 ELSE 0 END) as triples,
                SUM(CASE WHEN bp.is_final_pitch AND LOWER(bp.pa_result) LIKE '%home%run%' THEN 1 ELSE 0 END) as home_runs,
                SUM(CASE WHEN bp.is_final_pitch AND (LOWER(bp.pa_result) LIKE '%single%' OR LOWER(bp.pa_result) LIKE '%double%'
                    OR LOWER(bp.pa_result) LIKE '%triple%' OR LOWER(bp.pa_result) LIKE '%home%run%') THEN 1 ELSE 0 END) as hits,
                SUM(CASE WHEN bp.is_final_pitch AND LOWER(bp.pa_result) LIKE '%walk%' THEN 1 ELSE 0 END) as walks,
                SUM(CASE WHEN bp.is_final_pitch AND LOWER(bp.pa_result) LIKE '%strikeout%' THEN 1 ELSE 0 END) as strikeouts,

                -- Discipline metrics (pitch-level)
                AVG(CASE WHEN bp.zone <= 9 THEN 100.0 ELSE 0.0 END) as zone_rate,
                AVG(CASE WHEN bp.swing = true THEN 100.0 ELSE 0.0 END) as swing_rate,
                AVG(CASE WHEN bp.zone <= 9 AND bp.swing = true THEN 100.0
                        WHEN bp.zone <= 9 THEN 0.0
                        ELSE NULL END) as zone_swing_rate,
                AVG(CASE WHEN bp.zone > 9 AND bp.swing = true THEN 100.0
                        WHEN bp.zone > 9 THEN 0.0
                        ELSE NULL END) as chase_rate,

                -- Contact metrics
                AVG(CASE WHEN bp.swing = true AND bp.contact = true THEN 100.0
                        WHEN bp.swing = true THEN 0.0
                        ELSE NULL END) as contact_rate,
                AVG(CASE WHEN bp.swing = true AND bp.contact = false THEN 100.0
                        WHEN bp.swing = true THEN 0.0
                        ELSE NULL END) as whiff_rate,

                -- Power metrics (batted ball data)
                COUNT(*) FILTER (WHERE bp.hardness = 'hard' AND bp.contact = true AND bp.foul = false) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.hardness IS NOT NULL AND bp.contact = true AND bp.foul = false), 0) as hard_hit_rate,
                COUNT(*) FILTER (WHERE bp.trajectory = 'fly_ball' AND bp.contact = true AND bp.foul = false) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory IS NOT NULL AND bp.contact = true AND bp.foul = false), 0) as fly_ball_rate,
                COUNT(*) FILTER (WHERE bp.trajectory = 'line_drive' AND bp.contact = true AND bp.foul = false) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory IS NOT NULL AND bp.contact = true AND bp.foul = false), 0) as line_drive_rate,
                COUNT(*) FILTER (WHERE bp.trajectory = 'ground_ball' AND bp.contact = true AND bp.foul = false) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.trajectory IS NOT NULL AND bp.contact = true AND bp.foul = false), 0) as ground_ball_rate

            FROM milb_batter_pitches bp
            WHERE bp.season = :season
                {level_filter}
            GROUP BY bp.mlb_batter_id, bp.level
            -- Very lenient PA filter or none at all
            HAVING COUNT(DISTINCT CASE
                WHEN bp.is_final_pitch = true
                THEN bp.game_pk || '_' || bp.at_bat_index
            END) >= GREATEST(1, :min_pa / 2)  -- Cut min PA in half to be more inclusive
        )
        SELECT
            pps.mlb_batter_id,
            COALESCE(p.name, CAST(pps.mlb_batter_id AS VARCHAR)) as name,  -- Get real name from prospects
            pps.level,
            pps.games,
            pps.total_pitches,
            pps.total_pa,
            pps.hits,
            pps.singles,
            pps.doubles,
            pps.triples,
            pps.home_runs,
            pps.walks,
            pps.strikeouts,
            pps.zone_rate,
            pps.swing_rate,
            pps.zone_swing_rate,
            pps.chase_rate,
            pps.contact_rate,
            pps.whiff_rate,
            pps.hard_hit_rate,
            pps.fly_ball_rate,
            pps.line_drive_rate,
            pps.ground_ball_rate,
            p.id as prospect_id,
            COALESCE(p.age, 20) as age,
            COALESCE(p.position, 'UTIL') as position,
            p.organization,

            -- Traditional stats
            COALESCE(hits * 100.0 / NULLIF(total_pa - walks, 0), 0) as batting_avg,
            COALESCE(walks * 100.0 / NULLIF(total_pa, 0), 0) as walk_rate,
            COALESCE(strikeouts * 100.0 / NULLIF(total_pa, 0), 0) as strikeout_rate,
            COALESCE(home_runs * 100.0 / NULLIF(total_pa, 0), 0) as home_run_rate,

            -- Calculate DISCIPLINE SCORE (0-100) - focus on plate approach
            GREATEST(0, LEAST(100,
                COALESCE(contact_rate, 75) * 0.25 +                    -- 25% weight on contact ability
                (100 - COALESCE(chase_rate, 35)) * 0.25 +              -- 25% weight on not chasing
                COALESCE(zone_swing_rate, 65) * 0.15 +                 -- 15% weight on swinging at strikes
                (100 - COALESCE(whiff_rate, 25)) * 0.15 +              -- 15% weight on not whiffing
                COALESCE(walk_rate, 8) * 2.5 +                         -- 20% weight on walks (scaled)
                0
            )) as discipline_score,

            -- Calculate POWER SCORE (0-100) - focus on impact potential
            GREATEST(0, LEAST(100,
                COALESCE(hard_hit_rate, 30) * 1.0 +                    -- 30% weight on hard contact
                COALESCE(home_run_rate, 3) * 10.0 +                    -- 30% weight on HR rate (scaled)
                COALESCE(fly_ball_rate + line_drive_rate, 50) * 0.6 +  -- 30% weight on elevated balls
                CASE
                    WHEN doubles + triples + home_runs > 0
                    THEN (doubles + triples * 2 + home_runs * 3) * 100.0 / NULLIF(total_pa, 0) * 2.5
                    ELSE 0
                END +                                                    -- 10% weight on extra bases
                0
            )) as power_score,

            -- Calculate CONTACT SCORE (0-100) - focus on bat-to-ball skills
            GREATEST(0, LEAST(100,
                COALESCE(contact_rate, 75) * 0.40 +                    -- 40% weight on overall contact
                COALESCE(batting_avg, 25) * 2.0 +                      -- 50% weight on batting avg (scaled)
                (100 - COALESCE(strikeout_rate, 20)) * 0.10 +          -- 10% weight on avoiding Ks
                0
            )) as contact_score

        FROM player_pitch_stats pps
        LEFT JOIN prospects p ON CAST(p.mlb_player_id AS INTEGER) = pps.mlb_batter_id
        ORDER BY total_pa DESC
        """

        level_filter = f"AND bp.level = :level" if level else ""
        query = base_query.replace("{level_filter}", level_filter)

        params = {"season": season, "min_pa": min_pa}
        if level:
            params["level"] = level

        try:
            result = await self.db.execute(text(query), params)
            rows = result.fetchall()

            players = []
            for row in rows:
                player = dict(row._mapping)
                # Ensure all scores are present
                player['discipline_score'] = player.get('discipline_score', 50)
                player['power_score'] = player.get('power_score', 50)
                player['contact_score'] = player.get('contact_score', 50)
                players.append(player)

            return players

        except Exception as e:
            logger.error(f"Error in _get_all_players_with_pitch_data: {e}")
            return []

    async def _get_players_with_composite_scores(
        self,
        level: Optional[str],
        min_pa: int,
        season: int
    ) -> List[Dict]:
        """Get players with simplified composite scores from MILB pitch data."""

        # Simplified query focusing on key metrics for composite scores
        base_query = """
        WITH player_basics AS (
            -- First, get basic player info and check if they have enough PAs
            SELECT
                bp.mlb_batter_id,
                bp.mlb_batter_id as name,  -- Use ID for now, will join with prospects table
                bp.level,
                COUNT(DISTINCT bp.game_pk) as games,
                COUNT(*) as total_pitches,
                COUNT(DISTINCT CASE
                    WHEN bp.pa_result IS NOT NULL
                    THEN bp.game_id || '_' || bp.at_bat_index
                END) as total_pa,
                -- Basic counting stats
                SUM(CASE WHEN bp.pa_result IN ('single', 'double', 'triple', 'home_run') THEN 1 ELSE 0 END) as hits,
                SUM(CASE WHEN bp.pa_result = 'home_run' THEN 1 ELSE 0 END) as home_runs,
                SUM(CASE WHEN bp.pa_result = 'walk' THEN 1 ELSE 0 END) as walks,
                SUM(CASE WHEN bp.pa_result = 'strikeout' THEN 1 ELSE 0 END) as strikeouts
            FROM milb_batter_pitches bp
            WHERE bp.season = :season
                {level_filter}
            GROUP BY bp.mlb_batter_id, bp.level
            HAVING COUNT(DISTINCT CASE
                WHEN bp.pa_result IS NOT NULL
                THEN bp.game_id || '_' || bp.at_bat_index
            END) >= :min_pa
        ),
        player_metrics AS (
            -- Then calculate the metrics needed for composite scores
            SELECT
                pb.*,
                p.id as prospect_id,
                p.age,
                p.position,
                p.organization,

                -- Traditional stats
                CAST(pb.hits AS FLOAT) / NULLIF(pb.total_pa - pb.walks, 0) * 100 as batting_avg,
                CAST(pb.walks AS FLOAT) / NULLIF(pb.total_pa, 0) * 100 as walk_rate,
                CAST(pb.strikeouts AS FLOAT) / NULLIF(pb.total_pa, 0) * 100 as strikeout_rate,
                CAST(pb.home_runs AS FLOAT) / NULLIF(pb.total_pa, 0) * 100 as home_run_rate,

                -- Get pitch-level metrics for discipline score
                (SELECT
                    -- Contact rate (contact/swings)
                    AVG(CASE WHEN bp2.swing = true AND bp2.contact = true THEN 100.0
                            WHEN bp2.swing = true THEN 0.0
                            ELSE NULL END)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season) as contact_rate,

                (SELECT
                    -- Chase rate (swings outside zone)
                    AVG(CASE WHEN bp2.zone > 9 AND bp2.swing = true THEN 100.0
                            WHEN bp2.zone > 9 THEN 0.0
                            ELSE NULL END)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season) as chase_rate,

                -- Get batted ball metrics for power score
                (SELECT
                    COUNT(*) FILTER (WHERE bp2.hardness = 'hard') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp2.hardness IS NOT NULL), 0)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season
                    AND bp2.contact = true
                    AND bp2.foul = false) as hard_hit_rate,

                (SELECT
                    COUNT(*) FILTER (WHERE bp2.trajectory = 'fly_ball') * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp2.trajectory IS NOT NULL), 0)
                FROM milb_batter_pitches bp2
                WHERE bp2.mlb_batter_id = pb.mlb_batter_id
                    AND bp2.season = :season
                    AND bp2.contact = true
                    AND bp2.foul = false) as fly_ball_rate

            FROM player_basics pb
            LEFT JOIN prospects p ON CAST(p.mlb_player_id AS INTEGER) = pb.mlb_batter_id
        )
        SELECT
            *,
            -- Calculate DISCIPLINE SCORE (0-100)
            GREATEST(0, LEAST(100,
                COALESCE(contact_rate, 75) * 0.30 +           -- 30% weight on contact
                (100 - COALESCE(chase_rate, 35)) * 0.30 +     -- 30% weight on not chasing
                COALESCE(walk_rate, 8) * 3.0 +                -- 24% weight on walks (scaled)
                (100 - LEAST(strikeout_rate, 40)) * 0.16      -- 16% weight on avoiding Ks
            )) as discipline_score,

            -- Calculate POWER SCORE (0-100)
            GREATEST(0, LEAST(100,
                COALESCE(hard_hit_rate, 10) * 2.5 +           -- 25% weight (10% avg -> 25 pts)
                COALESCE(home_run_rate * 20, 0) +             -- 20% weight (5% HR rate -> 100 pts)
                COALESCE(fly_ball_rate, 30) * 1.5 +           -- 45% weight (30% avg -> 45 pts)
                CASE
                    WHEN batting_avg > 30 THEN 10
                    WHEN batting_avg > 25 THEN 5
                    ELSE 0
                END                                            -- 10% bonus for high avg
            )) as power_score

        FROM player_metrics
        ORDER BY total_pa DESC
        """

        level_filter = f"AND bp.level = :level" if level else ""
        query = base_query.replace("{level_filter}", level_filter)

        params = {"season": season, "min_pa": min_pa}
        if level:
            params["level"] = level

        try:
            result = await self.db.execute(text(query), params)
            rows = result.fetchall()

            players = []
            for row in rows:
                player = dict(row._mapping)
                players.append(player)

            return players

        except Exception as e:
            logger.error(f"Error querying MILB pitch data: {e}")
            return []

    async def _get_players_from_prospect_stats(
        self,
        level: Optional[str],
        min_pa: int
    ) -> List[Dict]:
        """Fallback to prospect_stats table with estimated composite scores."""

        # Make the query much simpler and less restrictive
        query = """
        SELECT DISTINCT ON (p.id)
            p.id as prospect_id,
            COALESCE(p.mlb_player_id, '') as mlb_batter_id,
            p.name,
            p.position,
            p.age,
            p.level,
            p.organization,
            COALESCE(ps.games_played, 0) as games,

            -- Calculate PAs (be very lenient)
            GREATEST(
                COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0),
                COALESCE(ps.at_bats, 0)
            ) as total_pa,

            -- Basic stats (handle nulls gracefully)
            COALESCE(ps.at_bats, 0) as at_bats,
            COALESCE(ps.hits, 0) as hits,
            COALESCE(ps.home_runs, 0) as home_runs,
            COALESCE(ps.walks, 0) as walks,
            COALESCE(ps.strikeouts, 0) as strikeouts,
            COALESCE(ps.batting_avg, 0) * 100 as batting_avg,
            COALESCE(ps.on_base_pct, 0) * 100 as on_base_pct,
            COALESCE(ps.slugging_pct, 0) * 100 as slugging_pct,

            -- Calculate rates (with safe division)
            CASE
                WHEN COALESCE(ps.at_bats, 0) > 0
                THEN CAST(COALESCE(ps.walks, 0) AS FLOAT) / (COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0)) * 100
                ELSE 0
            END as walk_rate,

            CASE
                WHEN COALESCE(ps.at_bats, 0) > 0
                THEN CAST(COALESCE(ps.strikeouts, 0) AS FLOAT) / COALESCE(ps.at_bats, 0) * 100
                ELSE 0
            END as strikeout_rate,

            CASE
                WHEN COALESCE(ps.at_bats, 0) > 0
                THEN CAST(COALESCE(ps.home_runs, 0) AS FLOAT) / COALESCE(ps.at_bats, 0) * 100
                ELSE 0
            END as home_run_rate,

            -- Simple DISCIPLINE SCORE (0-100)
            GREATEST(0, LEAST(100, 50 +
                CASE
                    WHEN COALESCE(ps.at_bats, 0) > 0
                    THEN (CAST(COALESCE(ps.walks, 0) AS FLOAT) / COALESCE(ps.at_bats, 0) * 100 - 10) * 2
                    ELSE 0
                END +
                CASE
                    WHEN COALESCE(ps.at_bats, 0) > 0
                    THEN (25 - CAST(COALESCE(ps.strikeouts, 0) AS FLOAT) / COALESCE(ps.at_bats, 0) * 100) * 1
                    ELSE 0
                END
            )) as discipline_score,

            -- Simple POWER SCORE (0-100)
            GREATEST(0, LEAST(100, 30 +
                CASE
                    WHEN COALESCE(ps.at_bats, 0) > 0
                    THEN CAST(COALESCE(ps.home_runs, 0) AS FLOAT) / COALESCE(ps.at_bats, 0) * 1000
                    ELSE 0
                END +
                (COALESCE(ps.slugging_pct, 0) - COALESCE(ps.batting_avg, 0)) * 200
            )) as power_score,

            -- Default pitch metrics
            75.0 as contact_rate,
            35.0 as chase_rate,
            10.0 as hard_hit_rate,
            30.0 as fly_ball_rate

        FROM prospects p
        LEFT JOIN prospect_stats ps ON p.id = ps.prospect_id
        WHERE 1=1
            {level_filter}
            {min_pa_filter}
        ORDER BY p.id, ps.date_recorded DESC NULLS LAST
        """

        # Only add filters if they make sense
        level_filter = f"AND p.level = :level" if level else ""

        # Make min PA filter very lenient
        min_pa_filter = f"AND GREATEST(COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0), COALESCE(ps.at_bats, 0)) >= :min_pa" if min_pa > 0 else ""

        query = query.replace("{level_filter}", level_filter)
        query = query.replace("{min_pa_filter}", min_pa_filter)

        params = {"min_pa": min_pa}
        if level:
            params["level"] = level

        try:
            logger.info(f"Executing prospect_stats query with params: {params}")
            result = await self.db.execute(text(query), params)
            rows = result.fetchall()

            players = []
            for row in rows:
                player = dict(row._mapping)
                # Ensure all required fields have valid values
                player['discipline_score'] = player.get('discipline_score', 50)
                player['power_score'] = player.get('power_score', 50)
                player['total_pa'] = player.get('total_pa', 0)
                player['name'] = player.get('name', 'Unknown')
                player['level'] = player.get('level', 'N/A')
                players.append(player)

            logger.info(f"Found {len(players)} players from prospect_stats")
            return players
        except Exception as e:
            logger.error(f"Error querying prospect_stats: {e}")
            # Return empty list but don't crash
            return []

    async def _emergency_fallback_all_prospects(self) -> List[Dict]:
        """Emergency fallback - just return all prospects with default scores."""
        query = """
        SELECT
            p.id as prospect_id,
            COALESCE(p.mlb_player_id, '') as mlb_batter_id,
            p.name,
            p.position,
            COALESCE(p.age, 20) as age,
            COALESCE(p.level, 'A') as level,
            p.organization,
            100 as games,
            100 as total_pa,
            25.0 as batting_avg,
            32.0 as on_base_pct,
            40.0 as slugging_pct,
            10.0 as walk_rate,
            20.0 as strikeout_rate,
            3.0 as home_run_rate,
            50.0 as discipline_score,
            50.0 as power_score,
            75.0 as contact_rate,
            35.0 as chase_rate,
            10.0 as hard_hit_rate,
            30.0 as fly_ball_rate
        FROM prospects p
        ORDER BY p.name
        LIMIT 100
        """

        try:
            logger.info("Executing emergency fallback query")
            result = await self.db.execute(text(query))
            rows = result.fetchall()

            players = []
            for row in rows:
                player = dict(row._mapping)
                players.append(player)

            logger.info(f"Emergency fallback found {len(players)} prospects")
            return players
        except Exception as e:
            logger.error(f"Emergency fallback failed: {e}")
            return []

    def _calculate_age_adjustment(self, player: Dict) -> float:
        """Calculate age-based adjustment factor."""

        age = player.get('age', 0)
        level = player.get('level')

        if not age or not level or level not in self.AGE_LEVEL_ADJUSTMENTS:
            return 0

        level_data = self.AGE_LEVEL_ADJUSTMENTS[level]
        avg_age = level_data["avg_age"]
        factor = level_data["factor"]

        # Calculate age difference from level average
        age_diff = age - avg_age

        # Apply adjustment (negative diff = younger = bonus)
        adjustment = age_diff * factor

        return adjustment

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""

        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "A-"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "B-"
        elif score >= 65:
            return "C+"
        elif score >= 60:
            return "C"
        elif score >= 55:
            return "C-"
        elif score >= 50:
            return "D+"
        elif score >= 45:
            return "D"
        else:
            return "D-"