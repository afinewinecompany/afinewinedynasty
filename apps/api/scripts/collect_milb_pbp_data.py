"""
Collect MiLB pitch-by-pitch data from MLB Stats API.

This script finds MiLB games for prospects and collects detailed pitch-by-pitch
data, then aggregates it into game-level statistics for the milb_game_logs table.

Based on baseballr's mlb_pbp() approach - both major and minor league
pitch-by-pitch data can be pulled using game_pk values.

Usage:
    python collect_milb_pbp_data.py --seasons 2024 2023
    python collect_milb_pbp_data.py --prospect-id 511 --seasons 2024
"""

import argparse
import asyncio
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

from app.db.database import get_db_sync
from app.services.mlb_api_service import MLBAPIClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MiLBPitchByPitchCollector:
    """Collect MiLB pitch-by-pitch data and aggregate to game logs."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # MiLB sport IDs
    MILB_SPORT_IDS = {
        11: "AAA",      # Triple-A
        12: "AA",       # Double-A
        13: "A+",       # High-A
        14: "A",        # Single-A
        15: "Rookie",   # Rookie
        16: "Rookie+"   # Rookie Advanced
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5  # 2 requests/second
        self.games_collected = 0
        self.errors = 0

    async def __aenter__(self):
        """Initialize aiohttp session."""
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": "A Fine Wine Dynasty Bot 1.0 (Research/Educational)",
                "Accept": "application/json"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session."""
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON data from URL."""
        try:
            await asyncio.sleep(self.request_delay)

            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    logger.warning(f"  HTTP {response.status} for {url}")
                    return None

        except Exception as e:
            logger.error(f"  Error fetching {url}: {str(e)}")
            self.errors += 1
            return None

    def get_prospects_with_mlb_ids(self, db, prospect_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get prospects that have MLB player IDs."""
        if prospect_id:
            query = text("""
                SELECT
                    id as prospect_id,
                    name,
                    mlb_player_id,
                    position,
                    organization
                FROM prospects
                WHERE id = :prospect_id
                    AND mlb_player_id IS NOT NULL
            """)
            result = db.execute(query, {"prospect_id": prospect_id})
        else:
            query = text("""
                SELECT
                    id as prospect_id,
                    name,
                    mlb_player_id,
                    position,
                    organization
                FROM prospects
                WHERE mlb_player_id IS NOT NULL
                ORDER BY id
            """)
            result = db.execute(query)

        prospects = []
        for row in result:
            prospects.append({
                "prospect_id": row.prospect_id,
                "name": row.name,
                "mlb_player_id": row.mlb_player_id,
                "position": row.position,
                "organization": row.organization
            })

        return prospects

    async def find_player_games(self, player_id: int, season: int) -> List[Dict[str, Any]]:
        """
        Find all games for a player in a season across all MiLB levels.
        Returns list of dicts with game_pk, game_date, and level.
        """
        logger.debug(f"  Finding games for player {player_id} in {season}...")

        all_games = {}  # Use dict to dedupe by game_pk

        # Query each MiLB sport level separately (API doesn't support multiple sportIds)
        for sport_id, level_name in self.MILB_SPORT_IDS.items():
            url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting,pitching&sportId={sport_id}"

            data = await self.fetch_json(url)
            if not data:
                continue

            try:
                stats = data.get('stats', [])
                for stat_group in stats:
                    splits = stat_group.get('splits', [])
                    for split in splits:
                        game = split.get('game', {})
                        game_pk = game.get('gamePk')
                        game_date = split.get('date')  # Game date is in split, not game

                        if game_pk and game_date:
                            all_games[game_pk] = {
                                'game_pk': game_pk,
                                'game_date': game_date,
                                'level': level_name  # Track the MiLB level
                            }

            except Exception as e:
                logger.error(f"  Error parsing games for sportId {sport_id}: {str(e)}")
                continue

        games = list(all_games.values())
        logger.debug(f"  Found {len(games)} total games for player {player_id}")
        return games

    async def fetch_pitch_by_pitch(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """
        Fetch pitch-by-pitch data for a game.
        This is the core mlb_pbp() functionality from baseballr.
        """
        url = f"{self.BASE_URL}/game/{game_pk}/playByPlay"
        return await self.fetch_json(url)

    def aggregate_game_stats(
        self,
        pbp_data: Dict[str, Any],
        game_pk: int,
        game_date_str: str,
        level: str,
        player_id: int,
        prospect_id: int,
        season: int
    ) -> Optional[Dict[str, Any]]:
        """
        Aggregate pitch-by-pitch data into game-level statistics.
        Returns data in format matching milb_game_logs schema.
        """
        try:
            logger.debug(f"    Aggregating game {game_pk} on {game_date_str}...")

            game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()

            # Initialize stats
            hitting_stats = defaultdict(int)
            hitting_stats['batting_avg'] = 0.0
            hitting_stats['obp'] = 0.0
            hitting_stats['slg'] = 0.0
            hitting_stats['ops'] = 0.0

            pitching_stats = defaultdict(int)
            pitching_stats['innings_pitched'] = 0.0
            pitching_stats['era'] = 0.0
            pitching_stats['whip'] = 0.0

            # Parse all plays to find player's stats
            plays = pbp_data.get('allPlays', [])
            is_pitcher = False

            # Ensure player_id is int for comparison
            player_id_int = int(player_id) if player_id else None

            for play in plays:
                matchup = play.get('matchup', {})
                batter_id = matchup.get('batter', {}).get('id')
                pitcher_id = matchup.get('pitcher', {}).get('id')

                # Check if our player was involved (compare as ints)
                if batter_id == player_id_int:
                    # Parse hitting play
                    result = play.get('result', {})
                    event = result.get('event', '')
                    rbi = result.get('rbi', 0)

                    hitting_stats['plate_appearances'] += 1

                    # Count at-bats (excludes walks, HBP, sac flies)
                    if event not in ['Walk', 'Intent Walk', 'Hit By Pitch', 'Sac Fly']:
                        hitting_stats['at_bats'] += 1

                    # Parse event types
                    if 'Single' in event:
                        hitting_stats['hits'] += 1
                    elif 'Double' in event:
                        hitting_stats['hits'] += 1
                        hitting_stats['doubles'] += 1
                    elif 'Triple' in event:
                        hitting_stats['hits'] += 1
                        hitting_stats['triples'] += 1
                    elif 'Home Run' in event:
                        hitting_stats['hits'] += 1
                        hitting_stats['home_runs'] += 1
                    elif 'Walk' in event:
                        hitting_stats['walks'] += 1
                    elif 'Strikeout' in event:
                        hitting_stats['strikeouts'] += 1
                    elif 'Hit By Pitch' in event:
                        hitting_stats['hit_by_pitch'] += 1

                    hitting_stats['rbi'] += rbi

                    # Check for runners
                    runners = play.get('runners', [])
                    for runner in runners:
                        if runner.get('details', {}).get('runner', {}).get('id') == player_id_int:
                            movement = runner.get('movement', {})
                            if movement.get('start'):
                                start_base = movement.get('start')
                                end_base = movement.get('end')

                                # Track runs scored
                                if end_base == 'score':
                                    hitting_stats['runs'] += 1

                                # Track stolen bases
                                if runner.get('details', {}).get('event') == 'Stolen Base':
                                    hitting_stats['stolen_bases'] += 1
                                elif runner.get('details', {}).get('event') == 'Caught Stealing':
                                    hitting_stats['caught_stealing'] += 1

                elif pitcher_id == player_id_int:
                    is_pitcher = True
                    # Parse pitching play
                    play_events = play.get('playEvents', [])

                    for event in play_events:
                        if event.get('isPitch'):
                            pitching_stats['number_of_pitches_pitched'] += 1

                            pitch_data = event.get('pitchData', {})
                            if pitch_data.get('zone'):
                                # Estimate strikes (simplified)
                                if event.get('details', {}).get('call', {}).get('description') in ['Called Strike', 'Swinging Strike', 'Foul']:
                                    pitching_stats['strikes'] += 1

                    # Get result
                    result = play.get('result', {})
                    event = result.get('event', '')

                    # Count outs
                    about = play.get('about', {})
                    if about.get('hasOut'):
                        pitching_stats['outs'] += about.get('outs', 0)

                    # Parse events
                    if 'Single' in event or 'Double' in event or 'Triple' in event or 'Home Run' in event:
                        pitching_stats['hits_allowed'] += 1
                    if 'Home Run' in event:
                        pitching_stats['home_runs_allowed'] += 1
                    if 'Walk' in event:
                        pitching_stats['walks_allowed'] += 1
                    if 'Strikeout' in event:
                        pitching_stats['strikeouts_pitched'] += 1
                    if 'Hit By Pitch' in event:
                        pitching_stats['hit_batsmen'] += 1

                    # Runs/earned runs (simplified - assumes all runs are earned)
                    runs = result.get('rbi', 0)  # Runs scored on play
                    pitching_stats['runs_allowed'] += runs
                    pitching_stats['earned_runs'] += runs

            # Calculate derived stats
            if hitting_stats['at_bats'] > 0:
                hitting_stats['batting_avg'] = hitting_stats['hits'] / hitting_stats['at_bats']

            if pitching_stats['outs'] > 0:
                pitching_stats['innings_pitched'] = pitching_stats['outs'] / 3.0

            # Build database record
            record = {
                'prospect_id': prospect_id,
                'mlb_player_id': player_id,
                'season': season,
                'game_pk': game_pk,
                'game_date': game_date,
                'level': level,  # MiLB level (AAA, AA, A+, A, Rookie)
                'game_type': 'Regular',  # Regular season (must match CHECK constraint)
                'games_played': 1,
                'data_source': 'mlb_stats_api_pbp',
            }

            # Add stats based on whether player batted or pitched
            if not is_pitcher or hitting_stats['plate_appearances'] > 0:
                record.update({
                    'at_bats': hitting_stats['at_bats'],
                    'plate_appearances': hitting_stats['plate_appearances'],
                    'runs': hitting_stats['runs'],
                    'hits': hitting_stats['hits'],
                    'doubles': hitting_stats['doubles'],
                    'triples': hitting_stats['triples'],
                    'home_runs': hitting_stats['home_runs'],
                    'rbi': hitting_stats['rbi'],
                    'walks': hitting_stats['walks'],
                    'strikeouts': hitting_stats['strikeouts'],
                    'hit_by_pitch': hitting_stats['hit_by_pitch'],
                    'stolen_bases': hitting_stats['stolen_bases'],
                    'caught_stealing': hitting_stats['caught_stealing'],
                    'batting_avg': hitting_stats['batting_avg'],
                    'on_base_pct': hitting_stats['obp'],  # Database uses on_base_pct
                    'slugging_pct': hitting_stats['slg'],  # Database uses slugging_pct
                    'ops': hitting_stats['ops'],  # Database uses ops
                })

            if is_pitcher:
                record.update({
                    'innings_pitched': pitching_stats['innings_pitched'],
                    'number_of_pitches_pitched': pitching_stats['number_of_pitches_pitched'],
                    'strikes': pitching_stats['strikes'],
                    'hits_allowed': pitching_stats['hits_allowed'],
                    'runs_allowed': pitching_stats['runs_allowed'],
                    'earned_runs': pitching_stats['earned_runs'],
                    'home_runs_allowed': pitching_stats['home_runs_allowed'],
                    'walks_allowed': pitching_stats['walks_allowed'],
                    'strikeouts_pitched': pitching_stats['strikeouts_pitched'],
                    'hit_batsmen': pitching_stats['hit_batsmen'],
                    'outs': pitching_stats['outs'],
                    'era': pitching_stats['era'],
                    'whip': pitching_stats['whip'],
                })

            return record

        except Exception as e:
            logger.error(f"  Error aggregating stats: {str(e)}")
            return None

    def save_game_log(self, db, game: Dict[str, Any]) -> bool:
        """Save a single game log to database."""
        try:
            # Build INSERT query dynamically
            columns = list(game.keys())
            placeholders = [f":{col}" for col in columns]

            query = text(f"""
                INSERT INTO milb_game_logs ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """)

            db.execute(query, game)
            db.commit()
            return True

        except IntegrityError:
            # Duplicate game
            db.rollback()
            return False
        except Exception as e:
            logger.error(f"  Error saving game: {str(e)}")
            db.rollback()
            self.errors += 1
            return False

    async def collect_prospect_games(
        self,
        db,
        prospect: Dict[str, Any],
        seasons: List[int]
    ) -> int:
        """Collect all game logs for a prospect across specified seasons."""
        name = prospect['name']
        player_id = prospect['mlb_player_id']
        prospect_id = prospect['prospect_id']

        logger.info(f"Processing {name} (MLB ID: {player_id})")

        total_games = 0

        for season in seasons:
            logger.info(f"  Season {season}...")

            # Find all games for this player
            games = await self.find_player_games(player_id, season)

            if not games:
                logger.info(f"  No games found for {season}")
                continue

            logger.info(f"  Found {len(games)} games")

            # Fetch pitch-by-pitch data for each game
            saved = 0
            for i, game_info in enumerate(games, 1):
                game_pk = game_info['game_pk']
                game_date = game_info['game_date']
                level = game_info['level']

                if i % 10 == 0:
                    logger.info(f"    Processing game {i}/{len(games)}...")

                pbp_data = await self.fetch_pitch_by_pitch(game_pk)
                if not pbp_data:
                    continue

                # Aggregate to game stats
                game_record = self.aggregate_game_stats(
                    pbp_data,
                    game_pk,
                    game_date,
                    level,
                    player_id,
                    prospect_id,
                    season
                )

                if not game_record:
                    logger.debug(f"    Game {game_pk}: No stats found")
                    continue

                if self.save_game_log(db, game_record):
                    saved += 1
                    logger.debug(f"    Game {game_pk}: Saved")

            logger.info(f"  Saved {saved} new games for {season}")
            total_games += saved
            self.games_collected += saved

        return total_games


async def main():
    """Main collection function."""
    parser = argparse.ArgumentParser(
        description="Collect MiLB pitch-by-pitch data from MLB Stats API"
    )
    parser.add_argument(
        '--seasons',
        type=int,
        nargs='+',
        default=[2024, 2023],
        help='Seasons to collect (e.g., 2024 2023 2022)'
    )
    parser.add_argument(
        '--prospect-id',
        type=int,
        help='Collect for specific prospect ID only (for testing)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of prospects to process (for testing)'
    )

    args = parser.parse_args()

    logger.info("Starting MiLB pitch-by-pitch data collection")
    logger.info(f"Seasons: {args.seasons}")

    # Get database connection
    db = get_db_sync()

    try:
        # Initialize collector
        async with MiLBPitchByPitchCollector() as collector:
            # Get prospects
            prospects = collector.get_prospects_with_mlb_ids(db, args.prospect_id)

            if args.limit:
                prospects = prospects[:args.limit]

            logger.info(f"Found {len(prospects)} prospects with MLB IDs")

            if not prospects:
                logger.warning("No prospects found with MLB IDs")
                return

            # Process each prospect
            start_time = time.time()

            for i, prospect in enumerate(prospects, 1):
                logger.info(f"[{i}/{len(prospects)}] {prospect['name']}")

                try:
                    games_collected = await collector.collect_prospect_games(
                        db,
                        prospect,
                        args.seasons
                    )

                    if games_collected > 0:
                        logger.info(f"  ✓ Collected {games_collected} total games")
                    else:
                        logger.info(f"  No new games found")

                except Exception as e:
                    logger.error(f"  Error processing {prospect['name']}: {str(e)}")
                    collector.errors += 1
                    continue

            # Summary
            elapsed = time.time() - start_time
            logger.info("")
            logger.info("Collection complete!")
            logger.info(f"Total games collected: {collector.games_collected}")
            logger.info(f"Errors: {collector.errors}")
            logger.info(f"Time elapsed: {elapsed:.1f}s")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
