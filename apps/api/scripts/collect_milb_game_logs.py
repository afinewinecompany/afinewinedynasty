#!/usr/bin/env python3
"""
MiLB Game Log Data Collection (from MLB Stats API)
===================================================
Collects game-by-game Minor League statistics for prospects.

This script:
1. Identifies prospects with MLB player IDs
2. Fetches Minor League game logs from MLB Stats API for recent seasons
3. Stores game-by-game MiLB stats in milb_game_logs table

Usage:
    python collect_milb_game_logs.py --seasons 2024 2023 2022
    python collect_milb_game_logs.py --seasons 2024 --player-id 660271
"""

import sys
import os
import argparse
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db_sync
from app.services.mlb_api_service import MLBAPIClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MiLBGameLogCollector:
    """Collects Minor League game log data for prospects from MLB Stats API."""

    def __init__(self, seasons: List[int]):
        self.seasons = seasons
        self.stats_collected = 0
        self.errors = 0

    async def collect_all_game_logs(self, player_id: Optional[int] = None):
        """
        Collect MiLB game logs for all prospects with MLB IDs.

        Args:
            player_id: Optional specific player ID to collect for
        """
        db = get_db_sync()

        try:
            # Get prospects with MLB IDs
            if player_id:
                query = text("""
                    SELECT id, mlb_player_id, name, position
                    FROM prospects
                    WHERE mlb_player_id = :player_id
                """)
                result = db.execute(query, {'player_id': str(player_id)})
            else:
                query = text("""
                    SELECT id, mlb_player_id, name, position
                    FROM prospects
                    WHERE mlb_player_id IS NOT NULL
                    ORDER BY id
                """)
                result = db.execute(query)

            prospects = result.fetchall()
            logger.info(f"Found {len(prospects)} prospects with MLB IDs")

            async with MLBAPIClient() as api_client:
                for idx, prospect in enumerate(prospects, 1):
                    prospect_id, mlb_player_id, name, position = prospect
                    logger.info(f"[{idx}/{len(prospects)}] Processing {name} (MLB ID: {mlb_player_id})")

                    try:
                        await self.collect_player_game_logs(
                            api_client,
                            db,
                            prospect_id,
                            mlb_player_id,
                            name,
                            position
                        )
                    except Exception as e:
                        logger.error(f"Error collecting data for {name}: {str(e)}")
                        self.errors += 1
                        continue

            logger.info(f"\nCollection complete!")
            logger.info(f"Game logs collected: {self.stats_collected}")
            logger.info(f"Errors: {self.errors}")

        finally:
            db.close()

    async def collect_player_game_logs(
        self,
        api_client: MLBAPIClient,
        db,
        prospect_id: int,
        mlb_player_id: str,
        name: str,
        position: str
    ):
        """Collect game logs for a single player across all specified seasons."""

        # Convert mlb_player_id to int for API call
        try:
            player_id_int = int(mlb_player_id)
        except (ValueError, TypeError):
            logger.error(f"Invalid MLB player ID: {mlb_player_id}")
            return

        for season in self.seasons:
            try:
                logger.info(f"  Fetching {season} game logs...")

                # Fetch game logs from MLB API
                response = await api_client.get_player_game_logs(
                    player_id=player_id_int,
                    season=season,
                    game_type="R"  # Regular season only
                )

                # Parse and store game logs
                games_saved = self.save_game_logs(
                    db,
                    prospect_id,
                    player_id_int,
                    season,
                    response
                )

                if games_saved > 0:
                    logger.info(f"  Saved {games_saved} games for {season}")
                    self.stats_collected += games_saved
                else:
                    logger.info(f"  No game logs found for {season}")

            except Exception as e:
                logger.error(f"  Error fetching {season} game logs: {str(e)}")
                self.errors += 1
                continue

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
        db,
        prospect_id: int,
        mlb_player_id: int,
        season: int,
        api_response: Dict[str, Any]
    ) -> int:
        """Parse API response and save game logs to database."""

        games_saved = 0

        try:
            # Navigate API response structure
            stats = api_response.get('stats', [])

            for stat_group in stats:
                if stat_group.get('type', {}).get('displayName') != 'gameLog':
                    continue

                splits = stat_group.get('splits', [])

                for game_split in splits:
                    try:
                        # Extract game info
                        game_info = game_split.get('game', {})
                        game_pk = game_info.get('gamePk')
                        game_date = game_split.get('date')
                        is_home = game_split.get('isHome')

                        if not game_pk or not game_date:
                            continue

                        # Extract stats
                        stat = game_split.get('stat', {})

                        # Determine if this is hitting or pitching data
                        is_pitching = 'inningsPitched' in stat

                        # Build comprehensive parameter dictionary with ALL available stats
                        params = {
                            'prospect_id': prospect_id,
                            'mlb_player_id': mlb_player_id,
                            'season': season,
                            'game_pk': game_pk,
                            'game_date': game_date,
                            'game_type': 'R',
                            'is_home': is_home,
                            'data_source': 'mlb_stats_api',

                            # === HITTING STATS (36 fields) ===
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
                            'sacrifice_hits': stat.get('sacBunts') if not is_pitching else None,  # Map sac bunts to sacrifice_hits
                            'sacrifice_flies': stat.get('sacFlies') if not is_pitching else None,  # Map sac flies to sacrifice_flies
                            'left_on_base': stat.get('leftOnBase'),
                            'pitches_seen': stat.get('numberOfPitches') if not is_pitching else None,  # Old column name
                            'catchers_interference': stat.get('catchersInterference') if not is_pitching else None,
                            'batting_avg': self.sanitize_stat_value(stat.get('avg')) if not is_pitching else None,
                            'on_base_pct': self.sanitize_stat_value(stat.get('obp')) if not is_pitching else None,  # Old column name
                            'slugging_pct': self.sanitize_stat_value(stat.get('slg')) if not is_pitching else None,  # Old column name
                            'ops': self.sanitize_stat_value(stat.get('ops')) if not is_pitching else None,
                            'babip': self.sanitize_stat_value(stat.get('babip')) if not is_pitching else None,
                            'stolen_base_percentage': self.sanitize_stat_value(stat.get('stolenBasePercentage')),
                            'ground_outs_to_airouts': self.sanitize_stat_value(stat.get('groundOutsToAirouts')) if not is_pitching else None,
                            'at_bats_per_home_run': self.sanitize_stat_value(stat.get('atBatsPerHomeRun')),

                            # === PITCHING STATS (63 fields) ===
                            'games_started': stat.get('gamesStarted') if is_pitching else None,
                            'games_pitched': stat.get('gamesPitched') if is_pitching else None,
                            'complete_games': stat.get('completeGames') if is_pitching else None,
                            'shutouts': stat.get('shutouts') if is_pitching else None,
                            'games_finished': stat.get('gamesFinished') if is_pitching else None,
                            'wins': stat.get('wins') if is_pitching else None,
                            'losses': stat.get('losses') if is_pitching else None,
                            'saves': stat.get('saves') if is_pitching else None,
                            'save_opportunities': stat.get('saveOpportunities') if is_pitching else None,
                            'holds': stat.get('holds') if is_pitching else None,
                            'blown_saves': stat.get('blownSaves') if is_pitching else None,
                            'innings_pitched': stat.get('inningsPitched') if is_pitching else None,
                            'outs': stat.get('outs') if is_pitching else None,
                            'batters_faced': stat.get('battersFaced') if is_pitching else None,
                            'number_of_pitches_pitched': stat.get('numberOfPitches') if is_pitching else None,
                            'strikes': stat.get('strikes') if is_pitching else None,
                            'hits_allowed': stat.get('hits') if is_pitching else None,
                            'runs_allowed': stat.get('runs') if is_pitching else None,
                            'earned_runs': stat.get('earnedRuns') if is_pitching else None,
                            'home_runs_allowed': stat.get('homeRuns') if is_pitching else None,
                            'walks_allowed': stat.get('baseOnBalls') if is_pitching else None,
                            'intentional_walks_allowed': stat.get('intentionalWalks') if is_pitching else None,
                            'strikeouts_pitched': stat.get('strikeOuts') if is_pitching else None,
                            'hit_batsmen': stat.get('hitBatsmen') if is_pitching else None,
                            'stolen_bases_allowed': stat.get('stolenBases') if is_pitching else None,
                            'caught_stealing_allowed': stat.get('caughtStealing') if is_pitching else None,
                            'balks': stat.get('balks') if is_pitching else None,
                            'wild_pitches': stat.get('wildPitches') if is_pitching else None,
                            'pickoffs': stat.get('pickoffs') if is_pitching else None,
                            'inherited_runners': stat.get('inheritedRunners') if is_pitching else None,
                            'inherited_runners_scored': stat.get('inheritedRunnersScored') if is_pitching else None,
                            'fly_outs_pitched': stat.get('flyOuts') if is_pitching else None,
                            'ground_outs_pitched': stat.get('groundOuts') if is_pitching else None,
                            'air_outs_pitched': stat.get('airOuts') if is_pitching else None,
                            'ground_into_double_play_pitched': stat.get('groundIntoDoublePlay') if is_pitching else None,
                            'total_bases_allowed': stat.get('totalBases') if is_pitching else None,
                            'sac_bunts_allowed': stat.get('sacBunts') if is_pitching else None,
                            'sac_flies_allowed': stat.get('sacFlies') if is_pitching else None,
                            'catchers_interference_pitched': stat.get('catchersInterference') if is_pitching else None,
                            'era': self.sanitize_stat_value(stat.get('era')) if is_pitching else None,
                            'whip': self.sanitize_stat_value(stat.get('whip')) if is_pitching else None,
                            'avg_against': self.sanitize_stat_value(stat.get('avg')) if is_pitching else None,
                            'obp_against': self.sanitize_stat_value(stat.get('obp')) if is_pitching else None,
                            'slg_against': self.sanitize_stat_value(stat.get('slg')) if is_pitching else None,
                            'ops_against': self.sanitize_stat_value(stat.get('ops')) if is_pitching else None,
                            'win_percentage': self.sanitize_stat_value(stat.get('winPercentage')) if is_pitching else None,
                            'strike_percentage': self.sanitize_stat_value(stat.get('strikePercentage')) if is_pitching else None,
                            'pitches_per_inning': self.sanitize_stat_value(stat.get('pitchesPerInning')) if is_pitching else None,
                            'strikeout_walk_ratio': self.sanitize_stat_value(stat.get('strikeoutWalkRatio')) if is_pitching else None,
                            'strikeouts_per_9inn': self.sanitize_stat_value(stat.get('strikeoutsPer9Inn')) if is_pitching else None,
                            'walks_per_9inn': self.sanitize_stat_value(stat.get('walksPer9Inn')) if is_pitching else None,
                            'hits_per_9inn': self.sanitize_stat_value(stat.get('hitsPer9Inn')) if is_pitching else None,
                            'runs_scored_per_9': self.sanitize_stat_value(stat.get('runsScoredPer9')) if is_pitching else None,
                            'home_runs_per_9': self.sanitize_stat_value(stat.get('homeRunsPer9')) if is_pitching else None,
                            'stolen_base_percentage_against': self.sanitize_stat_value(stat.get('stolenBasePercentage')) if is_pitching else None,
                            'ground_outs_to_airouts_pitched': self.sanitize_stat_value(stat.get('groundOutsToAirouts')) if is_pitching else None,
                        }

                        # Build dynamic INSERT query for ALL fields
                        columns = ', '.join(params.keys())
                        placeholders = ', '.join(f':{key}' for key in params.keys())

                        insert_query = text(f"""
                            INSERT INTO milb_game_logs ({columns})
                            VALUES ({placeholders})
                            ON CONFLICT (mlb_player_id, game_pk, season)
                            DO UPDATE SET
                                updated_at = now(),
                                batting_avg = EXCLUDED.batting_avg,
                                ops = EXCLUDED.ops
                        """)

                        db.execute(insert_query, params)
                        db.commit()  # Commit each game individually to avoid transaction rollback issues

                        games_saved += 1

                    except IntegrityError as e:
                        # Game already exists, rollback and skip
                        db.rollback()
                        continue
                    except Exception as e:
                        logger.warning(f"  Error saving game {game_pk}: {str(e)}")
                        db.rollback()
                        continue

        except Exception as e:
            logger.error(f"Error parsing game logs: {str(e)}")
            db.rollback()

        return games_saved


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Collect Minor League game log data for prospects from MLB Stats API'
    )
    parser.add_argument(
        '--seasons',
        nargs='+',
        type=int,
        default=[2024, 2023, 2022],
        help='Seasons to collect (default: 2024 2023 2022)'
    )
    parser.add_argument(
        '--player-id',
        type=int,
        default=None,
        help='Optional: Collect for specific MLB player ID only'
    )

    args = parser.parse_args()

    logger.info(f"Starting MiLB game log collection for seasons: {args.seasons}")

    collector = MiLBGameLogCollector(seasons=args.seasons)

    # Run async collection
    asyncio.run(collector.collect_all_game_logs(player_id=args.player_id))


if __name__ == '__main__':
    main()
