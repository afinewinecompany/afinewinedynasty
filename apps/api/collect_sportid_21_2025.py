"""
Collect MiLB data specifically for Sports ID 21 (Complex/Rookie leagues) for 2025 season

This script targets sports ID 21 which typically includes:
- Complex leagues (ACL, FCL, DSL)
- Extended Spring Training games
- Other rookie-level competitions
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
        if value in ('.---', '-.--', '∞', 'Infinity', ''):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    return None


class SportId21Collector:
    """Collect MiLB game logs for Sports ID 21."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    def __init__(self, season: int):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.5
        self.season = season
        self.sport_id = 21  # Target sports ID
        self.players_collected = 0
        self.games_collected = 0
        self.existing_players = set()

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        await self.load_existing_data()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def load_existing_data(self):
        """Load list of players we've already collected data for this season."""
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT DISTINCT mlb_player_id
                    FROM milb_game_logs
                    WHERE season = :season
                """), {"season": self.season})

                self.existing_players = {row[0] for row in result}
                logger.info(f"Found {len(self.existing_players)} players with existing {self.season} data")
        except Exception as e:
            logger.error(f"Error loading existing data: {e}")

    async def fetch_json(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """Fetch JSON from MLB API."""
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"API returned status {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_teams_for_sport(self) -> List[Dict]:
        """Get all teams for sports ID 21."""
        data = await self.fetch_json("teams", {
            "season": self.season,
            "sportId": self.sport_id
        })

        if not data or "teams" not in data:
            return []

        teams = data["teams"]
        logger.info(f"Found {len(teams)} teams for sports ID {self.sport_id} in {self.season}")
        for team in teams[:5]:  # Show first 5 teams
            logger.info(f"  - {team.get('name', 'Unknown')} (ID: {team.get('id')})")

        return teams

    async def get_roster(self, team_id: int) -> List[Dict]:
        """Get roster for a specific team."""
        data = await self.fetch_json(f"teams/{team_id}/roster", {
            "season": self.season,
            "rosterType": "fullSeason"
        })

        if not data or "roster" not in data:
            return []

        return data["roster"]

    async def collect_player_gamelogs(self, player_id: int, position_type: str) -> int:
        """Collect game logs for a single player."""
        if player_id in self.existing_players:
            return 0

        # Determine stat group
        group = "hitting" if position_type != "Pitcher" else "pitching"

        data = await self.fetch_json(f"people/{player_id}/stats", {
            "stats": "gameLog",
            "season": self.season,
            "group": group,
            "sportId": self.sport_id
        })

        if not data or "stats" not in data:
            return 0

        games_added = 0

        for stat_group in data["stats"]:
            if stat_group.get("type", {}).get("displayName") != "gameLog":
                continue

            splits = stat_group.get("splits", [])

            for game in splits:
                game_data = game.get("stat", {})
                game_info = game.get("game", {})
                team_info = game.get("team", {})

                # Prepare record
                record = {
                    "mlb_player_id": player_id,
                    "season": self.season,
                    "game_date": game.get("date"),
                    "game_id": game_info.get("gamePk"),
                    "team_id": team_info.get("id"),
                    "team_name": team_info.get("name"),
                    "level": "Complex",  # Sports ID 21 is complex/rookie leagues
                    "opponent_id": game.get("opponent", {}).get("id"),
                    "opponent_name": game.get("opponent", {}).get("name"),
                    "is_home": game.get("isHome", False),
                    "position": position_type,
                }

                if group == "hitting":
                    # Add hitting stats
                    record.update({
                        "games_played": 1,
                        "plate_appearances": game_data.get("plateAppearances", 0),
                        "at_bats": game_data.get("atBats", 0),
                        "runs": game_data.get("runs", 0),
                        "hits": game_data.get("hits", 0),
                        "doubles": game_data.get("doubles", 0),
                        "triples": game_data.get("triples", 0),
                        "home_runs": game_data.get("homeRuns", 0),
                        "rbi": game_data.get("rbi", 0),
                        "stolen_bases": game_data.get("stolenBases", 0),
                        "caught_stealing": game_data.get("caughtStealing", 0),
                        "walks": game_data.get("baseOnBalls", 0),
                        "strikeouts": game_data.get("strikeOuts", 0),
                        "hit_by_pitch": game_data.get("hitByPitch", 0),
                        "sacrifice_hits": game_data.get("sacBunts", 0),
                        "sacrifice_flies": game_data.get("sacFlies", 0),
                        "batting_average": safe_float(game_data.get("avg")),
                        "on_base_percentage": safe_float(game_data.get("obp")),
                        "slugging_percentage": safe_float(game_data.get("slg")),
                        "ops": safe_float(game_data.get("ops")),
                    })
                else:
                    # Add pitching stats
                    record.update({
                        "games_pitched": 1,
                        "games_started": game_data.get("gamesStarted", 0),
                        "wins": game_data.get("wins", 0),
                        "losses": game_data.get("losses", 0),
                        "saves": game_data.get("saves", 0),
                        "holds": game_data.get("holds", 0),
                        "innings_pitched": safe_float(game_data.get("inningsPitched")),
                        "hits_allowed": game_data.get("hits", 0),
                        "runs_allowed": game_data.get("runs", 0),
                        "earned_runs": game_data.get("earnedRuns", 0),
                        "home_runs_allowed": game_data.get("homeRuns", 0),
                        "walks_allowed": game_data.get("baseOnBalls", 0),
                        "strikeouts_pitched": game_data.get("strikeOuts", 0),
                        "era": safe_float(game_data.get("era")),
                        "whip": safe_float(game_data.get("whip")),
                    })

                # Store the record
                await self.store_game_log(record, group)
                games_added += 1

        return games_added

    async def store_game_log(self, record: Dict, stat_type: str):
        """Store game log in database."""
        try:
            async with engine.begin() as conn:
                # Check if record already exists
                result = await conn.execute(text("""
                    SELECT 1 FROM milb_game_logs
                    WHERE mlb_player_id = :mlb_player_id
                    AND game_id = :game_id
                    LIMIT 1
                """), {
                    "mlb_player_id": record["mlb_player_id"],
                    "game_id": record["game_id"]
                })

                if result.fetchone():
                    return  # Already exists

                # Insert new record
                columns = ", ".join(record.keys())
                placeholders = ", ".join([f":{k}" for k in record.keys()])

                await conn.execute(text(f"""
                    INSERT INTO milb_game_logs ({columns})
                    VALUES ({placeholders})
                """), record)

        except Exception as e:
            logger.error(f"Error storing game log: {e}")

    async def collect_all(self):
        """Main collection process."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Starting Sports ID 21 collection for {self.season}")
        logger.info(f"{'='*60}\n")

        # Get all teams for sports ID 21
        teams = await self.get_teams_for_sport()

        if not teams:
            logger.warning(f"No teams found for sports ID {self.sport_id} in {self.season}")
            return

        total_players = 0
        new_players = 0

        for team in teams:
            team_id = team.get("id")
            team_name = team.get("name", "Unknown")

            logger.info(f"\nProcessing team: {team_name} (ID: {team_id})")

            # Get roster
            roster = await self.get_roster(team_id)

            if not roster:
                logger.warning(f"  No roster found for {team_name}")
                continue

            logger.info(f"  Found {len(roster)} players")

            # Collect data for each player
            for player_entry in roster:
                person = player_entry.get("person", {})
                player_id = person.get("id")
                player_name = person.get("fullName", "Unknown")
                position = player_entry.get("position", {}).get("type", "Unknown")

                if not player_id:
                    continue

                total_players += 1

                # Check if we already have this player's data
                if player_id not in self.existing_players:
                    games = await self.collect_player_gamelogs(player_id, position)

                    if games > 0:
                        new_players += 1
                        self.games_collected += games
                        self.existing_players.add(player_id)
                        logger.info(f"    ✓ {player_name}: {games} games collected")

                    # Progress update every 10 new players
                    if new_players % 10 == 0:
                        logger.info(f"\n  Progress: {new_players} new players, {self.games_collected} total games")

        logger.info(f"\n{'='*60}")
        logger.info(f"Collection Complete!")
        logger.info(f"  Total players processed: {total_players}")
        logger.info(f"  New players with data: {new_players}")
        logger.info(f"  Total games collected: {self.games_collected}")
        logger.info(f"{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser(
        description='Collect MiLB data for Sports ID 21 (Complex/Rookie leagues)'
    )
    parser.add_argument('--season', type=int, default=2025,
                       help='Season to collect (default: 2025)')

    args = parser.parse_args()

    async with SportId21Collector(season=args.season) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())