#!/usr/bin/env python3
"""
Collect MiLB plate appearance data for prospects missing PA data.

This script:
1. Finds prospects with game logs but missing PA data
2. Collects PA summaries from MLB Stats API game feeds
3. Saves data to milb_plate_appearances table
4. Runs for all seasons 2021-2025
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

import aiohttp
from sqlalchemy import text

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

class ProspectPACollector:
    """Collect plate appearance data for prospects."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"
    MILB_SPORT_IDS = {
        11: "AAA",
        12: "AA",
        13: "A+",
        14: "A",
        15: "A-",
        16: "Rookie",
        21: "Complex/DSL"
    }

    def __init__(self, season: int, limit: Optional[int] = None):
        self.season = season
        self.limit = limit
        self.session: Optional[aiohttp.ClientSession] = None
        self.collected_pas = 0
        self.errors = 0

    async def __aenter__(self):
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
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str) -> Optional[Dict]:
        """Fetch JSON from URL with error handling."""
        try:
            await asyncio.sleep(0.3)  # Rate limiting
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            self.errors += 1
            return None

    def get_prospects_needing_pas(self, db, season: int) -> List[Dict]:
        """Get prospects who played in this season but have no PA data."""
        query = text("""
            SELECT DISTINCT
                CAST(p.mlb_player_id AS INTEGER) as mlb_player_id,
                p.name,
                p.position,
                p.organization,
                COUNT(g.game_pk) as game_count
            FROM prospects p
            INNER JOIN milb_game_logs g ON g.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE g.season = :season
            AND p.mlb_player_id IS NOT NULL
            AND p.mlb_player_id != ''
            AND NOT EXISTS (
                SELECT 1
                FROM milb_plate_appearances pa
                WHERE pa.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                AND pa.season = :season
            )
            GROUP BY p.mlb_player_id, p.name, p.position, p.organization
            HAVING COUNT(g.game_pk) > 10
            ORDER BY COUNT(g.game_pk) DESC
            LIMIT :limit
        """)

        result = db.execute(query, {"season": season, "limit": self.limit or 10000})

        prospects = []
        for row in result:
            prospects.append({
                "mlb_player_id": row.mlb_player_id,
                "name": row.name or f"Player {row.mlb_player_id}",
                "position": row.position,
                "organization": row.organization,
                "game_count": row.game_count
            })

        return prospects

    async def find_player_games(self, player_id: int) -> List[Dict]:
        """Find all games for player in season (same as pitch collection)."""
        all_games = {}

        for sport_id, level_name in self.MILB_SPORT_IDS.items():
            url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={self.season}&group=hitting,pitching&sportId={sport_id}"
            data = await self.fetch_json(url)

            if not data:
                continue

            # Validate data structure
            if not isinstance(data, dict):
                continue

            try:
                stats = data.get('stats', [])
                if not stats:
                    continue

                for stat_group in stats:
                    if not isinstance(stat_group, dict):
                        continue

                    splits = stat_group.get('splits', [])
                    if not splits:
                        continue

                    for split in splits:
                        if not isinstance(split, dict):
                            continue

                        game = split.get('game', {})
                        if not isinstance(game, dict):
                            continue

                        game_pk = game.get('gamePk')
                        game_date = split.get('date')

                        if game_pk and game_date:
                            all_games[game_pk] = {
                                'game_pk': game_pk,
                                'game_date': game_date,
                                'level': level_name
                            }
            except Exception as e:
                # Only log at debug level to reduce noise
                logger.debug(f"Error parsing games for player {player_id} sport {sport_id}: {e}")
                continue

        return list(all_games.values())

    async def fetch_game_pbp(self, game_pk: int) -> Optional[Dict]:
        """Fetch game play-by-play data.

        For MiLB games, playByPlay endpoint is more reliable than feed/live.
        """
        # Try playByPlay first (works for MiLB)
        url = f"{self.BASE_URL}/game/{game_pk}/playByPlay"
        data = await self.fetch_json(url)

        if data:
            return data

        # Fallback to feed/live
        url = f"{self.BASE_URL}/game/{game_pk}/feed/live"
        return await self.fetch_json(url)

    async def collect_game_pas(self, game_info: Dict, player_id: int, db) -> int:
        """Collect plate appearances for a player from a specific game."""
        game_pk = game_info['game_pk']
        game_date = game_info['game_date']
        level = game_info['level']

        pbp_data = await self.fetch_game_pbp(game_pk)
        if not pbp_data:
            return 0

        # Get plays (same logic as pitch collection)
        if 'liveData' in pbp_data:
            all_plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
        else:
            all_plays = pbp_data.get('allPlays', [])

        if not all_plays:
            return 0

        pas_saved = 0

        try:
            for play in all_plays:
                matchup = play.get('matchup', {})
                batter_id = matchup.get('batter', {}).get('id')

                # Only save if this player was the batter
                if batter_id != player_id:
                    continue

                result = play.get('result', {})
                about = play.get('about', {})

                # Extract PA data (matching actual table schema)
                pa_data = {
                    'mlb_player_id': player_id,
                    'season': self.season,
                    'game_pk': game_pk,
                    'game_date': datetime.strptime(game_date, '%Y-%m-%d').date(),
                    'level': level,
                    'inning': about.get('inning'),
                    'half_inning': about.get('halfInning'),
                    'at_bat_index': about.get('atBatIndex'),
                    'event_type': result.get('event'),
                    'event_type_desc': result.get('eventType'),
                    'description': result.get('description')
                }

                # Insert into database
                insert_query = text("""
                    INSERT INTO milb_plate_appearances (
                        mlb_player_id, season, game_pk, game_date, level,
                        inning, half_inning, at_bat_index, event_type, event_type_desc,
                        description, created_at
                    ) VALUES (
                        :mlb_player_id, :season, :game_pk, :game_date, :level,
                        :inning, :half_inning, :at_bat_index, :event_type, :event_type_desc,
                        :description, NOW()
                    )
                    ON CONFLICT (mlb_player_id, game_pk, at_bat_index) DO NOTHING
                """)

                db.execute(insert_query, pa_data)
                pas_saved += 1

            if pas_saved > 0:
                db.commit()

        except Exception as e:
            logger.error(f"Error collecting PAs from game {game_pk}: {e}")
            db.rollback()

        return pas_saved

    async def collect_player_pas(self, prospect: Dict, db) -> int:
        """Collect all PAs for a prospect."""
        player_id = prospect['mlb_player_id']
        name = prospect['name']

        # Find games using same method as pitch collection
        games = await self.find_player_games(player_id)

        if not games:
            logger.info(f"    No games found")
            return 0

        logger.info(f"    Found {len(games)} games")

        total_pas = 0
        for i, game_info in enumerate(games, 1):
            if i % 20 == 0:
                logger.info(f"      Progress: {i}/{len(games)} games")

            pas = await self.collect_game_pas(game_info, player_id, db)
            total_pas += pas

        logger.info(f"    Collected {total_pas} PAs")
        return total_pas

    async def run(self):
        """Run the collection process."""
        logger.info("="*70)
        logger.info(f"PROSPECT PA COLLECTION - {self.season}")
        logger.info("="*70)

        # Get database connection
        db = get_db_sync()

        try:
            # Get prospects needing data
            prospects = self.get_prospects_needing_pas(db, self.season)

            if not prospects:
                logger.info(f"No prospects need PA data for {self.season}")
                return

            logger.info(f"Found {len(prospects)} prospects needing {self.season} PA data")
            logger.info("")

            for i, prospect in enumerate(prospects, 1):
                logger.info(f"[{i}/{len(prospects)}] {prospect['name']} ({prospect['organization']})")

                try:
                    pas = await self.collect_player_pas(prospect, db)
                    self.collected_pas += pas
                except Exception as e:
                    logger.error(f"  ERROR: {e}")
                    self.errors += 1

                if i % 10 == 0:
                    logger.info("")
                    logger.info(f"Progress: {i}/{len(prospects)} prospects")
                    logger.info(f"PAs collected: {self.collected_pas:,}")
                    logger.info(f"Errors: {self.errors}")
                    logger.info("")

        finally:
            db.close()

        logger.info("")
        logger.info("="*70)
        logger.info("COLLECTION COMPLETE")
        logger.info(f"Total PAs collected: {self.collected_pas}")
        logger.info(f"Errors: {self.errors}")
        logger.info("="*70)


async def main():
    parser = argparse.ArgumentParser(description='Collect PA data for prospects')
    parser.add_argument('--season', type=int, required=True, help='Season to collect (2021-2025)')
    parser.add_argument('--limit', type=int, help='Limit number of prospects')
    args = parser.parse_args()

    async with ProspectPACollector(args.season, args.limit) as collector:
        await collector.run()


if __name__ == "__main__":
    asyncio.run(main())
