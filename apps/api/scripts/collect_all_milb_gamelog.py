"""
Collect ALL MiLB player stats using gameLog API (Fixed Version with Pitching)

This script uses the proven gameLog API approach with sportId parameter
to collect game-by-game statistics for all MiLB players.

Key features:
- Uses gameLog API directly (stats already aggregated)
- Collects BOTH hitting AND pitching stats
- No play-by-play fetching required
- Much faster and more reliable

Usage:
    python collect_all_milb_gamelog.py --season 2024 --levels AAA AA A+
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


def safe_float(value) -> Optional[float]:
    """Safely convert value to float, handling MLB API's '.---' for undefined stats."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # MLB API returns '.---' for undefined stats (like ERA when 0 innings pitched)
        if value in ('.---', '-.--', '∞', 'Infinity', ''):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


class MiLBGameLogCollector:
    """Collect MiLB game logs using gameLog API."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    MILB_SPORT_IDS = {
        11: "AAA",
        12: "AA",
        13: "A+",
        14: "A",
        15: "Rookie",
        16: "Rookie+"
    }

    # Positions that are pitchers
    PITCHER_POSITIONS = {'P', 'SP', 'RP', 'LHP', 'RHP'}

    def __init__(self, season: int, levels: List[str]):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.season = season
        self.levels = levels
        self.hitting_games_collected = 0
        self.pitching_games_collected = 0
        self.players_processed = 0
        self.players_with_hitting_data = 0
        self.players_with_pitching_data = 0
        # Track players we've already collected data for
        self.existing_players = set()  # Set of mlb_player_ids with any data for this season
        self.existing_hitting = set()  # Set of mlb_player_ids with hitting data
        self.existing_pitching = set()  # Set of mlb_player_ids with pitching data
        self.skipped_players = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        # Load existing player data to skip API calls
        await self.load_existing_data()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def load_existing_data(self):
        """Load list of players we've already collected hitting/pitching data for this season."""
        try:
            async with engine.begin() as conn:
                # Get players with hitting data (games_played > 0)
                result = await conn.execute(text("""
                    SELECT DISTINCT mlb_player_id
                    FROM milb_game_logs
                    WHERE season = :season
                    AND mlb_player_id IS NOT NULL
                    AND games_played > 0
                """), {'season': self.season})
                self.existing_hitting = {row[0] for row in result}

                # Get players with pitching data (games_pitched > 0)
                result = await conn.execute(text("""
                    SELECT DISTINCT mlb_player_id
                    FROM milb_game_logs
                    WHERE season = :season
                    AND mlb_player_id IS NOT NULL
                    AND games_pitched > 0
                """), {'season': self.season})
                self.existing_pitching = {row[0] for row in result}

                self.existing_players = self.existing_hitting | self.existing_pitching
                if self.existing_players:
                    logger.info(f"Found existing data for {len(self.existing_players)} players in {self.season}")
                    logger.info(f"  - {len(self.existing_hitting)} with hitting data")
                    logger.info(f"  - {len(self.existing_pitching)} with pitching data")
        except Exception as e:
            logger.warning(f"Could not load existing data: {e}. Will proceed without skipping.")
            self.existing_hitting = set()
            self.existing_pitching = set()

    async def fetch_json(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON with rate limiting."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def get_milb_teams(self, sport_id: int) -> List[Dict[str, Any]]:
        """Get all teams for a MiLB level.

        Filters out college/amateur teams to only include professional MiLB organizations.
        """
        url = f"{self.BASE_URL}/teams?sportId={sport_id}&season={self.season}"
        data = await self.fetch_json(url)

        if not data:
            return []

        teams = data.get('teams', [])

        # Filter out college/amateur teams - only keep professional MiLB teams
        # Professional MiLB teams have a parent org ID (MLB affiliate)
        professional_teams = []
        for team in teams:
            league = team.get('league', {})
            league_name = league.get('name', '').lower()

            # Skip college leagues and non-affiliated teams
            if 'college' in league_name or 'amateur' in league_name or 'collegiate' in league_name:
                continue

            # MiLB teams should have parent org (MLB affiliate) or be in recognized MiLB leagues
            # Most important: sportId filtering should already handle this, but double-check league
            if team.get('parentOrgId') or team.get('parentOrgName'):
                professional_teams.append(team)
            elif any(milb_league in league_name for milb_league in [
                'international', 'pacific coast', 'eastern', 'southern', 'texas',
                'midwest', 'south atlantic', 'carolina', 'california', 'florida state'
            ]):
                professional_teams.append(team)

        if len(professional_teams) < len(teams):
            logger.info(f"  Filtered out {len(teams) - len(professional_teams)} non-professional teams")

        return professional_teams

    async def get_team_roster(self, team_id: int) -> List[Dict[str, Any]]:
        """Get roster for a team."""
        url = f"{self.BASE_URL}/teams/{team_id}/roster?season={self.season}"
        data = await self.fetch_json(url)

        if not data:
            return []

        return data.get('roster', [])

    async def discover_players(self) -> List[Dict[str, Any]]:
        """Discover all MiLB players for specified levels."""
        logger.info(f"Discovering players for {self.season}...")

        all_players = {}
        level_map = {v: k for k, v in self.MILB_SPORT_IDS.items()}

        for level in self.levels:
            sport_id = level_map.get(level)
            if not sport_id:
                continue

            logger.info(f"\nProcessing {level} level (sportId={sport_id})...")
            teams = await self.get_milb_teams(sport_id)
            logger.info(f"  Found {len(teams)} {level} teams")

            for i, team in enumerate(teams, 1):
                roster = await self.get_team_roster(team['id'])

                for player_entry in roster:
                    person = player_entry.get('person', {})
                    player_id = person.get('id')

                    if player_id and player_id not in all_players:
                        all_players[player_id] = {
                            'player_id': player_id,
                            'name': person.get('fullName'),
                            'position': player_entry.get('position', {}).get('abbreviation')
                        }

                if i % 10 == 0:
                    logger.info(f"  [{i}/{len(teams)}] {team['name']} - Total unique: {len(all_players)}")

        players_list = list(all_players.values())
        logger.info(f"\nDiscovered {len(players_list)} unique players")
        return players_list

    async def get_player_game_logs(self, player_id: int, sport_id: int, group: str = 'hitting') -> List[Dict[str, Any]]:
        """Get game logs for a player at a specific MiLB level.

        Args:
            player_id: MLB player ID
            sport_id: MiLB level sport ID
            group: 'hitting' or 'pitching'
        """
        url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={self.season}&group={group}&sportId={sport_id}"

        data = await self.fetch_json(url)
        if not data:
            return []

        stats = data.get('stats', [])
        if not stats:
            return []

        return stats[0].get('splits', [])

    async def save_hitting_game_log(self, player_id: int, game_log: Dict[str, Any], level: str):
        """Save hitting stats from a game log to database."""
        try:
            stat = game_log.get('stat', {})
            game = game_log.get('game', {})
            team = game_log.get('team', {})
            opponent = game_log.get('opponent', {})

            # Parse date
            date_str = game_log.get('date')
            game_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

            record = {
                'prospect_id': None,  # Not a prospect, just a MiLB player
                'mlb_player_id': player_id,
                'season': self.season,
                'game_pk': game.get('gamePk'),
                'game_date': game_date,
                'level': level,
                'game_type': 'Regular',
                'team_id': team.get('id'),
                'opponent_id': opponent.get('id'),
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
                'data_source': 'mlb_stats_api_gamelog'
            }

            async with engine.begin() as conn:
                await conn.execute(text("""
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
                    ON CONFLICT (game_pk, mlb_player_id)
                    DO UPDATE SET
                        games_played = EXCLUDED.games_played,
                        plate_appearances = EXCLUDED.plate_appearances,
                        at_bats = EXCLUDED.at_bats,
                        runs = EXCLUDED.runs,
                        hits = EXCLUDED.hits,
                        doubles = EXCLUDED.doubles,
                        triples = EXCLUDED.triples,
                        home_runs = EXCLUDED.home_runs,
                        rbi = EXCLUDED.rbi,
                        total_bases = EXCLUDED.total_bases,
                        walks = EXCLUDED.walks,
                        strikeouts = EXCLUDED.strikeouts,
                        stolen_bases = EXCLUDED.stolen_bases,
                        batting_avg = EXCLUDED.batting_avg,
                        on_base_pct = EXCLUDED.on_base_pct,
                        slugging_pct = EXCLUDED.slugging_pct,
                        ops = EXCLUDED.ops
                """), record)

            self.hitting_games_collected += 1
            return True

        except Exception as e:
            logger.error(f"Error saving hitting game log: {str(e)}")
            return False

    async def save_pitching_game_log(self, player_id: int, game_log: Dict[str, Any], level: str):
        """Save pitching stats from a game log to database."""
        try:
            stat = game_log.get('stat', {})
            game = game_log.get('game', {})
            team = game_log.get('team', {})
            opponent = game_log.get('opponent', {})

            # Parse date
            date_str = game_log.get('date')
            game_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else None

            record = {
                'prospect_id': None,
                'mlb_player_id': player_id,
                'season': self.season,
                'game_pk': game.get('gamePk'),
                'game_date': game_date,
                'level': level,
                'game_type': 'Regular',
                'team_id': team.get('id'),
                'opponent_id': opponent.get('id'),
                # Pitching stats
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
                'data_source': 'mlb_stats_api_gamelog'
            }

            async with engine.begin() as conn:
                await conn.execute(text("""
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
                    ON CONFLICT (game_pk, mlb_player_id)
                    DO UPDATE SET
                        games_pitched = EXCLUDED.games_pitched,
                        games_started = EXCLUDED.games_started,
                        innings_pitched = EXCLUDED.innings_pitched,
                        outs = EXCLUDED.outs,
                        batters_faced = EXCLUDED.batters_faced,
                        hits_allowed = EXCLUDED.hits_allowed,
                        runs_allowed = EXCLUDED.runs_allowed,
                        earned_runs = EXCLUDED.earned_runs,
                        walks_allowed = EXCLUDED.walks_allowed,
                        strikeouts_pitched = EXCLUDED.strikeouts_pitched,
                        era = EXCLUDED.era,
                        whip = EXCLUDED.whip,
                        strikeouts_per_9inn = EXCLUDED.strikeouts_per_9inn
                """), record)

            self.pitching_games_collected += 1
            return True

        except Exception as e:
            logger.error(f"Error saving pitching game log: {str(e)}")
            return False

    async def process_player(self, player: Dict[str, Any]):
        """Process a single player - get all their hitting and pitching game logs."""
        player_id = player['player_id']
        position = player.get('position', '')
        is_pitcher = position in self.PITCHER_POSITIONS

        # Check if we need to collect hitting or pitching data
        need_hitting = player_id not in self.existing_hitting
        need_pitching = is_pitcher and (player_id not in self.existing_pitching)

        # Skip if we already have all necessary data for this player
        if not need_hitting and not need_pitching:
            self.skipped_players += 1
            return

        self.players_processed += 1

        level_map = {v: k for k, v in self.MILB_SPORT_IDS.items()}
        total_hitting_games = 0
        total_pitching_games = 0

        # Check each level
        for level in self.levels:
            sport_id = level_map.get(level)
            if not sport_id:
                continue

            # Collect hitting stats if needed (even pitchers hit in MiLB)
            if need_hitting:
                hitting_logs = await self.get_player_game_logs(player_id, sport_id, group='hitting')
                for game_log in hitting_logs:
                    success = await self.save_hitting_game_log(player_id, game_log, level)
                    if success:
                        total_hitting_games += 1

            # For pitchers, collect pitching stats if needed
            if need_pitching:
                pitching_logs = await self.get_player_game_logs(player_id, sport_id, group='pitching')
                for game_log in pitching_logs:
                    success = await self.save_pitching_game_log(player_id, game_log, level)
                    if success:
                        total_pitching_games += 1

        if total_hitting_games > 0:
            self.players_with_hitting_data += 1
        if total_pitching_games > 0:
            self.players_with_pitching_data += 1

        if total_hitting_games > 0 or total_pitching_games > 0:
            logger.info(f"  [{self.players_processed}/{len(self.all_players)}] Player {player_id} ({position}): "
                       f"{total_hitting_games} hitting, {total_pitching_games} pitching games saved")

        # Progress update
        if self.players_processed % 50 == 0:
            logger.info(f"\nProgress: {self.players_processed}/{len(self.all_players)} players")
            logger.info(f"  Players with hitting data: {self.players_with_hitting_data}")
            logger.info(f"  Players with pitching data: {self.players_with_pitching_data}")
            logger.info(f"  Total hitting games: {self.hitting_games_collected}")
            logger.info(f"  Total pitching games: {self.pitching_games_collected}\n")

    async def collect_all(self):
        """Main collection loop."""
        logger.info("="*80)
        logger.info(f"MiLB GameLog Collection - Season {self.season}")
        logger.info(f"Levels: {', '.join(self.levels)}")
        logger.info("="*80 + "\n")

        # Discover players
        self.all_players = await self.discover_players()

        if not self.all_players:
            logger.info("No players found")
            return

        logger.info(f"\nProcessing {len(self.all_players)} players...\n")

        # Process each player
        for player in self.all_players:
            await self.process_player(player)

        # Summary
        logger.info("\n" + "="*80)
        logger.info("COLLECTION COMPLETE!")
        logger.info("="*80)
        logger.info(f"Total players discovered: {len(self.all_players)}")
        logger.info(f"Players skipped (already in DB): {self.skipped_players}")
        logger.info(f"Players processed (new data): {self.players_processed}")
        logger.info(f"Players with hitting data: {self.players_with_hitting_data}")
        logger.info(f"Players with pitching data: {self.players_with_pitching_data}")
        logger.info(f"Total hitting games collected: {self.hitting_games_collected}")
        logger.info(f"Total pitching games collected: {self.pitching_games_collected}")
        logger.info(f"Average hitting games/player: {self.hitting_games_collected/max(self.players_with_hitting_data,1):.1f}")
        logger.info(f"Average pitching games/pitcher: {self.pitching_games_collected/max(self.players_with_pitching_data,1):.1f}")


async def main():
    parser = argparse.ArgumentParser(description='Collect ALL MiLB game logs (hitting + pitching) using gameLog API')
    parser.add_argument('--season', type=int, default=2024, help='Season to collect')
    parser.add_argument('--levels', nargs='+', default=['AAA', 'AA', 'A+'],
                       help='MiLB levels to include')

    args = parser.parse_args()

    async with MiLBGameLogCollector(season=args.season, levels=args.levels) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())
