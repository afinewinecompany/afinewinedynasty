"""
Collect ALL MiLB player stats using gameLog API (Fixed Version)

This script uses the proven gameLog API approach with sportId parameter
to collect game-by-game statistics for all MiLB players.

Key difference from previous version:
- Uses gameLog API directly (stats already aggregated)
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

    def __init__(self, season: int, levels: List[str]):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.season = season
        self.levels = levels
        self.games_collected = 0
        self.players_processed = 0
        self.players_with_data = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

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
        """Get all teams for a MiLB level."""
        url = f"{self.BASE_URL}/teams?sportId={sport_id}&season={self.season}"
        data = await self.fetch_json(url)

        if not data:
            return []

        return data.get('teams', [])

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

    async def get_player_game_logs(self, player_id: int, sport_id: int) -> List[Dict[str, Any]]:
        """Get game logs for a player at a specific MiLB level."""
        url = f"{self.BASE_URL}/people/{player_id}/stats?stats=gameLog&season={self.season}&group=hitting&sportId={sport_id}"

        data = await self.fetch_json(url)
        if not data:
            return []

        stats = data.get('stats', [])
        if not stats:
            return []

        return stats[0].get('splits', [])

    async def save_game_log(self, player_id: int, game_log: Dict[str, Any], level: str):
        """Save a single game log to database."""
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
                'strikeouts': stat.get('strikeOuts', 0),
                'stolen_bases': stat.get('stolenBases', 0),
                'caught_stealing': stat.get('caughtStealing', 0),
                'hit_by_pitch': stat.get('hitByPitch', 0),
                'sacrifice_flies': stat.get('sacFlies', 0),
                'ground_outs': stat.get('groundOuts', 0),
                'fly_outs': stat.get('flyOuts', 0),
                'on_base_pct': float(stat.get('obp', 0)) if stat.get('obp') else None,
                'slugging_pct': float(stat.get('slg', 0)) if stat.get('slg') else None,
                'ops': float(stat.get('ops', 0)) if stat.get('ops') else None,
                'data_source': 'mlb_stats_api_gamelog'
            }

            async with engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO milb_game_logs (
                        prospect_id, mlb_player_id, season, game_pk, game_date, level, game_type,
                        team_id, opponent_id, games_played, plate_appearances, at_bats, runs, hits,
                        doubles, triples, home_runs, rbi, walks, strikeouts, stolen_bases,
                        caught_stealing, hit_by_pitch, sacrifice_flies, ground_outs, fly_outs,
                        on_base_pct, slugging_pct, ops, data_source
                    ) VALUES (
                        :prospect_id, :mlb_player_id, :season, :game_pk, :game_date, :level, :game_type,
                        :team_id, :opponent_id, :games_played, :plate_appearances, :at_bats, :runs, :hits,
                        :doubles, :triples, :home_runs, :rbi, :walks, :strikeouts, :stolen_bases,
                        :caught_stealing, :hit_by_pitch, :sacrifice_flies, :ground_outs, :fly_outs,
                        :on_base_pct, :slugging_pct, :ops, :data_source
                    )
                    ON CONFLICT (game_pk, mlb_player_id) DO NOTHING
                """), record)

            self.games_collected += 1
            return True

        except Exception as e:
            logger.error(f"Error saving game log: {str(e)}")
            return False

    async def process_player(self, player: Dict[str, Any]):
        """Process a single player - get all their game logs."""
        player_id = player['player_id']
        self.players_processed += 1

        level_map = {v: k for k, v in self.MILB_SPORT_IDS.items()}
        total_games = 0

        # Check each level
        for level in self.levels:
            sport_id = level_map.get(level)
            if not sport_id:
                continue

            game_logs = await self.get_player_game_logs(player_id, sport_id)

            for game_log in game_logs:
                success = await self.save_game_log(player_id, game_log, level)
                if success:
                    total_games += 1

        if total_games > 0:
            self.players_with_data += 1
            logger.info(f"  [{self.players_processed}/{len(self.all_players)}] Player {player_id}: {total_games} games saved")

        # Progress update
        if self.players_processed % 50 == 0:
            logger.info(f"\nProgress: {self.players_processed}/{len(self.all_players)} players")
            logger.info(f"  Players with data: {self.players_with_data}")
            logger.info(f"  Total games collected: {self.games_collected}\n")

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
        logger.info(f"Total players processed: {self.players_processed}")
        logger.info(f"Players with game data: {self.players_with_data}")
        logger.info(f"Total games collected: {self.games_collected}")
        logger.info(f"Average games/player: {self.games_collected/max(self.players_with_data,1):.1f}")


async def main():
    parser = argparse.ArgumentParser(description='Collect ALL MiLB game logs using gameLog API')
    parser.add_argument('--season', type=int, default=2024, help='Season to collect')
    parser.add_argument('--levels', nargs='+', default=['AAA', 'AA', 'A+'],
                       help='MiLB levels to include')

    args = parser.parse_args()

    async with MiLBGameLogCollector(season=args.season, levels=args.levels) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())
