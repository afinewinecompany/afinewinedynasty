"""
Collect MLB Game Logs for Players with MiLB Data

This script:
1. Gets all unique MLB player IDs from milb_game_logs
2. Fetches MLB game-by-game stats using gameLog API
3. Stores granular MLB performance data for ML analysis

This provides the "Y" (outcome) data for supervised learning where
MiLB stats are "X" (features) predicting MLB performance.

Usage:
    python collect_mlb_gamelogs.py --seasons 2024 2023 2022
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


class MLBGameLogCollector:
    """Collect MLB game logs for players with MiLB data."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"
    MLB_SPORT_ID = 1  # MLB = sport ID 1

    def __init__(self, seasons: List[int]):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.seasons = seasons
        self.games_collected = 0
        self.players_processed = 0
        self.players_with_mlb_data = 0

    async def create_session(self):
        """Create aiohttp session."""
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from URL with error handling."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_mlb_player_ids(self) -> List[int]:
        """Get unique MLB player IDs from milb_game_logs."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT DISTINCT mlb_player_id, COUNT(*) as milb_games
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
                ORDER BY milb_games DESC
            """))

            players = [(row[0], row[1]) for row in result.fetchall()]
            logger.info(f"Found {len(players)} unique MiLB players to check for MLB data")
            return players

    async def get_player_game_logs(self, player_id: int, season: int) -> List[Dict[str, Any]]:
        """Get MLB game logs for a player in a specific season."""
        url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={season}&group=hitting&sportId={self.MLB_SPORT_ID}"

        data = await self.fetch_json(url)
        if not data:
            return []

        stats = data.get('stats', [])
        if not stats:
            return []

        return stats[0].get('splits', [])

    async def save_game_log(self, player_id: int, game_log: Dict[str, Any], season: int):
        """Save a single MLB game log to database."""
        try:
            stat = game_log.get('stat', {})
            game = game_log.get('game', {})
            team = game_log.get('team', {})
            opponent = game_log.get('opponent', {})

            # Parse game date - it's at top level of game_log, not in 'game' object
            game_date_str = game_log.get('date')
            if not game_date_str:
                print(f"WARNING: No date for player {player_id}, skipping game")
                return

            game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()

            record = {
                'mlb_player_id': player_id,
                'season': season,
                'game_pk': game.get('gamePk'),
                'game_date': game_date,
                'game_type': 'Regular',  # Could be R, P, S, etc. - normalize to full names
                'team_id': team.get('id'),
                'opponent_id': opponent.get('id'),
                'is_home': game.get('isHome', False),
                'is_win': game.get('isWin', False),

                # Batting stats
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
                'sacrifice_hits': stat.get('sacBunts', 0),
                'ground_outs': stat.get('groundOuts', 0),
                'fly_outs': stat.get('flyOuts', 0),
                'grounded_into_double_play': stat.get('groundIntoDoublePlay', 0),

                # Advanced stats
                'total_bases': stat.get('totalBases', 0),
                'left_on_base': stat.get('leftOnBase', 0),

                # Rate stats (from API)
                'batting_avg': float(stat.get('avg', 0)) if stat.get('avg') else None,
                'on_base_pct': float(stat.get('obp', 0)) if stat.get('obp') else None,
                'slugging_pct': float(stat.get('slg', 0)) if stat.get('slg') else None,
                'ops': float(stat.get('ops', 0)) if stat.get('ops') else None,

                'data_source': 'mlb_stats_api_gamelog'
            }

            async with engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO mlb_game_logs (
                        mlb_player_id, season, game_pk, game_date, game_type,
                        team_id, opponent_id, is_home, is_win,
                        games_played, plate_appearances, at_bats, runs, hits,
                        doubles, triples, home_runs, rbi, walks, intentional_walks,
                        strikeouts, stolen_bases, caught_stealing, hit_by_pitch,
                        sacrifice_flies, sacrifice_hits, ground_outs, fly_outs,
                        grounded_into_double_play, total_bases, left_on_base,
                        batting_avg, on_base_pct, slugging_pct, ops, data_source
                    ) VALUES (
                        :mlb_player_id, :season, :game_pk, :game_date, :game_type,
                        :team_id, :opponent_id, :is_home, :is_win,
                        :games_played, :plate_appearances, :at_bats, :runs, :hits,
                        :doubles, :triples, :home_runs, :rbi, :walks, :intentional_walks,
                        :strikeouts, :stolen_bases, :caught_stealing, :hit_by_pitch,
                        :sacrifice_flies, :sacrifice_hits, :ground_outs, :fly_outs,
                        :grounded_into_double_play, :total_bases, :left_on_base,
                        :batting_avg, :on_base_pct, :slugging_pct, :ops, :data_source
                    )
                    ON CONFLICT (game_pk, mlb_player_id) DO NOTHING
                """), record)

                self.games_collected += 1

        except Exception as e:
            print(f"ERROR saving game for player {player_id}: {e}")
            import traceback
            traceback.print_exc()

    async def process_player(self, player_id: int, milb_games: int):
        """Process a single player - fetch all MLB game logs."""
        self.players_processed += 1

        player_total_games = 0

        # Process each season
        for season in self.seasons:
            game_logs = await self.get_player_game_logs(player_id, season)

            for game_log in game_logs:
                await self.save_game_log(player_id, game_log, season)
                player_total_games += 1

        if player_total_games > 0:
            self.players_with_mlb_data += 1
            logger.info(f"  [{self.players_processed}] Player {player_id}: {player_total_games} MLB games "
                       f"({milb_games} MiLB games)")

        if self.players_processed % 50 == 0:
            logger.info(f"Progress: {self.players_processed} players processed, "
                       f"{self.players_with_mlb_data} with MLB data, "
                       f"{self.games_collected} games collected")

    async def create_table(self):
        """Create mlb_game_logs table if it doesn't exist."""
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS mlb_game_logs (
                    id SERIAL PRIMARY KEY,
                    mlb_player_id INTEGER NOT NULL,
                    season INTEGER NOT NULL,
                    game_pk INTEGER NOT NULL,
                    game_date DATE NOT NULL,
                    game_type VARCHAR(20),
                    team_id INTEGER,
                    opponent_id INTEGER,
                    is_home BOOLEAN,
                    is_win BOOLEAN,

                    -- Batting stats
                    games_played INTEGER DEFAULT 1,
                    plate_appearances INTEGER DEFAULT 0,
                    at_bats INTEGER DEFAULT 0,
                    runs INTEGER DEFAULT 0,
                    hits INTEGER DEFAULT 0,
                    doubles INTEGER DEFAULT 0,
                    triples INTEGER DEFAULT 0,
                    home_runs INTEGER DEFAULT 0,
                    rbi INTEGER DEFAULT 0,
                    walks INTEGER DEFAULT 0,
                    intentional_walks INTEGER DEFAULT 0,
                    strikeouts INTEGER DEFAULT 0,
                    stolen_bases INTEGER DEFAULT 0,
                    caught_stealing INTEGER DEFAULT 0,
                    hit_by_pitch INTEGER DEFAULT 0,
                    sacrifice_flies INTEGER DEFAULT 0,
                    sacrifice_hits INTEGER DEFAULT 0,
                    ground_outs INTEGER DEFAULT 0,
                    fly_outs INTEGER DEFAULT 0,
                    grounded_into_double_play INTEGER DEFAULT 0,
                    total_bases INTEGER DEFAULT 0,
                    left_on_base INTEGER DEFAULT 0,

                    -- Rate stats
                    batting_avg DECIMAL(5,3),
                    on_base_pct DECIMAL(5,3),
                    slugging_pct DECIMAL(5,3),
                    ops DECIMAL(5,3),

                    -- Metadata
                    data_source VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    -- Constraints
                    UNIQUE(game_pk, mlb_player_id)
                )
            """))

            # Create indexes
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_logs_player
                ON mlb_game_logs(mlb_player_id)
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_logs_season
                ON mlb_game_logs(season)
            """))

            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mlb_logs_date
                ON mlb_game_logs(game_date)
            """))

            logger.info("MLB game logs table ready")

    async def collect_all_mlb_games(self):
        """Main collection loop."""
        logger.info("="*80)
        logger.info("MLB Game Log Collection")
        logger.info(f"Seasons: {', '.join(map(str, self.seasons))}")
        logger.info("="*80)

        # Create table
        await self.create_table()

        # Get all MiLB players
        players = await self.get_mlb_player_ids()

        logger.info(f"\nProcessing {len(players)} players with MiLB data...")
        logger.info("")

        # Process each player
        for player_id, milb_games in players:
            await self.process_player(player_id, milb_games)

        logger.info("")
        logger.info("="*80)
        logger.info("Collection complete!")
        logger.info(f"  Players processed: {self.players_processed}")
        logger.info(f"  Players with MLB data: {self.players_with_mlb_data}")
        logger.info(f"  MLB games collected: {self.games_collected}")
        logger.info(f"  Conversion rate: {self.players_with_mlb_data/self.players_processed*100:.1f}%")
        logger.info("="*80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Collect MLB game logs for MiLB players')
    parser.add_argument('--seasons', type=int, nargs='+', default=[2024, 2023, 2022, 2021, 2020],
                       help='Seasons to collect (default: 2024 2023 2022 2021 2020)')
    args = parser.parse_args()

    collector = MLBGameLogCollector(seasons=args.seasons)

    try:
        await collector.create_session()
        await collector.collect_all_mlb_games()
    finally:
        await collector.close_session()


if __name__ == "__main__":
    asyncio.run(main())
