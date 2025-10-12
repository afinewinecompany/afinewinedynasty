"""
Collect MiLB stats for specific players with proper prospect linking

This script specifically collects data for players who were missed
by the main collection script.
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from sqlalchemy import text

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Critical missing players
TARGET_PLAYERS = {
    800050: 'Chase DeLauter',
    701398: 'Sal Stewart',
    683953: 'Travis Bazzana',
    703601: 'Max Clark',
    802419: 'JJ Wetherholt',
    806968: 'Braden Montgomery',
    805805: 'Walker Jenkins',
    691620: 'Jeferson Quero',
}

def safe_float(value) -> Optional[float]:
    """Safely convert value to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value in ('.---', '-.--', '∞', 'Infinity', ''):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


class SpecificPlayerCollector:
    """Collect MiLB game logs for specific players."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    MILB_SPORT_IDS = {
        11: "AAA",
        12: "AA",
        13: "A+",
        14: "A",
        15: "Rookie",
        16: "Rookie+"
    }

    def __init__(self, season: int):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.season = season
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
        """Fetch JSON data from URL."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    await asyncio.sleep(self.request_delay)
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_or_create_prospect(self, mlb_player_id: int, player_name: str) -> Optional[int]:
        """Get or create prospect record and return prospect_id."""
        async with engine.begin() as conn:
            # First try to find existing prospect by MLB ID
            result = await conn.execute(text("""
                SELECT id FROM prospects
                WHERE mlb_id = :mlb_id
                LIMIT 1
            """), {'mlb_id': str(mlb_player_id)})

            row = result.fetchone()
            if row:
                return row[0]

            # Try to find by name
            result = await conn.execute(text("""
                SELECT id FROM prospects
                WHERE name = :name
                LIMIT 1
            """), {'name': player_name})

            row = result.fetchone()
            if row:
                # Update with MLB ID
                await conn.execute(text("""
                    UPDATE prospects
                    SET mlb_id = :mlb_id
                    WHERE id = :id
                """), {'mlb_id': str(mlb_player_id), 'id': row[0]})
                return row[0]

            # Create new prospect
            result = await conn.execute(text("""
                INSERT INTO prospects (mlb_id, name, created_at, updated_at)
                VALUES (:mlb_id, :name, NOW(), NOW())
                RETURNING id
            """), {'mlb_id': str(mlb_player_id), 'name': player_name})

            return result.fetchone()[0]

    async def collect_player(self, mlb_player_id: int, player_name: str):
        """Collect all data for a specific player."""
        logger.info(f"Collecting {player_name} ({mlb_player_id}) for {self.season}...")

        # Get or create prospect record
        prospect_id = await self.get_or_create_prospect(mlb_player_id, player_name)
        if not prospect_id:
            logger.error(f"Failed to get/create prospect record for {player_name}")
            return

        logger.info(f"  Using prospect_id: {prospect_id}")

        # Check if we already have data
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT COUNT(*)
                FROM milb_game_logs
                WHERE prospect_id = :prospect_id
                AND season = :season
            """), {'prospect_id': prospect_id, 'season': self.season})

            existing_count = result.scalar()
            if existing_count > 0:
                logger.info(f"  Already have {existing_count} games for {self.season}, checking for updates...")

        # Collect for each MiLB level
        total_games = 0
        for sport_id, level in self.MILB_SPORT_IDS.items():
            # Get hitting stats
            url = f"{self.BASE_URL}/people/{mlb_player_id}/stats?stats=gameLog&season={self.season}&group=hitting&sportId={sport_id}"
            data = await self.fetch_json(url)

            if data and data.get('stats'):
                stats = data['stats'][0].get('splits', [])
                if stats:
                    logger.info(f"  Found {len(stats)} games at {level} level")

                    for game_log in stats:
                        await self.save_game_log(prospect_id, mlb_player_id, game_log, level)
                        total_games += 1

        self.games_collected += total_games
        self.players_processed += 1
        logger.info(f"  Total: {total_games} games collected for {self.season}")

    async def save_game_log(self, prospect_id: int, mlb_player_id: int, game_log: Dict[str, Any], level: str):
        """Save game log to database with proper prospect_id."""
        try:
            stat = game_log.get('stat', {})
            game = game_log.get('game', {})
            team = game_log.get('team', {})
            opponent = game_log.get('opponent', {})

            # Parse date
            date_str = game_log.get('date')
            game_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

            record = {
                'prospect_id': prospect_id,  # PROPERLY LINKED!
                'mlb_player_id': mlb_player_id,
                'season': self.season,
                'game_pk': game.get('gamePk'),
                'game_date': game_date,
                'level': level,
                'game_type': 'Regular',
                'team': team.get('name'),
                'opponent': opponent.get('name'),
                'is_home': game_log.get('isHome', False),
                # Hitting stats
                'games_played': 1,
                'plate_appearances': stat.get('plateAppearances', 0),
                'at_bats': stat.get('atBats', 0),
                'runs': stat.get('runs', 0),
                'hits': stat.get('hits', 0),
                'doubles': stat.get('doubles', 0),
                'triples': stat.get('triples', 0),
                'home_runs': stat.get('homeRuns', 0),
                'rbi': stat.get('rbi', 0),
                'walks': stat.get('baseOnBalls', 0),
                'intentional_walks': stat.get('intentionalWalks', 0),
                'strikeouts': stat.get('strikeOuts', 0),
                'stolen_bases': stat.get('stolenBases', 0),
                'caught_stealing': stat.get('caughtStealing', 0),
                'hit_by_pitch': stat.get('hitByPitch', 0),
                'sacrifice_flies': stat.get('sacFlies', 0),
                'ground_outs': stat.get('groundOuts', 0),
                'fly_outs': stat.get('flyOuts', 0),
                'left_on_base': stat.get('leftOnBase', 0),
            }

            async with engine.begin() as conn:
                # Check if record exists
                result = await conn.execute(text("""
                    SELECT id FROM milb_game_logs
                    WHERE prospect_id = :prospect_id
                    AND game_date = :game_date
                    AND level = :level
                    LIMIT 1
                """), {
                    'prospect_id': record['prospect_id'],
                    'game_date': record['game_date'],
                    'level': record['level']
                })

                if result.fetchone():
                    # Skip duplicate
                    return

                # Insert new record
                await conn.execute(text("""
                    INSERT INTO milb_game_logs (
                        prospect_id, mlb_player_id, season, game_date, level,
                        team, opponent, is_home, games_played,
                        plate_appearances, at_bats, runs, hits, doubles, triples,
                        home_runs, rbi, walks, intentional_walks, strikeouts,
                        stolen_bases, caught_stealing, hit_by_pitch,
                        sacrifice_flies, ground_outs, fly_outs, left_on_base
                    ) VALUES (
                        :prospect_id, :mlb_player_id, :season, :game_date, :level,
                        :team, :opponent, :is_home, :games_played,
                        :plate_appearances, :at_bats, :runs, :hits, :doubles, :triples,
                        :home_runs, :rbi, :walks, :intentional_walks, :strikeouts,
                        :stolen_bases, :caught_stealing, :hit_by_pitch,
                        :sacrifice_flies, :ground_outs, :fly_outs, :left_on_base
                    )
                """), record)

        except Exception as e:
            logger.error(f"Error saving game log: {e}")


async def main(season: int, player_ids: List[int] = None):
    """Main collection function."""
    if player_ids is None:
        player_ids = list(TARGET_PLAYERS.keys())

    logger.info(f"Starting collection for {len(player_ids)} players in {season}")
    logger.info("=" * 80)

    async with SpecificPlayerCollector(season) as collector:
        for player_id in player_ids:
            player_name = TARGET_PLAYERS.get(player_id, f"Player {player_id}")
            await collector.collect_player(player_id, player_name)

        logger.info("=" * 80)
        logger.info(f"Collection complete!")
        logger.info(f"Players processed: {collector.players_processed}")
        logger.info(f"Total games collected: {collector.games_collected}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--season', type=int, required=True)
    parser.add_argument('--players', nargs='+', type=int, help='Specific player IDs')
    args = parser.parse_args()

    asyncio.run(main(args.season, args.players))