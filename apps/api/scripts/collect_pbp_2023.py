"""
Collect MiLB play-by-play data for 2023 season.
Simplified version with correct database connection.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import text

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

# Make sure we're loading the env from the right place
os.chdir(api_dir)

from app.db.database import sync_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MiLBPBPCollector2023:
    """Collect MiLB pitch-by-pitch data for 2023 season."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # MiLB sport IDs
    MILB_SPORT_IDS = {
        11: "AAA",      # Triple-A
        12: "AA",       # Double-A
        13: "A+",       # High-A
        14: "A",        # Single-A
        15: "Rookie",   # Rookie
        16: "Rookie+",  # Rookie Advanced
        21: "Complex"   # Arizona/Florida Complex League
    }

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.3  # Be respectful to the API
        self.games_collected = 0
        self.errors = 0
        self.players_processed = 0

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
        """Fetch JSON data from URL with rate limiting."""
        try:
            await asyncio.sleep(self.request_delay)

            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None
                else:
                    logger.debug(f"HTTP {response.status} for {url}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            self.errors += 1
            return None

    def get_players_needing_pbp(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get players who have 2023 game logs but no PBP data."""
        with sync_engine.connect() as conn:
            query = text("""
                WITH player_game_counts AS (
                    SELECT
                        mlb_player_id,
                        COUNT(*) as game_count
                    FROM milb_game_logs
                    WHERE season = 2023
                    AND mlb_player_id IS NOT NULL
                    GROUP BY mlb_player_id
                ),
                player_pbp_counts AS (
                    SELECT
                        mlb_player_id,
                        COUNT(*) as pbp_count
                    FROM milb_plate_appearances
                    WHERE season = 2023
                    GROUP BY mlb_player_id
                )
                SELECT
                    pgc.mlb_player_id,
                    pgc.game_count,
                    COALESCE(ppc.pbp_count, 0) as pbp_count,
                    p.name,
                    p.position,
                    p.organization
                FROM player_game_counts pgc
                LEFT JOIN player_pbp_counts ppc ON pgc.mlb_player_id = ppc.mlb_player_id
                LEFT JOIN prospects p ON pgc.mlb_player_id::text = p.mlb_player_id
                WHERE COALESCE(ppc.pbp_count, 0) = 0
                ORDER BY pgc.game_count DESC
                LIMIT :limit
            """)

            result = conn.execute(query, {"limit": limit or 10000})

            players = []
            for row in result:
                players.append({
                    "mlb_player_id": row.mlb_player_id,
                    "game_count": row.game_count,
                    "pbp_count": row.pbp_count,
                    "name": row.name or f"Player {row.mlb_player_id}",
                    "position": row.position,
                    "organization": row.organization
                })

            return players

    async def find_player_games_2023(self, player_id: int) -> List[Dict[str, Any]]:
        """Find all 2023 games for a player across all MiLB levels."""
        all_games = {}  # Use dict to dedupe by game_pk

        # Query each MiLB sport level
        for sport_id, level_name in self.MILB_SPORT_IDS.items():
            url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season=2023&group=hitting,pitching&sportId={sport_id}"

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
                                'level': level_name
                            }

            except Exception as e:
                logger.error(f"Error parsing games for sportId {sport_id}: {str(e)}")
                continue

        games = list(all_games.values())
        return games

    async def fetch_play_by_play(self, game_pk: int) -> Optional[Dict[str, Any]]:
        """Fetch detailed play-by-play data for a game."""
        # Try the newer feed/live endpoint first (has more data)
        url = f"{self.BASE_URL}.1/game/{game_pk}/feed/live"
        data = await self.fetch_json(url)

        if data:
            return data

        # Fallback to basic playByPlay endpoint
        url = f"{self.BASE_URL}/game/{game_pk}/playByPlay"
        return await self.fetch_json(url)

    def extract_and_save_pbp_data(
        self,
        pbp_data: Dict[str, Any],
        game_pk: int,
        game_date_str: str,
        level: str,
        player_id: int
    ) -> int:
        """Extract player's plate appearances and save to database."""
        try:
            game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()

            # Get plays from appropriate structure
            if 'liveData' in pbp_data:
                # feed/live format
                all_plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
            else:
                # playByPlay format
                all_plays = pbp_data.get('allPlays', [])

            if not all_plays:
                return 0

            pas_saved = 0

            with sync_engine.begin() as conn:
                for play_idx, play in enumerate(all_plays):
                    matchup = play.get('matchup', {})
                    batter_id = matchup.get('batter', {}).get('id')

                    # Check if this PA involves our player
                    if batter_id != player_id:
                        continue

                    # Extract play result
                    result = play.get('result', {})
                    event_type = result.get('event', '')
                    event_type_desc = result.get('eventType', '')
                    description = result.get('description', '')

                    # Extract inning info
                    about = play.get('about', {})
                    inning = about.get('inning')
                    half_inning = about.get('halfInning', '')

                    # Look for batted ball data in play events
                    play_events = play.get('playEvents', [])
                    batted_ball_data = {}

                    for event in play_events:
                        hit_data = event.get('hitData', {})
                        if hit_data:
                            batted_ball_data = {
                                'launch_speed': hit_data.get('launchSpeed'),
                                'launch_angle': hit_data.get('launchAngle'),
                                'total_distance': hit_data.get('totalDistance'),
                                'trajectory': hit_data.get('trajectory'),
                                'hardness': hit_data.get('hardness'),
                                'location': hit_data.get('location'),
                                'coord_x': hit_data.get('coordinates', {}).get('coordX'),
                                'coord_y': hit_data.get('coordinates', {}).get('coordY')
                            }
                            break

                    # Check if this PA already exists
                    check_query = text("""
                        SELECT id FROM milb_plate_appearances
                        WHERE mlb_player_id = :player_id
                        AND game_pk = :game_pk
                        AND at_bat_index = :at_bat_index
                    """)

                    existing = conn.execute(check_query, {
                        'player_id': player_id,
                        'game_pk': game_pk,
                        'at_bat_index': play.get('atBatIndex', play_idx)
                    }).fetchone()

                    if existing:
                        continue

                    # Insert new PA
                    insert_query = text("""
                        INSERT INTO milb_plate_appearances
                        (mlb_player_id, game_pk, game_date, season, level, at_bat_index,
                         inning, half_inning, event_type, event_type_desc, description,
                         launch_speed, launch_angle, total_distance, trajectory, hardness,
                         location, coord_x, coord_y, created_at)
                        VALUES
                        (:player_id, :game_pk, :game_date, 2023, :level, :at_bat_index,
                         :inning, :half_inning, :event_type, :event_type_desc, :description,
                         :launch_speed, :launch_angle, :total_distance, :trajectory, :hardness,
                         :location, :coord_x, :coord_y, NOW())
                    """)

                    conn.execute(insert_query, {
                        'player_id': player_id,
                        'game_pk': game_pk,
                        'game_date': game_date,
                        'level': level,
                        'at_bat_index': play.get('atBatIndex', play_idx),
                        'inning': inning,
                        'half_inning': half_inning,
                        'event_type': event_type,
                        'event_type_desc': event_type_desc,
                        'description': description,
                        'launch_speed': batted_ball_data.get('launch_speed'),
                        'launch_angle': batted_ball_data.get('launch_angle'),
                        'total_distance': batted_ball_data.get('total_distance'),
                        'trajectory': batted_ball_data.get('trajectory'),
                        'hardness': batted_ball_data.get('hardness'),
                        'location': batted_ball_data.get('location'),
                        'coord_x': batted_ball_data.get('coord_x'),
                        'coord_y': batted_ball_data.get('coord_y')
                    })

                    pas_saved += 1

            return pas_saved

        except Exception as e:
            logger.error(f"Error saving PBP data for game {game_pk}: {str(e)}")
            return 0

    async def collect_player_pbp(self, player: Dict[str, Any]) -> int:
        """Collect all 2023 PBP data for a single player."""
        player_id = player['mlb_player_id']
        name = player['name']

        logger.info(f"  Processing {name} (ID: {player_id}) - {player['game_count']} games to process")

        # Find all 2023 games
        games = await self.find_player_games_2023(player_id)

        if not games:
            logger.info(f"    No 2023 games found via API")
            return 0

        logger.info(f"    Found {len(games)} games in 2023")

        total_pas = 0
        games_with_data = 0

        # Process each game
        for i, game_info in enumerate(games, 1):
            if i % 20 == 0:
                logger.info(f"      Progress: {i}/{len(games)} games, {total_pas} PAs collected")

            game_pk = game_info['game_pk']
            game_date = game_info['game_date']
            level = game_info['level']

            # Fetch PBP data
            pbp_data = await self.fetch_play_by_play(game_pk)
            if not pbp_data:
                continue

            # Extract and save PAs
            pas_saved = self.extract_and_save_pbp_data(
                pbp_data, game_pk, game_date, level, player_id
            )

            if pas_saved > 0:
                total_pas += pas_saved
                games_with_data += 1
                self.games_collected += 1

        logger.info(f"    Completed: {total_pas} PAs from {games_with_data} games")
        return total_pas

    async def ensure_table_exists(self):
        """Ensure the milb_plate_appearances table exists."""
        with sync_engine.begin() as conn:
            # Check if table exists
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name = 'milb_plate_appearances'
            """))

            if result.fetchone()[0] == 0:
                logger.info("Creating milb_plate_appearances table...")

                conn.execute(text("""
                    CREATE TABLE milb_plate_appearances (
                        id SERIAL PRIMARY KEY,
                        mlb_player_id INTEGER NOT NULL,
                        game_pk BIGINT NOT NULL,
                        game_date DATE,
                        season INTEGER,
                        level VARCHAR(20),
                        at_bat_index INTEGER,
                        inning INTEGER,
                        half_inning VARCHAR(10),
                        event_type VARCHAR(50),
                        event_type_desc VARCHAR(50),
                        description TEXT,
                        launch_speed FLOAT,
                        launch_angle FLOAT,
                        total_distance FLOAT,
                        trajectory VARCHAR(20),
                        hardness VARCHAR(20),
                        location INTEGER,
                        coord_x FLOAT,
                        coord_y FLOAT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        UNIQUE(mlb_player_id, game_pk, at_bat_index)
                    )
                """))

                # Create indexes
                conn.execute(text("""
                    CREATE INDEX idx_milb_pa_player
                    ON milb_plate_appearances(mlb_player_id)
                """))

                conn.execute(text("""
                    CREATE INDEX idx_milb_pa_season
                    ON milb_plate_appearances(season)
                """))

                conn.execute(text("""
                    CREATE INDEX idx_milb_pa_launch
                    ON milb_plate_appearances(launch_speed, launch_angle)
                    WHERE launch_speed IS NOT NULL
                """))

                logger.info("Table created successfully")


async def main():
    """Main collection function."""
    parser = argparse.ArgumentParser(
        description="Collect MiLB play-by-play data for 2023 season"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Number of players to process (default: 10)'
    )
    parser.add_argument(
        '--offset',
        type=int,
        default=0,
        help='Skip first N players (for resuming)'
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("MiLB Play-by-Play Collection for 2023 Season")
    logger.info("="*80)

    try:
        async with MiLBPBPCollector2023() as collector:
            # Ensure table exists
            await collector.ensure_table_exists()

            # Get players needing PBP data
            players = collector.get_players_needing_pbp(args.limit + args.offset)

            if args.offset:
                players = players[args.offset:]
                logger.info(f"Skipping first {args.offset} players")

            players = players[:args.limit]

            logger.info(f"Found {len(players)} players needing PBP data for 2023")
            logger.info("")

            if not players:
                logger.warning("No players found needing PBP collection")
                return

            # Process each player
            start_time = time.time()
            total_pas_collected = 0

            for i, player in enumerate(players, 1):
                logger.info(f"[{i}/{len(players)}] {player['name']} ({player['organization']})")

                try:
                    pas_collected = await collector.collect_player_pbp(player)
                    total_pas_collected += pas_collected
                    collector.players_processed += 1

                except Exception as e:
                    logger.error(f"  Error processing {player['name']}: {str(e)}")
                    collector.errors += 1
                    continue

                # Progress update every 5 players
                if i % 5 == 0:
                    elapsed = time.time() - start_time
                    rate = collector.players_processed / elapsed if elapsed > 0 else 0
                    logger.info("")
                    logger.info(f"=== Progress Update ===")
                    logger.info(f"Players processed: {collector.players_processed}")
                    logger.info(f"Total PAs collected: {total_pas_collected}")
                    logger.info(f"Games processed: {collector.games_collected}")
                    logger.info(f"Processing rate: {rate:.2f} players/sec")
                    logger.info(f"Errors: {collector.errors}")
                    logger.info("")

            # Final summary
            elapsed = time.time() - start_time
            logger.info("")
            logger.info("="*80)
            logger.info("Collection Complete!")
            logger.info("="*80)
            logger.info(f"Players processed: {collector.players_processed}")
            logger.info(f"Total PAs collected: {total_pas_collected}")
            logger.info(f"Games processed: {collector.games_collected}")
            logger.info(f"Errors: {collector.errors}")
            logger.info(f"Time elapsed: {elapsed:.1f}s")

            if collector.players_processed > 0:
                logger.info(f"Average PAs/player: {total_pas_collected/collector.players_processed:.1f}")
                logger.info(f"Average time/player: {elapsed/collector.players_processed:.1f}s")

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())