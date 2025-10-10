"""
Collect Rookie Ball (Sport ID 16) game stats for 2021-2025 seasons.
This fills in missing lower-level data that wasn't captured in the initial collection.
"""

import statsapi
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import time
import asyncio
import asyncpg
from pathlib import Path
import os
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Make sure we're loading the env from the right place
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

# Configure logging
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'rookie_ball_collection.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class RookieBallCollector:
    """Collector for Rookie Ball (Sport ID 16) statistics."""

    def __init__(self, checkpoint_file: str = 'rookie_ball_checkpoint.json'):
        """Initialize the Rookie Ball data collector."""
        self.db_pool = None
        self.checkpoint_file = Path(__file__).parent / checkpoint_file
        self.checkpoint_data = self.load_checkpoint()

        # Target seasons
        self.seasons = [2021, 2022, 2023, 2024, 2025]

        # Rookie Ball sport ID
        self.sport_id = 16
        self.level_name = 'Rookie'

        # Track collection statistics
        self.stats = {
            'total_players': 0,
            'total_game_logs': 0,
            'total_errors': 0,
            'start_time': datetime.now()
        }

    def load_checkpoint(self) -> Dict:
        """Load checkpoint data to resume collection."""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading checkpoint: {e}")
        return {
            'completed_seasons': [],
            'completed_teams': {},
            'processed_players': set()
        }

    def save_checkpoint(self):
        """Save checkpoint data for resuming collection."""
        try:
            # Convert sets to lists for JSON serialization
            checkpoint_copy = self.checkpoint_data.copy()
            if isinstance(checkpoint_copy.get('processed_players'), set):
                checkpoint_copy['processed_players'] = list(checkpoint_copy['processed_players'])

            with open(self.checkpoint_file, 'w') as f:
                json.dump(checkpoint_copy, f, indent=2)
            logger.info("Checkpoint saved")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")

    async def init_db(self):
        """Initialize database connection pool."""
        try:
            # Parse the connection string
            db_url = str(settings.SQLALCHEMY_DATABASE_URI)
            if db_url.startswith("postgresql+asyncpg://"):
                db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

            self.db_pool = await asyncpg.create_pool(
                db_url,
                min_size=2,
                max_size=20,
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

    def get_season_teams(self, season: int) -> List[Dict]:
        """Get all rookie ball teams for a season."""
        all_teams = []

        try:
            # Get teams for rookie ball (sport ID 16)
            response = statsapi.get(
                'teams',
                {'sportId': self.sport_id, 'season': season}
            )

            teams = response.get('teams', [])
            for team in teams:
                team['level'] = self.level_name
                team['sport_id'] = self.sport_id
            all_teams.extend(teams)

            logger.info(f"Found {len(teams)} teams for {season} {self.level_name}")
            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            logger.error(f"Error fetching teams for {season} {self.level_name}: {e}")

        return all_teams

    def get_roster(self, team_id: int, season: int) -> List[Dict]:
        """Get roster for a team in a given season."""
        try:
            # Try different roster types
            for roster_type in ['active', 'fullSeason', '40Man']:
                try:
                    roster_data = statsapi.get(
                        f'teams/{team_id}/roster',
                        {'rosterType': roster_type, 'season': season}
                    )
                    roster = roster_data.get('roster', [])
                    if roster:
                        return roster
                except:
                    continue

            # Fallback to default roster
            roster_data = statsapi.get(
                f'teams/{team_id}/roster',
                {'season': season}
            )
            return roster_data.get('roster', [])

        except Exception as e:
            logger.error(f"Error fetching roster for team {team_id}: {e}")
            return []

    def get_player_game_logs(self, player_id: int, season: int) -> List[Dict]:
        """Get all game logs for a player in a season."""
        all_logs = []

        # Try both hitting and pitching stats
        for stat_group in ['hitting', 'pitching']:
            try:
                response = statsapi.get(
                    f'people/{player_id}/stats',
                    {
                        'stats': 'gameLog',
                        'season': season,
                        'group': stat_group,
                        'gameType': 'R'  # Regular season
                    }
                )

                for stat_type in response.get('stats', []):
                    if stat_type.get('type', {}).get('displayName') == 'gameLog':
                        splits = stat_type.get('splits', [])
                        for split in splits:
                            split['stat_group'] = stat_group
                            split['player_id'] = player_id
                            all_logs.append(split)

            except Exception as e:
                # Many players won't have both hitting and pitching stats
                if 'No stats available' not in str(e):
                    logger.debug(f"Error getting {stat_group} logs for player {player_id}: {e}")

        return all_logs

    async def store_game_logs_batch(self, game_logs: List[Dict], player_info: Dict) -> int:
        """Store multiple game logs in a batch."""
        if not game_logs:
            return 0

        stored_count = 0

        try:
            async with self.db_pool.acquire() as conn:
                # First, ensure prospect exists
                prospect_id = await self.ensure_prospect_exists(conn, player_info)

                for log in game_logs:
                    try:
                        stored = await self.store_single_log(conn, log, prospect_id, player_info)
                        if stored:
                            stored_count += 1
                    except Exception as e:
                        logger.debug(f"Error storing individual log: {e}")

        except Exception as e:
            logger.error(f"Error in batch storage: {e}")

        return stored_count

    async def ensure_prospect_exists(self, conn, player_info: Dict) -> Optional[int]:
        """Ensure a prospect exists in the database."""
        player_id = player_info.get('id')

        # Check if prospect exists
        existing = await conn.fetchval(
            "SELECT id FROM prospects WHERE mlb_id = $1",
            player_id
        )

        if existing:
            return existing

        # Create new prospect
        try:
            prospect_id = await conn.fetchval(
                """
                INSERT INTO prospects (
                    mlb_id, name, position, organization, level, age,
                    date_recorded, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, NOW(), NOW())
                ON CONFLICT (mlb_id) DO UPDATE
                SET
                    name = EXCLUDED.name,
                    organization = EXCLUDED.organization,
                    level = EXCLUDED.level,
                    updated_at = NOW()
                RETURNING id
                """,
                player_id,
                player_info.get('fullName', 'Unknown'),
                player_info.get('position', 'Unknown'),
                player_info.get('team_name', 'Unknown'),
                player_info.get('level', 'Unknown'),
                player_info.get('age')
            )
            return prospect_id
        except Exception as e:
            logger.error(f"Error creating prospect: {e}")
            return None

    async def store_single_log(self, conn, log: Dict, prospect_id: int, player_info: Dict) -> bool:
        """Store a single game log."""
        try:
            stat = log.get('stat', {})
            game = log.get('game', {})

            # Parse date
            date_str = log.get('date', '')
            game_date = None
            if date_str:
                try:
                    game_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    pass

            # Determine if this is hitting or pitching
            is_pitching = log.get('stat_group') == 'pitching'

            # Build insert query based on stat type
            if is_pitching:
                query = """
                    INSERT INTO milb_game_logs (
                        prospect_id, mlb_player_id, season, game_pk, game_date, game_type,
                        team_id, opponent_id, is_home, level,
                        games_pitched, games_started, innings_pitched,
                        wins, losses, saves, holds,
                        hits_allowed, runs_allowed, earned_runs, home_runs_allowed,
                        walks_allowed, strikeouts_pitched, hit_batsmen,
                        era, whip, batters_faced,
                        data_source, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        1, $11, $12, $13, $14, $15, $16,
                        $17, $18, $19, $20, $21, $22, $23,
                        $24, $25, $26,
                        'mlb_stats_api_rookie', NOW()
                    )
                    ON CONFLICT (mlb_player_id, game_pk, season)
                    DO UPDATE SET updated_at = NOW()
                """

                values = (
                    prospect_id,
                    player_info.get('id'),
                    log.get('season'),
                    game.get('gamePk'),
                    game_date,
                    game.get('gameType', 'R'),
                    log.get('team', {}).get('id'),
                    log.get('opponent', {}).get('id'),
                    log.get('isHome', False),
                    'Rookie',  # Set level to Rookie
                    stat.get('gamesStarted', 0),
                    self.parse_innings(stat.get('inningsPitched', '0.0')),
                    stat.get('wins', 0),
                    stat.get('losses', 0),
                    stat.get('saves', 0),
                    stat.get('holds', 0),
                    stat.get('hitsAllowed', 0),
                    stat.get('runsAllowed', 0),
                    stat.get('earnedRuns', 0),
                    stat.get('homeRunsAllowed', 0),
                    stat.get('walksAllowed', 0),
                    stat.get('strikeOuts', 0),
                    stat.get('hitBatsmen', 0),
                    float(stat.get('era', 0) or 0),
                    float(stat.get('whip', 0) or 0),
                    stat.get('battersFaced', 0)
                )

            else:  # Hitting
                query = """
                    INSERT INTO milb_game_logs (
                        prospect_id, mlb_player_id, season, game_pk, game_date, game_type,
                        team_id, opponent_id, is_home, level,
                        games_played, at_bats, plate_appearances,
                        runs, hits, doubles, triples, home_runs, rbi,
                        walks, strikeouts, stolen_bases, caught_stealing,
                        batting_avg, on_base_pct, slugging_pct, ops,
                        data_source, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        1, $11, $12, $13, $14, $15, $16, $17, $18,
                        $19, $20, $21, $22,
                        $23, $24, $25, $26,
                        'mlb_stats_api_rookie', NOW()
                    )
                    ON CONFLICT (mlb_player_id, game_pk, season)
                    DO UPDATE SET updated_at = NOW()
                """

                values = (
                    prospect_id,
                    player_info.get('id'),
                    log.get('season'),
                    game.get('gamePk'),
                    game_date,
                    game.get('gameType', 'R'),
                    log.get('team', {}).get('id'),
                    log.get('opponent', {}).get('id'),
                    log.get('isHome', False),
                    'Rookie',  # Set level to Rookie
                    stat.get('atBats', 0),
                    stat.get('plateAppearances', 0),
                    stat.get('runs', 0),
                    stat.get('hits', 0),
                    stat.get('doubles', 0),
                    stat.get('triples', 0),
                    stat.get('homeRuns', 0),
                    stat.get('rbi', 0),
                    stat.get('baseOnBalls', 0),
                    stat.get('strikeOuts', 0),
                    stat.get('stolenBases', 0),
                    stat.get('caughtStealing', 0),
                    float(stat.get('avg', 0) or 0),
                    float(stat.get('obp', 0) or 0),
                    float(stat.get('slg', 0) or 0),
                    float(stat.get('ops', 0) or 0)
                )

            await conn.execute(query, *values)
            return True

        except Exception as e:
            if 'duplicate key' not in str(e).lower():
                logger.debug(f"Error storing log: {e}")
            return False

    def parse_innings(self, innings_str: str) -> float:
        """Parse innings pitched string (e.g., '5.2' means 5 and 2/3 innings)."""
        try:
            if not innings_str:
                return 0.0
            innings_str = str(innings_str)
            if '.' in innings_str:
                parts = innings_str.split('.')
                full = int(parts[0])
                thirds = int(parts[1]) if len(parts) > 1 else 0
                return full + (thirds / 3.0)
            return float(innings_str)
        except:
            return 0.0

    async def collect_team_players(self, team: Dict, season: int) -> Dict[str, int]:
        """Collect all players and their stats for a team."""
        team_id = team.get('id')
        team_name = team.get('name')
        level = team.get('level')

        # Check if team already processed
        season_key = str(season)
        if season_key not in self.checkpoint_data.get('completed_teams', {}):
            self.checkpoint_data['completed_teams'][season_key] = []

        if team_id in self.checkpoint_data['completed_teams'][season_key]:
            logger.info(f"Skipping already processed team: {team_name}")
            return {'players': 0, 'logs': 0}

        logger.info(f"Processing team: {team_name} ({level})")

        # Get roster
        roster = self.get_roster(team_id, season)

        if not roster:
            logger.warning(f"No roster found for {team_name}")
            return {'players': 0, 'logs': 0}

        team_stats = {'players': 0, 'logs': 0}

        # Process each player
        for player_entry in roster:
            player = player_entry.get('person', {})
            player_id = player.get('id')

            if not player_id:
                continue

            # Check if player already processed
            player_key = f"{season}_{player_id}"
            if player_key in self.checkpoint_data.get('processed_players', set()):
                continue

            player_name = player.get('fullName', 'Unknown')
            position = player_entry.get('position', {}).get('abbreviation', 'Unknown')

            # Get player details including age
            try:
                player_details = statsapi.get(f'people/{player_id}')
                person_data = player_details.get('people', [{}])[0]
                birth_date = person_data.get('birthDate')
                age = None
                if birth_date:
                    birth = datetime.strptime(birth_date, '%Y-%m-%d')
                    age = season - birth.year

                player_info = {
                    'id': player_id,
                    'fullName': player_name,
                    'position': position,
                    'team_name': team_name,
                    'level': level,
                    'age': age
                }

            except Exception as e:
                logger.debug(f"Error getting player details for {player_name}: {e}")
                player_info = {
                    'id': player_id,
                    'fullName': player_name,
                    'position': position,
                    'team_name': team_name,
                    'level': level,
                    'age': None
                }

            # Get game logs
            game_logs = self.get_player_game_logs(player_id, season)

            if game_logs:
                # Add season to each log
                for log in game_logs:
                    log['season'] = season

                # Store logs
                stored = await self.store_game_logs_batch(game_logs, player_info)

                if stored > 0:
                    team_stats['players'] += 1
                    team_stats['logs'] += stored
                    logger.info(f"  {player_name}: {stored} game logs stored")

                # Mark player as processed
                if 'processed_players' not in self.checkpoint_data:
                    self.checkpoint_data['processed_players'] = set()
                elif isinstance(self.checkpoint_data['processed_players'], list):
                    self.checkpoint_data['processed_players'] = set(self.checkpoint_data['processed_players'])

                self.checkpoint_data['processed_players'].add(player_key)

            # Rate limiting
            await asyncio.sleep(0.1)

        # Mark team as completed
        self.checkpoint_data['completed_teams'][season_key].append(team_id)
        self.save_checkpoint()

        return team_stats

    async def collect_season(self, season: int):
        """Collect all data for a specific season."""
        if season in self.checkpoint_data.get('completed_seasons', []):
            logger.info(f"Season {season} already completed, skipping")
            return

        logger.info(f"{'='*60}")
        logger.info(f"Starting Rookie Ball collection for {season} season")
        logger.info(f"{'='*60}")

        # Get all teams for the season
        teams = self.get_season_teams(season)
        logger.info(f"Found {len(teams)} total teams for {season}")

        season_stats = {'players': 0, 'logs': 0}

        # Process each team
        for i, team in enumerate(teams, 1):
            logger.info(f"Progress: {i}/{len(teams)} teams")

            team_stats = await self.collect_team_players(team, season)
            season_stats['players'] += team_stats['players']
            season_stats['logs'] += team_stats['logs']

            # Longer delay between teams
            await asyncio.sleep(2)

        # Mark season as completed
        if 'completed_seasons' not in self.checkpoint_data:
            self.checkpoint_data['completed_seasons'] = []
        self.checkpoint_data['completed_seasons'].append(season)
        self.save_checkpoint()

        logger.info(f"Season {season} complete: {season_stats['players']} players, {season_stats['logs']} game logs")

        # Update global stats
        self.stats['total_players'] += season_stats['players']
        self.stats['total_game_logs'] += season_stats['logs']

    async def run_collection(self):
        """Run the full collection for all target seasons."""
        logger.info("Starting Rookie Ball data collection for 2021-2025")

        try:
            await self.init_db()

            for season in self.seasons:
                await self.collect_season(season)

                # Longer delay between seasons
                if season != self.seasons[-1]:
                    logger.info("Pausing 30 seconds before next season...")
                    await asyncio.sleep(30)

            # Print final statistics
            duration = datetime.now() - self.stats['start_time']
            logger.info(f"{'='*60}")
            logger.info("Rookie Ball Collection Complete!")
            logger.info(f"Total players processed: {self.stats['total_players']}")
            logger.info(f"Total game logs stored: {self.stats['total_game_logs']}")
            logger.info(f"Total errors: {self.stats['total_errors']}")
            logger.info(f"Duration: {duration}")
            logger.info(f"{'='*60}")

        except KeyboardInterrupt:
            logger.info("Collection interrupted by user")
            self.save_checkpoint()
        except Exception as e:
            logger.error(f"Collection failed: {e}")
            self.save_checkpoint()
        finally:
            await self.close_db()


async def main():
    """Main execution function."""
    collector = RookieBallCollector()
    await collector.run_collection()


if __name__ == "__main__":
    asyncio.run(main())