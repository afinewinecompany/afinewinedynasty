"""
Collect Minor League Baseball (MiLB) game stats using MLB StatsAPI wrapper.
This script collects comprehensive game-by-game stats for both hitters and pitchers.
Sport ID 21 = Triple-A
"""

import statsapi
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import time
import asyncio
import asyncpg
from pathlib import Path
import os
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('V1/milb_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MiLBDataCollector:
    """Collector for Minor League Baseball statistics using MLB StatsAPI."""

    def __init__(self):
        """Initialize the MiLB data collector."""
        self.db_pool = None
        self.stats_to_collect = {
            'hitting': [
                'season', 'seasonAdvanced', 'gameLog'
            ],
            'pitching': [
                'season', 'seasonAdvanced', 'gameLog'
            ]
        }
        # Minor League sport IDs
        self.sport_ids = {
            'Triple-A': 11,
            'Double-A': 12,
            'High-A': 13,
            'Single-A': 14,
            'Rookie Advanced': 5,
            'Rookie': 16
        }

    async def init_db(self):
        """Initialize database connection pool."""
        try:
            # Parse the connection string
            db_url = str(settings.SQLALCHEMY_DATABASE_URI)
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            self.db_pool = await asyncpg.create_pool(
                db_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def close_db(self):
        """Close database connection pool."""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("Database connection pool closed")

    def get_leagues_by_sport(self, sport_id: int, season: int) -> List[Dict]:
        """Get all leagues for a given sport and season."""
        try:
            leagues_data = statsapi.get(
                'league',
                {'sportId': sport_id, 'season': season}
            )
            return leagues_data.get('leagues', [])
        except Exception as e:
            logger.error(f"Error fetching leagues for sport {sport_id}: {e}")
            return []

    def get_teams_by_league(self, league_id: int, season: int) -> List[Dict]:
        """Get all teams in a league for a season."""
        try:
            teams_data = statsapi.get(
                'teams',
                {'leagueId': league_id, 'season': season, 'sportId': 21}
            )
            return teams_data.get('teams', [])
        except Exception as e:
            logger.error(f"Error fetching teams for league {league_id}: {e}")
            return []

    def get_roster(self, team_id: int, season: int) -> List[Dict]:
        """Get roster for a team in a given season."""
        try:
            roster_data = statsapi.get(
                f'teams/{team_id}/roster',
                {'season': season}
            )
            return roster_data.get('roster', [])
        except Exception as e:
            logger.error(f"Error fetching roster for team {team_id}: {e}")
            return []

    def get_player_stats(self, player_id: int, season: int, stat_group: str = 'hitting,pitching') -> Dict:
        """Get comprehensive stats for a player."""
        try:
            stats = statsapi.get(
                'people',
                {
                    'personIds': player_id,
                    'season': season,
                    'hydrate': f'stats(group=[{stat_group}],type=[season,seasonAdvanced])'
                }
            )

            if stats.get('people'):
                return stats['people'][0]
            return {}
        except Exception as e:
            logger.error(f"Error fetching stats for player {player_id}: {e}")
            return {}

    def get_game_logs(self, player_id: int, season: int, game_type: str = 'R') -> List[Dict]:
        """Get game logs for a player in a season."""
        try:
            # Build the request for game logs
            logs = statsapi.get(
                f'people/{player_id}/stats',
                {
                    'stats': 'gameLog',
                    'season': season,
                    'gameType': game_type,
                    'group': 'hitting,pitching'
                }
            )

            game_logs = []
            for stat_group in logs.get('stats', []):
                if stat_group.get('type', {}).get('displayName') == 'gameLog':
                    for split in stat_group.get('splits', []):
                        game_logs.append(split)

            return game_logs
        except Exception as e:
            logger.error(f"Error fetching game logs for player {player_id}: {e}")
            return []

    async def store_game_log(self, game_log_data: Dict) -> bool:
        """Store game log data in the database."""
        try:
            async with self.db_pool.acquire() as conn:
                # Map API fields to database columns
                insert_query = """
                    INSERT INTO milb_game_logs (
                        mlb_player_id, season, game_pk, game_date, game_type,
                        team_id, opponent_id, is_home,
                        -- Hitting stats
                        games_played, at_bats, plate_appearances, runs, hits,
                        doubles, triples, home_runs, rbi, total_bases,
                        walks, intentional_walks, strikeouts, hit_by_pitch,
                        stolen_bases, caught_stealing,
                        fly_outs, ground_outs, ground_into_double_play,
                        sac_bunts, sac_flies, left_on_base,
                        batting_avg, obp, slg, ops,
                        -- Pitching stats
                        games_pitched, games_started, complete_games, shutouts,
                        wins, losses, saves, holds,
                        innings_pitched, batters_faced,
                        hits_allowed, runs_allowed, earned_runs, home_runs_allowed,
                        walks_allowed, strikeouts_pitched, hit_batsmen,
                        balks, wild_pitches, pickoffs,
                        era, whip, avg_against, strike_percentage,
                        data_source, prospect_id
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8,
                        $9, $10, $11, $12, $13, $14, $15, $16, $17, $18,
                        $19, $20, $21, $22, $23, $24, $25, $26, $27,
                        $28, $29, $30, $31, $32, $33, $34,
                        $35, $36, $37, $38, $39, $40, $41, $42,
                        $43, $44, $45, $46, $47, $48, $49, $50, $51,
                        $52, $53, $54, $55, $56, $57, $58,
                        'mlb_stats_api',
                        (SELECT id FROM prospects WHERE mlb_id = $1 LIMIT 1)
                    )
                    ON CONFLICT (mlb_player_id, game_pk, season)
                    DO UPDATE SET
                        updated_at = NOW(),
                        data_source = EXCLUDED.data_source
                    RETURNING id
                """

                # Execute the insert
                result = await conn.fetchval(insert_query, *self._extract_values(game_log_data))
                return result is not None

        except Exception as e:
            logger.error(f"Error storing game log: {e}")
            return False

    def _extract_values(self, game_log: Dict) -> tuple:
        """Extract values from game log for database insertion."""
        stat = game_log.get('stat', {})
        game = game_log.get('game', {})

        # Parse game date
        game_date_str = game_log.get('date', '')
        game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date() if game_date_str else None

        return (
            game_log.get('player', {}).get('id'),  # mlb_player_id
            game_log.get('season'),  # season
            game.get('gamePk'),  # game_pk
            game_date,  # game_date
            game.get('gameType', 'R'),  # game_type
            game_log.get('team', {}).get('id'),  # team_id
            game_log.get('opponent', {}).get('id'),  # opponent_id
            game_log.get('isHome', False),  # is_home
            # Hitting stats
            stat.get('gamesPlayed', 0),
            stat.get('atBats', 0),
            stat.get('plateAppearances', 0),
            stat.get('runs', 0),
            stat.get('hits', 0),
            stat.get('doubles', 0),
            stat.get('triples', 0),
            stat.get('homeRuns', 0),
            stat.get('rbi', 0),
            stat.get('totalBases', 0),
            stat.get('baseOnBalls', 0),
            stat.get('intentionalWalks', 0),
            stat.get('strikeOuts', 0),
            stat.get('hitByPitch', 0),
            stat.get('stolenBases', 0),
            stat.get('caughtStealing', 0),
            stat.get('flyOuts', 0),
            stat.get('groundOuts', 0),
            stat.get('groundIntoDoublePlay', 0),
            stat.get('sacBunts', 0),
            stat.get('sacFlies', 0),
            stat.get('leftOnBase', 0),
            stat.get('avg', 0.0),
            stat.get('obp', 0.0),
            stat.get('slg', 0.0),
            stat.get('ops', 0.0),
            # Pitching stats
            stat.get('gamesPitched', 0),
            stat.get('gamesStarted', 0),
            stat.get('completeGames', 0),
            stat.get('shutouts', 0),
            stat.get('wins', 0),
            stat.get('losses', 0),
            stat.get('saves', 0),
            stat.get('holds', 0),
            float(stat.get('inningsPitched', '0.0') or 0),
            stat.get('battersFaced', 0),
            stat.get('hitsAllowed', 0),
            stat.get('runsAllowed', 0),
            stat.get('earnedRuns', 0),
            stat.get('homeRunsAllowed', 0),
            stat.get('walksAllowed', 0),
            stat.get('strikeoutsPitched', 0),
            stat.get('hitBatsmen', 0),
            stat.get('balks', 0),
            stat.get('wildPitches', 0),
            stat.get('pickoffs', 0),
            stat.get('era', 0.0),
            stat.get('whip', 0.0),
            stat.get('avgAgainst', 0.0),
            stat.get('strikePercentage', 0.0)
        )

    async def collect_season_data(self, season: int, sport_level: str = 'Triple-A'):
        """Collect all data for a specific season and minor league level."""
        sport_id = self.sport_ids.get(sport_level)
        if not sport_id:
            logger.error(f"Unknown sport level: {sport_level}")
            return

        logger.info(f"Starting collection for {season} {sport_level} (sport_id: {sport_id})")

        # Get all leagues for this sport
        leagues = self.get_leagues_by_sport(sport_id, season)
        logger.info(f"Found {len(leagues)} leagues for {sport_level}")

        total_players = 0
        total_game_logs = 0

        for league in leagues:
            league_id = league.get('id')
            league_name = league.get('name')
            logger.info(f"Processing league: {league_name} (ID: {league_id})")

            # Get all teams in league
            teams = self.get_teams_by_league(league_id, season)

            for team in teams:
                team_id = team.get('id')
                team_name = team.get('name')
                logger.info(f"Processing team: {team_name}")

                # Get roster
                roster = self.get_roster(team_id, season)

                for player in roster:
                    player_id = player.get('person', {}).get('id')
                    player_name = player.get('person', {}).get('fullName')
                    position = player.get('position', {}).get('type')

                    if not player_id:
                        continue

                    # Get game logs for player
                    game_logs = self.get_game_logs(player_id, season)

                    if game_logs:
                        logger.info(f"Found {len(game_logs)} game logs for {player_name}")
                        total_players += 1

                        # Store each game log
                        for log in game_logs:
                            log['player'] = {'id': player_id}
                            log['season'] = season
                            success = await self.store_game_log(log)
                            if success:
                                total_game_logs += 1

                    # Rate limiting
                    time.sleep(0.1)

        logger.info(f"Collection complete for {season} {sport_level}")
        logger.info(f"Total players processed: {total_players}")
        logger.info(f"Total game logs stored: {total_game_logs}")

    async def collect_multiple_seasons(self, start_season: int, end_season: int, levels: List[str] = None):
        """Collect data for multiple seasons and levels."""
        if levels is None:
            levels = list(self.sport_ids.keys())

        for season in range(start_season, end_season + 1):
            for level in levels:
                await self.collect_season_data(season, level)

                # Longer delay between levels
                await asyncio.sleep(5)

            # Even longer delay between seasons
            await asyncio.sleep(10)


async def main():
    """Main execution function."""
    collector = MiLBDataCollector()

    try:
        # Initialize database
        await collector.init_db()

        # Collect data for 2024 season, Triple-A only as a test
        await collector.collect_season_data(2024, 'Triple-A')

        # To collect multiple seasons/levels:
        # await collector.collect_multiple_seasons(2022, 2024, ['Triple-A', 'Double-A'])

    except Exception as e:
        logger.error(f"Collection failed: {e}")
    finally:
        await collector.close_db()


if __name__ == "__main__":
    asyncio.run(main())