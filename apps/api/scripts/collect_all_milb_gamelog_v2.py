"""
Enhanced MiLB Game Log Collector v2 - Improved reliability and performance

Key improvements over v1:
- Concurrent player processing with configurable batch size
- Better error handling with automatic retries
- Progress tracking with ETA
- Resume capability for interrupted collections
- Separate log files for errors
- Rate limiting with backoff
- Memory optimization
- Better duplicate detection

Usage:
    python collect_all_milb_gamelog_v2.py --season 2025 --levels AAA AA A+
    python collect_all_milb_gamelog_v2.py --season 2025 --resume  # Resume interrupted collection
"""

import argparse
import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import aiohttp
from sqlalchemy import text

from app.db.database import engine

# Configure logging
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Main log file
log_file = LOG_DIR / f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Error log file
error_logger = logging.getLogger('errors')
error_handler = logging.FileHandler(LOG_DIR / f"errors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
error_logger.addHandler(error_handler)


def safe_float(value) -> Optional[float]:
    """Safely convert value to float, handling MLB API's special values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        if value in ('.---', '-.--', '∞', 'Infinity', '', 'inf', '-inf'):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


class ProgressTracker:
    """Track collection progress and estimate completion time."""

    def __init__(self, total_items: int):
        self.total_items = total_items
        self.processed_items = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_update_count = 0

    def update(self, count: int = 1):
        """Update progress and return stats."""
        self.processed_items += count
        current_time = time.time()

        # Calculate rates
        elapsed = current_time - self.start_time
        overall_rate = self.processed_items / elapsed if elapsed > 0 else 0

        # Recent rate (last minute)
        recent_elapsed = current_time - self.last_update_time
        if recent_elapsed > 60:  # Update recent rate every minute
            recent_count = self.processed_items - self.last_update_count
            recent_rate = recent_count / recent_elapsed
            self.last_update_time = current_time
            self.last_update_count = self.processed_items
        else:
            recent_rate = overall_rate

        # Estimate time remaining
        remaining_items = self.total_items - self.processed_items
        if recent_rate > 0:
            eta_seconds = remaining_items / recent_rate
            eta = datetime.now() + timedelta(seconds=eta_seconds)
        else:
            eta = None

        return {
            'processed': self.processed_items,
            'total': self.total_items,
            'percentage': (self.processed_items / self.total_items * 100) if self.total_items > 0 else 0,
            'rate': recent_rate,
            'elapsed': elapsed,
            'eta': eta
        }


class EnhancedMiLBCollector:
    """Enhanced MiLB game log collector with improved reliability."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    MILB_SPORT_IDS = {
        11: "AAA",
        12: "AA",
        13: "A+",
        14: "A",
        15: "Rookie",
        16: "Rookie+",
        17: "Winter",  # Arizona Fall League / Dominican Winter League
        # Note: DSL and ACL teams might be under Rookie (15) or complex leagues
    }

    PITCHER_POSITIONS = {'P', 'SP', 'RP', 'LHP', 'RHP', 'CL', 'SU', 'MR'}

    def __init__(self, season: int, levels: List[str], concurrent_limit: int = 5,
                 resume_file: Optional[str] = None):
        self.session: Optional[aiohttp.ClientSession] = None
        self.season = season
        self.levels = levels
        self.concurrent_limit = concurrent_limit

        # Rate limiting
        self.request_delay = 0.2  # Base delay between requests
        self.max_retries = 3
        self.retry_delay = 1.0

        # Statistics
        self.stats = {
            'hitting_games': 0,
            'pitching_games': 0,
            'players_processed': 0,
            'players_skipped': 0,
            'players_with_hitting': 0,
            'players_with_pitching': 0,
            'errors': 0,
            'api_calls': 0
        }

        # Resume capability
        self.resume_file = resume_file or f"resume_{season}.json"
        self.processed_players: Set[int] = set()
        self.failed_players: Set[int] = set()

        # Existing data cache
        self.existing_hitting: Set[int] = set()
        self.existing_pitching: Set[int] = set()

        # Progress tracking
        self.progress: Optional[ProgressTracker] = None

    async def __aenter__(self):
        """Initialize session and load existing data."""
        timeout = aiohttp.ClientTimeout(total=60)
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        )

        # Load existing data
        await self.load_existing_data()

        # Load resume state if exists
        self.load_resume_state()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up session and save state."""
        # Save resume state
        self.save_resume_state()

        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    def load_resume_state(self):
        """Load resume state from file if it exists."""
        resume_path = Path(self.resume_file)
        if resume_path.exists():
            try:
                with open(resume_path, 'r') as f:
                    state = json.load(f)
                    self.processed_players = set(state.get('processed', []))
                    self.failed_players = set(state.get('failed', []))
                    logger.info(f"Resumed from previous state: {len(self.processed_players)} already processed")
            except Exception as e:
                logger.warning(f"Could not load resume state: {e}")

    def save_resume_state(self):
        """Save current state for resume capability."""
        try:
            state = {
                'season': self.season,
                'levels': self.levels,
                'processed': list(self.processed_players),
                'failed': list(self.failed_players),
                'stats': self.stats,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.resume_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save resume state: {e}")

    async def load_existing_data(self):
        """Load existing player data from database."""
        try:
            async with engine.begin() as conn:
                # Get players with hitting data
                result = await conn.execute(text("""
                    SELECT DISTINCT mlb_player_id
                    FROM milb_game_logs
                    WHERE season = :season
                    AND mlb_player_id IS NOT NULL
                    AND games_played > 0
                """), {'season': self.season})
                self.existing_hitting = {row[0] for row in result}

                # Get players with pitching data
                result = await conn.execute(text("""
                    SELECT DISTINCT mlb_player_id
                    FROM milb_game_logs
                    WHERE season = :season
                    AND mlb_player_id IS NOT NULL
                    AND games_pitched > 0
                """), {'season': self.season})
                self.existing_pitching = {row[0] for row in result}

                logger.info(f"Found existing data: {len(self.existing_hitting)} hitters, "
                          f"{len(self.existing_pitching)} pitchers")
        except Exception as e:
            logger.warning(f"Could not load existing data: {e}")

    async def fetch_with_retry(self, url: str, retries: int = None) -> Optional[Dict[str, Any]]:
        """Fetch JSON with automatic retry and exponential backoff."""
        retries = retries if retries is not None else self.max_retries

        for attempt in range(retries):
            try:
                await asyncio.sleep(self.request_delay)
                self.stats['api_calls'] += 1

                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        return None  # Not found is not an error
                    elif response.status == 429:  # Rate limited
                        wait_time = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limited, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")

            except asyncio.TimeoutError:
                logger.warning(f"Timeout on attempt {attempt + 1} for {url}")
            except Exception as e:
                error_logger.error(f"Error fetching {url}: {str(e)}")

            if attempt < retries - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))

        self.stats['errors'] += 1
        return None

    async def get_milb_teams(self, sport_id: int) -> List[Dict[str, Any]]:
        """Get all teams for a MiLB level."""
        url = f"{self.BASE_URL}/teams?sportId={sport_id}&season={self.season}"
        data = await self.fetch_with_retry(url)

        if not data:
            return []

        teams = data.get('teams', [])

        # Filter professional teams
        professional_teams = []
        for team in teams:
            league = team.get('league', {})
            league_name = league.get('name', '').lower()

            # Skip non-professional leagues
            if any(skip in league_name for skip in ['college', 'amateur', 'collegiate', 'complex']):
                continue

            # Keep teams with parent org or recognized leagues
            if team.get('parentOrgId') or team.get('parentOrgName'):
                professional_teams.append(team)
            elif any(milb in league_name for milb in [
                'international', 'pacific coast', 'eastern', 'southern', 'texas',
                'midwest', 'south atlantic', 'carolina', 'california', 'florida state'
            ]):
                professional_teams.append(team)

        return professional_teams

    async def get_team_roster(self, team_id: int) -> List[Dict[str, Any]]:
        """Get roster for a team."""
        url = f"{self.BASE_URL}/teams/{team_id}/roster?season={self.season}"
        data = await self.fetch_with_retry(url)
        return data.get('roster', []) if data else []

    async def discover_players(self) -> List[Dict[str, Any]]:
        """Discover all MiLB players for specified levels."""
        logger.info(f"Discovering players for {self.season}...")

        all_players = {}
        level_map = {v: k for k, v in self.MILB_SPORT_IDS.items()}

        for level in self.levels:
            sport_id = level_map.get(level)
            if not sport_id:
                continue

            logger.info(f"Processing {level} level...")
            teams = await self.get_milb_teams(sport_id)
            logger.info(f"  Found {len(teams)} {level} teams")

            # Process teams concurrently
            roster_tasks = []
            for team in teams:
                roster_tasks.append(self.get_team_roster(team['id']))

            rosters = await asyncio.gather(*roster_tasks, return_exceptions=True)

            for roster in rosters:
                if isinstance(roster, Exception):
                    continue

                for player_entry in roster:
                    person = player_entry.get('person', {})
                    player_id = person.get('id')

                    if player_id and player_id not in all_players:
                        all_players[player_id] = {
                            'player_id': player_id,
                            'name': person.get('fullName'),
                            'position': player_entry.get('position', {}).get('abbreviation', '')
                        }

        players_list = list(all_players.values())
        logger.info(f"Discovered {len(players_list)} unique players")
        return players_list

    async def get_player_game_logs(self, player_id: int, sport_id: int,
                                  group: str = 'hitting') -> List[Dict[str, Any]]:
        """Get game logs for a player."""
        url = (f"{self.BASE_URL}/people/{player_id}/stats?"
               f"stats=gameLog&season={self.season}&group={group}&sportId={sport_id}")

        data = await self.fetch_with_retry(url)
        if not data:
            return []

        stats = data.get('stats', [])
        return stats[0].get('splits', []) if stats else []

    async def save_game_logs(self, player_id: int, game_logs: List[Dict],
                           level: str, stat_type: str) -> int:
        """Save multiple game logs to database in a single transaction."""
        if not game_logs:
            return 0

        saved_count = 0

        try:
            async with engine.begin() as conn:
                for game_log in game_logs:
                    if stat_type == 'hitting':
                        record = self.prepare_hitting_record(player_id, game_log, level)
                        query = self.get_hitting_insert_query()
                    else:
                        record = self.prepare_pitching_record(player_id, game_log, level)
                        query = self.get_pitching_insert_query()

                    await conn.execute(text(query), record)
                    saved_count += 1

            self.stats[f'{stat_type}_games'] += saved_count
            return saved_count

        except Exception as e:
            error_logger.error(f"Error saving {stat_type} logs for player {player_id}: {str(e)}")
            self.stats['errors'] += 1
            return 0

    def prepare_hitting_record(self, player_id: int, game_log: Dict, level: str) -> Dict:
        """Prepare hitting record for database insertion."""
        stat = game_log.get('stat', {})
        game = game_log.get('game', {})
        team = game_log.get('team', {})
        opponent = game_log.get('opponent', {})

        date_str = game_log.get('date')
        game_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

        return {
            'prospect_id': None,
            'mlb_player_id': player_id,
            'season': self.season,
            'game_pk': game.get('gamePk'),
            'game_date': game_date,
            'level': level,
            'game_type': 'Regular',
            'team_id': team.get('id'),
            'opponent_id': opponent.get('id'),
            'games_played': 1,
            'plate_appearances': stat.get('plateAppearances', 0),
            'at_bats': stat.get('atBats', 0),
            'runs': stat.get('runs', 0),
            'hits': stat.get('hits', 0),
            'doubles': stat.get('doubles', 0),
            'triples': stat.get('triples', 0),
            'home_runs': stat.get('homeRuns', 0),
            'rbi': stat.get('rbi', 0),
            'total_bases': stat.get('totalBases', 0),
            'walks': stat.get('baseOnBalls', 0),
            'intentional_walks': stat.get('intentionalWalks', 0),
            'strikeouts': stat.get('strikeOuts', 0),
            'stolen_bases': stat.get('stolenBases', 0),
            'caught_stealing': stat.get('caughtStealing', 0),
            'hit_by_pitch': stat.get('hitByPitch', 0),
            'sacrifice_flies': stat.get('sacFlies', 0),
            'sac_bunts': stat.get('sacBunts', 0),
            'ground_outs': stat.get('groundOuts', 0),
            'fly_outs': stat.get('flyOuts', 0),
            'air_outs': stat.get('airOuts', 0),
            'ground_into_double_play': stat.get('groundIntoDoublePlay', 0),
            'number_of_pitches': stat.get('numberOfPitches', 0),
            'left_on_base': stat.get('leftOnBase', 0),
            'batting_avg': safe_float(stat.get('avg')),
            'on_base_pct': safe_float(stat.get('obp')),
            'slugging_pct': safe_float(stat.get('slg')),
            'ops': safe_float(stat.get('ops')),
            'babip': safe_float(stat.get('babip')),
            'data_source': 'mlb_stats_api_gamelog_v2'
        }

    def prepare_pitching_record(self, player_id: int, game_log: Dict, level: str) -> Dict:
        """Prepare pitching record for database insertion."""
        stat = game_log.get('stat', {})
        game = game_log.get('game', {})
        team = game_log.get('team', {})
        opponent = game_log.get('opponent', {})

        date_str = game_log.get('date')
        game_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

        return {
            'prospect_id': None,
            'mlb_player_id': player_id,
            'season': self.season,
            'game_pk': game.get('gamePk'),
            'game_date': game_date,
            'level': level,
            'game_type': 'Regular',
            'team_id': team.get('id'),
            'opponent_id': opponent.get('id'),
            'games_pitched': 1,
            'games_started': stat.get('gamesStarted', 0),
            'complete_games': stat.get('completeGames', 0),
            'shutouts': stat.get('shutouts', 0),
            'games_finished': stat.get('gamesFinished', 0),
            'wins': stat.get('wins', 0),
            'losses': stat.get('losses', 0),
            'saves': stat.get('saves', 0),
            'save_opportunities': stat.get('saveOpportunities', 0),
            'holds': stat.get('holds', 0),
            'blown_saves': stat.get('blownSaves', 0),
            'innings_pitched': safe_float(stat.get('inningsPitched')),
            'outs': stat.get('outs', 0),
            'batters_faced': stat.get('battersFaced', 0),
            'number_of_pitches_pitched': stat.get('numberOfPitches', 0),
            'strikes': stat.get('strikes', 0),
            'hits_allowed': stat.get('hits', 0),
            'runs_allowed': stat.get('runs', 0),
            'earned_runs': stat.get('earnedRuns', 0),
            'home_runs_allowed': stat.get('homeRuns', 0),
            'walks_allowed': stat.get('baseOnBalls', 0),
            'intentional_walks_allowed': stat.get('intentionalWalks', 0),
            'strikeouts_pitched': stat.get('strikeOuts', 0),
            'hit_batsmen': stat.get('hitBatsmen', 0),
            'stolen_bases_allowed': stat.get('stolenBases', 0),
            'caught_stealing_allowed': stat.get('caughtStealing', 0),
            'balks': stat.get('balks', 0),
            'wild_pitches': stat.get('wildPitches', 0),
            'pickoffs': stat.get('pickoffs', 0),
            'inherited_runners': stat.get('inheritedRunners', 0),
            'inherited_runners_scored': stat.get('inheritedRunnersScored', 0),
            'fly_outs_pitched': stat.get('flyOuts', 0),
            'ground_outs_pitched': stat.get('groundOuts', 0),
            'air_outs_pitched': stat.get('airOuts', 0),
            'total_bases_allowed': stat.get('totalBases', 0),
            'sac_bunts_allowed': stat.get('sacBunts', 0),
            'sac_flies_allowed': stat.get('sacFlies', 0),
            'era': safe_float(stat.get('era')),
            'whip': safe_float(stat.get('whip')),
            'avg_against': safe_float(stat.get('avg')),
            'obp_against': safe_float(stat.get('obp')),
            'slg_against': safe_float(stat.get('slg')),
            'ops_against': safe_float(stat.get('ops')),
            'win_percentage': safe_float(stat.get('winPercentage')),
            'strike_percentage': safe_float(stat.get('strikePercentage')),
            'strikeouts_per_9inn': safe_float(stat.get('strikeoutsPer9Inn')),
            'walks_per_9inn': safe_float(stat.get('walksPer9Inn')),
            'hits_per_9inn': safe_float(stat.get('hitsPer9Inn')),
            'runs_scored_per_9': safe_float(stat.get('runsScoredPer9')),
            'home_runs_per_9': safe_float(stat.get('homeRunsPer9')),
            'pitches_per_inning': safe_float(stat.get('pitchesPerInning')),
            'strikeout_walk_ratio': safe_float(stat.get('strikeoutWalkRatio')),
            'ground_outs_to_airouts_pitched': safe_float(stat.get('groundOutsToAirouts')),
            'stolen_base_percentage_against': safe_float(stat.get('stolenBasePercentage')),
            'data_source': 'mlb_stats_api_gamelog_v2'
        }

    def get_hitting_insert_query(self) -> str:
        """Get SQL query for inserting hitting stats."""
        return """
            INSERT INTO milb_game_logs (
                prospect_id, mlb_player_id, season, game_pk, game_date, level, game_type,
                team_id, opponent_id, games_played, plate_appearances, at_bats, runs, hits,
                doubles, triples, home_runs, rbi, total_bases, walks, intentional_walks,
                strikeouts, stolen_bases, caught_stealing, hit_by_pitch, sacrifice_flies, sac_bunts,
                ground_outs, fly_outs, air_outs, ground_into_double_play, number_of_pitches,
                left_on_base, batting_avg, on_base_pct, slugging_pct, ops, babip, data_source
            ) VALUES (
                :prospect_id, :mlb_player_id, :season, :game_pk, :game_date, :level, :game_type,
                :team_id, :opponent_id, :games_played, :plate_appearances, :at_bats, :runs, :hits,
                :doubles, :triples, :home_runs, :rbi, :total_bases, :walks, :intentional_walks,
                :strikeouts, :stolen_bases, :caught_stealing, :hit_by_pitch, :sacrifice_flies, :sac_bunts,
                :ground_outs, :fly_outs, :air_outs, :ground_into_double_play, :number_of_pitches,
                :left_on_base, :batting_avg, :on_base_pct, :slugging_pct, :ops, :babip, :data_source
            )
            ON CONFLICT (game_pk, mlb_player_id) DO NOTHING
        """

    def get_pitching_insert_query(self) -> str:
        """Get SQL query for inserting pitching stats."""
        return """
            INSERT INTO milb_game_logs (
                prospect_id, mlb_player_id, season, game_pk, game_date, level, game_type,
                team_id, opponent_id, games_pitched, games_started, complete_games, shutouts,
                games_finished, wins, losses, saves, save_opportunities, holds, blown_saves,
                innings_pitched, outs, batters_faced, number_of_pitches_pitched, strikes,
                hits_allowed, runs_allowed, earned_runs, home_runs_allowed, walks_allowed,
                intentional_walks_allowed, strikeouts_pitched, hit_batsmen, stolen_bases_allowed,
                caught_stealing_allowed, balks, wild_pitches, pickoffs, inherited_runners,
                inherited_runners_scored, fly_outs_pitched, ground_outs_pitched, air_outs_pitched,
                total_bases_allowed, sac_bunts_allowed, sac_flies_allowed, era, whip, avg_against,
                obp_against, slg_against, ops_against, win_percentage, strike_percentage,
                strikeouts_per_9inn, walks_per_9inn, hits_per_9inn, runs_scored_per_9,
                home_runs_per_9, pitches_per_inning, strikeout_walk_ratio,
                ground_outs_to_airouts_pitched, stolen_base_percentage_against, data_source
            ) VALUES (
                :prospect_id, :mlb_player_id, :season, :game_pk, :game_date, :level, :game_type,
                :team_id, :opponent_id, :games_pitched, :games_started, :complete_games, :shutouts,
                :games_finished, :wins, :losses, :saves, :save_opportunities, :holds, :blown_saves,
                :innings_pitched, :outs, :batters_faced, :number_of_pitches_pitched, :strikes,
                :hits_allowed, :runs_allowed, :earned_runs, :home_runs_allowed, :walks_allowed,
                :intentional_walks_allowed, :strikeouts_pitched, :hit_batsmen, :stolen_bases_allowed,
                :caught_stealing_allowed, :balks, :wild_pitches, :pickoffs, :inherited_runners,
                :inherited_runners_scored, :fly_outs_pitched, :ground_outs_pitched, :air_outs_pitched,
                :total_bases_allowed, :sac_bunts_allowed, :sac_flies_allowed, :era, :whip, :avg_against,
                :obp_against, :slg_against, :ops_against, :win_percentage, :strike_percentage,
                :strikeouts_per_9inn, :walks_per_9inn, :hits_per_9inn, :runs_scored_per_9,
                :home_runs_per_9, :pitches_per_inning, :strikeout_walk_ratio,
                :ground_outs_to_airouts_pitched, :stolen_base_percentage_against, :data_source
            )
            ON CONFLICT (game_pk, mlb_player_id) DO NOTHING
        """

    async def process_player(self, player: Dict[str, Any]) -> Tuple[int, int]:
        """Process a single player and return counts of games collected."""
        player_id = player['player_id']

        # Skip if already processed in this run
        if player_id in self.processed_players:
            return 0, 0

        # Skip if failed too many times
        if player_id in self.failed_players:
            return 0, 0

        position = player.get('position', '')
        is_pitcher = position in self.PITCHER_POSITIONS

        # Check what data we need
        need_hitting = player_id not in self.existing_hitting
        need_pitching = is_pitcher and (player_id not in self.existing_pitching)

        if not need_hitting and not need_pitching:
            self.stats['players_skipped'] += 1
            self.processed_players.add(player_id)
            return 0, 0

        level_map = {v: k for k, v in self.MILB_SPORT_IDS.items()}
        total_hitting = 0
        total_pitching = 0

        try:
            # Collect data for each level
            for level in self.levels:
                sport_id = level_map.get(level)
                if not sport_id:
                    continue

                # Collect hitting stats
                if need_hitting:
                    hitting_logs = await self.get_player_game_logs(player_id, sport_id, 'hitting')
                    if hitting_logs:
                        count = await self.save_game_logs(player_id, hitting_logs, level, 'hitting')
                        total_hitting += count

                # Collect pitching stats
                if need_pitching:
                    pitching_logs = await self.get_player_game_logs(player_id, sport_id, 'pitching')
                    if pitching_logs:
                        count = await self.save_game_logs(player_id, pitching_logs, level, 'pitching')
                        total_pitching += count

            # Update statistics
            self.stats['players_processed'] += 1
            if total_hitting > 0:
                self.stats['players_with_hitting'] += 1
            if total_pitching > 0:
                self.stats['players_with_pitching'] += 1

            self.processed_players.add(player_id)

            # Log progress
            if total_hitting > 0 or total_pitching > 0:
                logger.debug(f"Player {player_id} ({position}): "
                           f"{total_hitting} hitting, {total_pitching} pitching games")

        except Exception as e:
            error_logger.error(f"Error processing player {player_id}: {str(e)}")
            self.failed_players.add(player_id)
            self.stats['errors'] += 1

        return total_hitting, total_pitching

    async def process_batch(self, players: List[Dict[str, Any]]) -> None:
        """Process a batch of players concurrently."""
        tasks = []
        for player in players:
            tasks.append(self.process_player(player))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Update progress
        if self.progress:
            completed = sum(1 for r in results if not isinstance(r, Exception))
            progress_stats = self.progress.update(completed)

            # Log progress every 10%
            if int(progress_stats['percentage']) % 10 == 0:
                eta_str = progress_stats['eta'].strftime('%H:%M:%S') if progress_stats['eta'] else 'Unknown'
                logger.info(f"Progress: {progress_stats['percentage']:.1f}% "
                          f"({progress_stats['processed']}/{progress_stats['total']}) "
                          f"Rate: {progress_stats['rate']:.1f} players/sec "
                          f"ETA: {eta_str}")

    async def collect_all(self):
        """Main collection loop with concurrent processing."""
        logger.info("="*80)
        logger.info(f"Enhanced MiLB GameLog Collection v2 - Season {self.season}")
        logger.info(f"Levels: {', '.join(self.levels)}")
        logger.info(f"Concurrent limit: {self.concurrent_limit}")
        logger.info("="*80)

        # Discover players
        all_players = await self.discover_players()

        # Filter out already processed players
        players_to_process = [
            p for p in all_players
            if p['player_id'] not in self.processed_players
        ]

        if not players_to_process:
            logger.info("No new players to process")
            return

        logger.info(f"Processing {len(players_to_process)} players "
                   f"({len(self.processed_players)} already done)")

        # Initialize progress tracker
        self.progress = ProgressTracker(len(players_to_process))

        # Process in batches
        for i in range(0, len(players_to_process), self.concurrent_limit):
            batch = players_to_process[i:i + self.concurrent_limit]
            await self.process_batch(batch)

            # Save state periodically
            if i % 100 == 0:
                self.save_resume_state()

        # Final summary
        logger.info("\n" + "="*80)
        logger.info("COLLECTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Players processed: {self.stats['players_processed']}")
        logger.info(f"Players skipped: {self.stats['players_skipped']}")
        logger.info(f"Players with hitting data: {self.stats['players_with_hitting']}")
        logger.info(f"Players with pitching data: {self.stats['players_with_pitching']}")
        logger.info(f"Total hitting games: {self.stats['hitting_games']}")
        logger.info(f"Total pitching games: {self.stats['pitching_games']}")
        logger.info(f"API calls made: {self.stats['api_calls']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")

        # Clean up resume file on successful completion
        if Path(self.resume_file).exists():
            Path(self.resume_file).unlink()
            logger.info("Removed resume file (collection completed)")


async def main():
    parser = argparse.ArgumentParser(
        description='Enhanced MiLB game log collector with improved reliability'
    )
    parser.add_argument('--season', type=int, default=2025,
                       help='Season to collect')
    parser.add_argument('--levels', nargs='+', default=['AAA', 'AA', 'A+'],
                       help='MiLB levels to include')
    parser.add_argument('--concurrent', type=int, default=5,
                       help='Number of concurrent player requests')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from previous collection')

    args = parser.parse_args()

    # Determine resume file
    resume_file = f"resume_{args.season}.json" if args.resume else None

    async with EnhancedMiLBCollector(
        season=args.season,
        levels=args.levels,
        concurrent_limit=args.concurrent,
        resume_file=resume_file
    ) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    # Set up Windows event loop policy for better performance
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())