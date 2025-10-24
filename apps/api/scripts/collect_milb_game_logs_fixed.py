#!/usr/bin/env python3
"""
MiLB Game Log Data Collection - FIXED VERSION
==============================================
Collects game-by-game Minor League statistics for prospects.

KEY FIX: Queries each sport level separately using sportId parameter

This script:
1. Identifies prospects with MLB player IDs
2. Fetches Minor League game logs from MLB Stats API for each sport level
3. Stores game-by-game MiLB stats in milb_game_logs table

Usage:
    python collect_milb_game_logs_fixed.py --seasons 2025
    python collect_milb_game_logs_fixed.py --seasons 2025 --player-id 805811
"""

import sys
import os
import argparse
import asyncio
import aiohttp
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Sport ID to Level mapping
SPORT_LEVELS = {
    11: 'AAA',
    12: 'AA',
    13: 'A+',
    14: 'A',
    16: 'FRk',  # Foreign Rookie (note: may need database constraint update)
}


class MiLBGameLogCollectorFixed:
    """Collects Minor League game log data for prospects from MLB Stats API."""

    def __init__(self, seasons: List[int]):
        self.seasons = seasons
        self.stats_collected = 0
        self.errors = 0
        self.api_calls = 0

    async def collect_all_game_logs(self, player_id: Optional[int] = None):
        """
        Collect MiLB game logs for all prospects with MLB IDs.

        Args:
            player_id: Optional specific player ID to collect for
        """
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        try:
            # Get prospects with MLB IDs
            if player_id:
                cursor.execute("""
                    SELECT id, mlb_player_id, name, position
                    FROM prospects
                    WHERE mlb_player_id = %s
                """, (str(player_id),))
            else:
                cursor.execute("""
                    SELECT id, mlb_player_id, name, position
                    FROM prospects
                    WHERE mlb_player_id IS NOT NULL
                    ORDER BY id
                """)

            prospects = cursor.fetchall()
            logger.info(f"Found {len(prospects)} prospects with MLB IDs")
            logger.info(f"Will query {len(SPORT_LEVELS)} sport levels for {len(self.seasons)} season(s)")
            logger.info(f"Sport levels: {', '.join([f'{id}={name}' for id, name in SPORT_LEVELS.items()])}")

            # Create aiohttp session for API calls
            async with aiohttp.ClientSession() as session:
                for idx, prospect in enumerate(prospects, 1):
                    prospect_id, mlb_player_id, name, position = prospect
                    logger.info(f"\n[{idx}/{len(prospects)}] Processing {name} (MLB ID: {mlb_player_id})")

                    try:
                        await self.collect_player_game_logs(
                            session,
                            conn,
                            cursor,
                            prospect_id,
                            mlb_player_id,
                            name,
                            position
                        )
                    except Exception as e:
                        logger.error(f"Error collecting data for {name}: {str(e)}")
                        self.errors += 1
                        continue

                    # Rate limiting
                    await asyncio.sleep(0.1)

            logger.info(f"\n{'='*80}")
            logger.info(f"COLLECTION COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"Game logs collected: {self.stats_collected}")
            logger.info(f"API calls made: {self.api_calls}")
            logger.info(f"Errors: {self.errors}")

        finally:
            conn.close()

    async def collect_player_game_logs(
        self,
        session: aiohttp.ClientSession,
        conn,
        cursor,
        prospect_id: int,
        mlb_player_id: str,
        name: str,
        position: str
    ):
        """Collect game logs for a single player across all specified seasons and sport levels."""

        # Convert mlb_player_id to int for API call
        try:
            player_id_int = int(mlb_player_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid MLB player ID: {mlb_player_id}")
            return

        player_total = 0

        for season in self.seasons:
            season_total = 0

            for sport_id, level_name in SPORT_LEVELS.items():
                try:
                    # Fetch game logs for this specific sport level
                    splits = await self.fetch_game_logs_for_sport(
                        session,
                        player_id_int,
                        season,
                        sport_id,
                        level_name
                    )

                    if splits:
                        # Save game logs to database
                        games_saved = self.save_game_logs(
                            conn,
                            cursor,
                            prospect_id,
                            player_id_int,
                            season,
                            level_name,
                            splits
                        )

                        if games_saved > 0:
                            logger.info(f"  {season} {level_name}: Saved {games_saved} games")
                            season_total += games_saved
                            self.stats_collected += games_saved

                    # Rate limiting between API calls
                    await asyncio.sleep(0.2)

                except Exception as e:
                    logger.error(f"  Error fetching {season} {level_name}: {str(e)}")
                    self.errors += 1
                    continue

            if season_total > 0:
                player_total += season_total
                logger.info(f"  Season {season} total: {season_total} games")

        if player_total > 0:
            logger.info(f"  Player total: {player_total} games")

    async def fetch_game_logs_for_sport(
        self,
        session: aiohttp.ClientSession,
        player_id: int,
        season: int,
        sport_id: int,
        level_name: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch game logs from MLB API for a specific sport level.

        Args:
            session: aiohttp session
            player_id: MLB player ID
            season: Season year
            sport_id: Sport ID (11=AAA, 12=AA, 13=A+, 14=A, 16=FRk)
            level_name: Level name for logging

        Returns:
            List of game splits
        """
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'season': season,
            'sportId': sport_id,  # KEY FIX: Query by sport level
            'gameType': 'R'  # Regular season
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                self.api_calls += 1

                if resp.status != 200:
                    return []

                data = await resp.json()

                if not data.get('stats') or not data['stats'][0].get('splits'):
                    return []

                return data['stats'][0]['splits']

        except asyncio.TimeoutError:
            logger.error(f"  Timeout fetching {season} {level_name}")
            return []
        except Exception as e:
            logger.error(f"  API error fetching {season} {level_name}: {str(e)}")
            return []

    def sanitize_stat_value(self, value: Any) -> Optional[float]:
        """
        Sanitize stat values from MLB API.

        The API returns strings like '-.--', '.---', etc. for undefined calculations.
        Convert these to None.
        """
        if value is None:
            return None

        if isinstance(value, str):
            # Check for special MLB API "undefined" values
            if value.startswith('.') and value.count('-') > 0:  # .---, -.--
                return None
            if value.startswith('-') and value.count('.') > 0:  # -.--
                return None

            # Try to convert to float
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        return value

    def save_game_logs(
        self,
        conn,
        cursor,
        prospect_id: int,
        mlb_player_id: int,
        season: int,
        level: str,
        splits: List[Dict[str, Any]]
    ) -> int:
        """Parse API response and save game logs to database."""

        games_saved = 0

        for game_split in splits:
            try:
                # Extract game info
                game_info = game_split.get('game', {})
                game_pk = game_info.get('gamePk')
                game_date = game_split.get('date')
                is_home = game_split.get('isHome')

                if not game_pk or not game_date:
                    continue

                # Extract team info
                team = game_split.get('team', {})
                team_id = team.get('id')
                team_name = team.get('name')

                opponent = game_split.get('opponent', {})
                opponent_id = opponent.get('id')
                opponent_name = opponent.get('name')

                # Extract stats
                stat = game_split.get('stat', {})

                # Determine if this is hitting or pitching data
                is_pitching = 'inningsPitched' in stat

                # Build parameter dictionary
                params = {
                    'prospect_id': prospect_id,
                    'mlb_player_id': mlb_player_id,
                    'season': season,
                    'game_pk': game_pk,
                    'game_date': game_date,
                    'level': level,  # KEY FIX: Use the level from sport_id mapping
                    'team_id': team_id,
                    'team': team_name,
                    'opponent_id': opponent_id,
                    'opponent': opponent_name,
                    'is_home': is_home,
                    'game_type': 'Regular',
                    'data_source': 'mlb_stats_api',

                    # Hitting stats
                    'games_played': stat.get('gamesPlayed'),
                    'at_bats': stat.get('atBats'),
                    'plate_appearances': stat.get('plateAppearances'),
                    'runs': stat.get('runs') if not is_pitching else None,
                    'hits': stat.get('hits') if not is_pitching else None,
                    'doubles': stat.get('doubles') if not is_pitching else None,
                    'triples': stat.get('triples') if not is_pitching else None,
                    'home_runs': stat.get('homeRuns') if not is_pitching else None,
                    'rbi': stat.get('rbi'),
                    'total_bases': stat.get('totalBases') if not is_pitching else None,
                    'walks': stat.get('baseOnBalls') if not is_pitching else None,
                    'intentional_walks': stat.get('intentionalWalks') if not is_pitching else None,
                    'strikeouts': stat.get('strikeOuts') if not is_pitching else None,
                    'hit_by_pitch': stat.get('hitByPitch') if not is_pitching else None,
                    'stolen_bases': stat.get('stolenBases') if not is_pitching else None,
                    'caught_stealing': stat.get('caughtStealing') if not is_pitching else None,
                    'fly_outs': stat.get('flyOuts') if not is_pitching else None,
                    'ground_outs': stat.get('groundOuts') if not is_pitching else None,
                    'air_outs': stat.get('airOuts') if not is_pitching else None,
                    'ground_into_double_play': stat.get('groundIntoDoublePlay'),
                    'ground_into_triple_play': stat.get('groundIntoTriplePlay'),
                    'sacrifice_hits': stat.get('sacBunts') if not is_pitching else None,
                    'sacrifice_flies': stat.get('sacFlies') if not is_pitching else None,
                    'left_on_base': stat.get('leftOnBase'),
                    'pitches_seen': stat.get('numberOfPitches') if not is_pitching else None,
                    'catchers_interference': stat.get('catchersInterference') if not is_pitching else None,
                    'batting_avg': self.sanitize_stat_value(stat.get('avg')) if not is_pitching else None,
                    'on_base_pct': self.sanitize_stat_value(stat.get('obp')) if not is_pitching else None,
                    'slugging_pct': self.sanitize_stat_value(stat.get('slg')) if not is_pitching else None,
                    'ops': self.sanitize_stat_value(stat.get('ops')) if not is_pitching else None,
                    'babip': self.sanitize_stat_value(stat.get('babip')) if not is_pitching else None,
                    'stolen_base_percentage': self.sanitize_stat_value(stat.get('stolenBasePercentage')),
                    'ground_outs_to_airouts': self.sanitize_stat_value(stat.get('groundOutsToAirouts')) if not is_pitching else None,
                    'at_bats_per_home_run': self.sanitize_stat_value(stat.get('atBatsPerHomeRun')),
                }

                # Build dynamic INSERT query
                columns = ', '.join(params.keys())
                placeholders = ', '.join(['%s'] * len(params))
                values = tuple(params.values())

                insert_query = f"""
                    INSERT INTO milb_game_logs ({columns})
                    VALUES ({placeholders})
                    ON CONFLICT (game_pk, mlb_player_id)
                    DO UPDATE SET
                        updated_at = now(),
                        level = EXCLUDED.level,
                        batting_avg = EXCLUDED.batting_avg,
                        ops = EXCLUDED.ops
                """

                cursor.execute(insert_query, values)
                conn.commit()

                games_saved += 1

            except psycopg2.IntegrityError as e:
                # Check if it's a constraint violation
                if 'valid_level' in str(e):
                    logger.warning(f"  Level '{level}' not in database constraint (game_pk={game_pk})")
                    logger.warning(f"  Add '{level}' to valid_level constraint to save this game")
                conn.rollback()
                continue
            except Exception as e:
                logger.warning(f"  Error saving game {game_pk}: {str(e)}")
                conn.rollback()
                continue

        return games_saved


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Collect Minor League game log data for prospects from MLB Stats API (FIXED VERSION)'
    )
    parser.add_argument(
        '--seasons',
        nargs='+',
        type=int,
        default=[2025],
        help='Seasons to collect (default: 2025)'
    )
    parser.add_argument(
        '--player-id',
        type=int,
        default=None,
        help='Optional: Collect for specific MLB player ID only'
    )

    args = parser.parse_args()

    logger.info(f"="*80)
    logger.info(f"MILB GAME LOG COLLECTION - FIXED VERSION")
    logger.info(f"="*80)
    logger.info(f"Starting MiLB game log collection for seasons: {args.seasons}")
    logger.info(f"This version queries each sport level separately using sportId parameter")
    logger.info(f"")

    collector = MiLBGameLogCollectorFixed(seasons=args.seasons)

    # Run async collection
    asyncio.run(collector.collect_all_game_logs(player_id=args.player_id))


if __name__ == '__main__':
    main()
