"""
Collect play-by-play data for ALL MiLB players in 2024.

This script discovers all MiLB teams and rosters, then collects game-by-game
pitch-by-pitch data for every player. This creates a comprehensive dataset
for machine learning analysis.

Strategy:
1. Query MLB Stats API for all MiLB teams by sport level
2. Get rosters for each team throughout the 2024 season
3. Collect game logs for each player
4. Store in database for ML training

Usage:
    python collect_all_milb_players_2024.py --levels AAA AA A+
    python collect_all_milb_players_2024.py --team-id 1234 --season 2024
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

from app.db.database import get_db_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllMiLBPlayerCollector:
    """Collect data for all MiLB players."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # MiLB sport IDs
    MILB_SPORT_IDS = {
        11: "AAA",
        12: "AA",
        13: "A+",
        14: "A",
        15: "Rookie",
        16: "Rookie+"
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.discovered_players: Set[int] = set()
        self.games_collected = 0
        self.players_processed = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from URL with rate limiting."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def get_milb_teams(self, sport_id: int, season: int) -> List[Dict[str, Any]]:
        """Get all teams for a MiLB level."""
        url = f"{self.BASE_URL}/teams?sportId={sport_id}&season={season}"

        data = await self.fetch_json(url)
        if not data:
            return []

        teams = data.get('teams', [])
        logger.info(f"  Found {len(teams)} {self.MILB_SPORT_IDS.get(sport_id)} teams")

        return teams

    async def get_team_roster(self, team_id: int, season: int) -> List[Dict[str, Any]]:
        """Get roster for a team."""
        url = f"{self.BASE_URL}/teams/{team_id}/roster?season={season}"

        data = await self.fetch_json(url)
        if not data:
            return []

        roster = data.get('roster', [])
        return roster

    async def discover_all_players(self, sport_ids: List[int], season: int) -> List[Dict[str, Any]]:
        """Discover all players across specified MiLB levels."""

        logger.info(f"Discovering all MiLB players for {season}...")

        all_players = {}

        for sport_id in sport_ids:
            level = self.MILB_SPORT_IDS.get(sport_id)
            logger.info(f"\nProcessing {level} level (sportId={sport_id})...")

            # Get all teams for this level
            teams = await self.get_milb_teams(sport_id, season)

            for i, team in enumerate(teams, 1):
                team_id = team.get('id')
                team_name = team.get('name')

                logger.info(f"  [{i}/{len(teams)}] {team_name}...")

                # Get roster
                roster = await self.get_team_roster(team_id, season)

                for player_entry in roster:
                    person = player_entry.get('person', {})
                    player_id = person.get('id')
                    player_name = person.get('fullName')
                    position = player_entry.get('position', {}).get('abbreviation')

                    if player_id and player_id not in all_players:
                        all_players[player_id] = {
                            'player_id': player_id,
                            'name': player_name,
                            'position': position,
                            'team_name': team_name,
                            'level': level
                        }

                logger.info(f"    Found {len(roster)} players (Total unique: {len(all_players)})")

        logger.info(f"\nDiscovered {len(all_players)} unique players")
        return list(all_players.values())

    async def find_player_games(self, player_id: int, season: int, sport_ids: List[int]) -> List[Dict[str, Any]]:
        """Find all games for a player."""

        all_games = {}

        for sport_id in sport_ids:
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
                        game_date = split.get('date')

                        if game_pk and game_date:
                            all_games[game_pk] = {
                                'game_pk': game_pk,
                                'game_date': game_date,
                                'level': self.MILB_SPORT_IDS.get(sport_id)
                            }
            except Exception as e:
                logger.debug(f"Error parsing games for player {player_id}: {str(e)}")
                continue

        return list(all_games.values())

    async def fetch_pitch_by_pitch(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Fetch pitch-by-pitch data."""
        url = f"{self.BASE_URL}/game/{game_pk}/playByPlay"
        return await self.fetch_json(url)

    def save_player_to_db(self, db, player: Dict[str, Any]) -> bool:
        """Save player to milb_players table (create if doesn't exist)."""
        try:
            # Create table if not exists
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS milb_players (
                    id SERIAL PRIMARY KEY,
                    mlb_player_id INTEGER UNIQUE NOT NULL,
                    name VARCHAR(255),
                    position VARCHAR(10),
                    team_name VARCHAR(255),
                    level VARCHAR(20),
                    season INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            db.commit()

            # Insert player
            db.execute(text("""
                INSERT INTO milb_players (mlb_player_id, name, position, team_name, level, season)
                VALUES (:player_id, :name, :position, :team_name, :level, 2024)
                ON CONFLICT (mlb_player_id) DO NOTHING
            """), player)
            db.commit()
            return True

        except Exception as e:
            logger.debug(f"Error saving player {player.get('player_id')}: {str(e)}")
            db.rollback()
            return False

    def aggregate_game_stats(
        self,
        pbp_data: Dict[str, Any],
        game_pk: int,
        game_date: str,
        level: str,
        player_id: int,
        season: int
    ) -> Optional[Dict[str, Any]]:
        """Aggregate PBP data to game stats."""
        # Use same aggregation logic from collect_milb_pbp_data.py
        # (Simplified for now - full implementation would mirror that script)

        from datetime import datetime
        from collections import defaultdict

        try:
            game_date_obj = datetime.strptime(game_date, '%Y-%m-%d').date()

            player_id_int = int(player_id)
            plays = pbp_data.get('allPlays', [])

            # Count stats
            hitting_stats = defaultdict(int)
            is_pitcher = False

            for play in plays:
                matchup = play.get('matchup', {})
                batter_id = matchup.get('batter', {}).get('id')
                pitcher_id = matchup.get('pitcher', {}).get('id')

                if batter_id == player_id_int:
                    result = play.get('result', {})
                    event = result.get('event', '')

                    hitting_stats['plate_appearances'] += 1

                    if event not in ['Walk', 'Intent Walk', 'Hit By Pitch', 'Sac Fly']:
                        hitting_stats['at_bats'] += 1

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

                    hitting_stats['rbi'] += result.get('rbi', 0)

            # Build record
            if hitting_stats['plate_appearances'] > 0:
                return {
                    'mlb_player_id': player_id,
                    'season': season,
                    'game_pk': game_pk,
                    'game_date': game_date_obj,
                    'level': level,
                    'game_type': 'Regular',
                    'games_played': 1,
                    'data_source': 'milb_stats_api_pbp_all',
                    'at_bats': hitting_stats['at_bats'],
                    'plate_appearances': hitting_stats['plate_appearances'],
                    'hits': hitting_stats['hits'],
                    'doubles': hitting_stats['doubles'],
                    'triples': hitting_stats['triples'],
                    'home_runs': hitting_stats['home_runs'],
                    'walks': hitting_stats['walks'],
                    'strikeouts': hitting_stats['strikeouts'],
                    'rbi': hitting_stats['rbi'],
                }

            return None

        except Exception as e:
            logger.debug(f"Error aggregating game {game_pk}: {str(e)}")
            return None

    def save_game_log(self, db, game: Dict[str, Any]) -> bool:
        """Save game log to database."""
        try:
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
            db.rollback()
            return False
        except Exception as e:
            logger.debug(f"Error saving game: {str(e)}")
            db.rollback()
            return False

    async def collect_player_data(
        self,
        db,
        player: Dict[str, Any],
        season: int,
        sport_ids: List[int]
    ) -> int:
        """Collect all game data for a player."""

        player_id = player['player_id']
        player_name = player['name']

        # Find games
        games = await self.find_player_games(player_id, season, sport_ids)

        if not games:
            return 0

        saved = 0

        for game_info in games:
            game_pk = game_info['game_pk']
            game_date = game_info['game_date']
            level = game_info['level']

            # Fetch PBP
            pbp_data = await self.fetch_pitch_by_pitch(game_pk)
            if not pbp_data:
                continue

            # Aggregate
            game_record = self.aggregate_game_stats(
                pbp_data, game_pk, game_date, level, player_id, season
            )

            if game_record and self.save_game_log(db, game_record):
                saved += 1

        self.games_collected += saved
        self.players_processed += 1

        if saved > 0:
            logger.info(f"  {player_name}: {saved} games")

        return saved


async def main():
    """Main collection function."""
    parser = argparse.ArgumentParser(
        description="Collect data for ALL MiLB players in 2024"
    )
    parser.add_argument(
        '--season',
        type=int,
        default=2024,
        help='Season to collect (default: 2024)'
    )
    parser.add_argument(
        '--levels',
        nargs='+',
        default=['AAA', 'AA', 'A+'],
        help='MiLB levels to include (default: AAA AA A+)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of players (for testing)'
    )

    args = parser.parse_args()

    # Map levels to sport IDs
    level_map = {v: k for k, v in AllMiLBPlayerCollector.MILB_SPORT_IDS.items()}
    sport_ids = [level_map[level] for level in args.levels if level in level_map]

    logger.info("Starting ALL MiLB player collection")
    logger.info(f"Season: {args.season}")
    logger.info(f"Levels: {args.levels}")

    db = get_db_sync()

    try:
        async with AllMiLBPlayerCollector() as collector:
            # Discover all players
            players = await collector.discover_all_players(sport_ids, args.season)

            if args.limit:
                players = players[:args.limit]

            logger.info(f"\nProcessing {len(players)} players...")

            start_time = time.time()

            # Process each player
            for i, player in enumerate(players, 1):
                if i % 50 == 0:
                    logger.info(f"\nProgress: {i}/{len(players)} players processed")
                    logger.info(f"Games collected: {collector.games_collected}")

                # Save player
                collector.save_player_to_db(db, player)

                # Collect games
                await collector.collect_player_data(db, player, args.season, sport_ids)

            # Summary
            elapsed = time.time() - start_time
            logger.info("\n" + "="*60)
            logger.info("Collection complete!")
            logger.info(f"Players processed: {collector.players_processed}")
            logger.info(f"Games collected: {collector.games_collected}")
            logger.info(f"Time elapsed: {elapsed/60:.1f} minutes")
            logger.info("="*60)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
