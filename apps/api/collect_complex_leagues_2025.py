"""
Collect MiLB data for Complex Leagues (ACL, FCL, DSL) for 2025 season

This script explores different sports IDs to find complex league data
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


class ComplexLeagueCollector:
    """Collect MiLB game logs for Complex Leagues."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # Try multiple sports IDs that might contain complex leagues
    SPORTS_TO_CHECK = {
        16: "Rookie+",
        15: "Rookie",
        17: "Winter/Instructional",
        5442: "DSL",  # Sometimes DSL has its own ID
        5443: "Complex",  # Generic complex league ID
        130: "Spring Training",  # Sometimes complex games are categorized here
        131: "Exhibition",
        132: "Extended Spring"
    }

    def __init__(self, season: int):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.3
        self.season = season
        self.complex_teams_found = []
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
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def explore_sports_ids(self):
        """Explore all sports IDs to find complex leagues."""
        logger.info("\n" + "="*60)
        logger.info("Exploring sports IDs for complex leagues...")
        logger.info("="*60)

        for sport_id, description in self.SPORTS_TO_CHECK.items():
            logger.info(f"\nChecking sports ID {sport_id} ({description})...")

            data = await self.fetch_json("teams", {
                "season": self.season,
                "sportId": sport_id
            })

            if not data or "teams" not in data:
                logger.info(f"  No teams found")
                continue

            teams = data["teams"]
            logger.info(f"  Found {len(teams)} teams")

            # Check for complex league teams
            complex_teams = []
            for team in teams:
                team_name = team.get('name', '')
                team_id = team.get('id')

                # Check if this is a complex league team
                if any(league in team_name for league in ['ACL', 'FCL', 'DSL', 'Complex', 'Arizona Complex', 'Florida Complex', 'Dominican Summer']):
                    complex_teams.append((team_id, team_name))
                    logger.info(f"    ✓ Found complex league team: {team_name} (ID: {team_id})")

            if complex_teams:
                self.complex_teams_found.extend([(sport_id, tid, name) for tid, name in complex_teams])

    async def get_roster(self, team_id: int) -> List[Dict]:
        """Get roster for a specific team."""
        # Try multiple roster types
        for roster_type in ["fullSeason", "active", "40Man", "fullRoster"]:
            data = await self.fetch_json(f"teams/{team_id}/roster", {
                "season": self.season,
                "rosterType": roster_type
            })

            if data and "roster" in data and len(data["roster"]) > 0:
                return data["roster"]

        return []

    async def collect_player_gamelogs(self, player_id: int, sport_id: int, team_name: str, position_type: str) -> int:
        """Collect game logs for a single player."""
        if player_id in self.existing_players:
            return 0

        # Determine stat group
        group = "hitting" if position_type != "Pitcher" else "pitching"

        data = await self.fetch_json(f"people/{player_id}/stats", {
            "stats": "gameLog",
            "season": self.season,
            "group": group,
            "sportId": sport_id
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

                # Get team name from game
                game_team_name = team_info.get("name", "")

                # Only process if this is a complex league game
                if not any(league in game_team_name for league in ['ACL', 'FCL', 'DSL', 'Complex']):
                    continue

                # Convert date string to date object
                from datetime import datetime
                game_date_str = game.get("date")
                game_date = None
                if game_date_str:
                    try:
                        game_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()
                    except:
                        pass

                # Prepare record
                record = {
                    "mlb_player_id": player_id,
                    "season": self.season,
                    "game_date": game_date,
                    "game_pk": game_info.get("gamePk"),
                    "team_id": team_info.get("id"),
                    "team": game_team_name,  # Use the actual team name from the game
                    "level": "Complex",  # Mark as complex league
                    "opponent_id": game.get("opponent", {}).get("id"),
                    "opponent": game.get("opponent", {}).get("name"),
                    "is_home": game.get("isHome", False),
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
                        "batting_avg": safe_float(game_data.get("avg")),
                        "on_base_pct": safe_float(game_data.get("obp")),
                        "slugging_pct": safe_float(game_data.get("slg")),
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
                logger.info(f"      Added {game_team_name} game on {game.get('date')}")

        return games_added

    async def store_game_log(self, record: Dict, stat_type: str):
        """Store game log in database."""
        try:
            async with engine.begin() as conn:
                # Check if record already exists
                result = await conn.execute(text("""
                    SELECT 1 FROM milb_game_logs
                    WHERE mlb_player_id = :mlb_player_id
                    AND game_pk = :game_pk
                    LIMIT 1
                """), {
                    "mlb_player_id": record["mlb_player_id"],
                    "game_pk": record["game_pk"]
                })

                if result.fetchone():
                    return  # Already exists

                # Insert new record - only include non-null columns
                columns = []
                values = {}
                for k, v in record.items():
                    if v is not None:
                        columns.append(k)
                        values[k] = v

                if columns:
                    columns_str = ", ".join(columns)
                    placeholders = ", ".join([f":{k}" for k in columns])

                    await conn.execute(text(f"""
                        INSERT INTO milb_game_logs ({columns_str})
                        VALUES ({placeholders})
                    """), values)

        except Exception as e:
            logger.error(f"Error storing game log: {e}")

    async def collect_all(self):
        """Main collection process."""
        # First, explore sports IDs to find complex league teams
        await self.explore_sports_ids()

        if not self.complex_teams_found:
            logger.warning("\nNo complex league teams found in any sports ID!")
            return

        logger.info(f"\n{'='*60}")
        logger.info(f"Found {len(self.complex_teams_found)} complex league teams")
        logger.info(f"Starting data collection...")
        logger.info(f"{'='*60}\n")

        for sport_id, team_id, team_name in self.complex_teams_found:
            logger.info(f"\nProcessing: {team_name} (Sport ID: {sport_id}, Team ID: {team_id})")

            # Get roster
            roster = await self.get_roster(team_id)

            if not roster:
                logger.warning(f"  No roster found")
                continue

            logger.info(f"  Found {len(roster)} players on roster")

            # Collect data for each player
            new_players_this_team = 0
            for player_entry in roster:
                person = player_entry.get("person", {})
                player_id = person.get("id")
                player_name = person.get("fullName", "Unknown")
                position = player_entry.get("position", {}).get("type", "Unknown")

                if not player_id:
                    continue

                # Check if we already have this player's data
                if player_id not in self.existing_players:
                    games = await self.collect_player_gamelogs(player_id, sport_id, team_name, position)

                    if games > 0:
                        new_players_this_team += 1
                        self.players_collected += 1  # Also update total count
                        self.games_collected += games
                        self.existing_players.add(player_id)
                        logger.info(f"    ✓ {player_name}: {games} complex league games collected")

            if new_players_this_team > 0:
                logger.info(f"  Collected data for {new_players_this_team} new players from {team_name}")

        logger.info(f"\n{'='*60}")
        logger.info(f"Collection Complete!")
        logger.info(f"  Complex league teams found: {len(self.complex_teams_found)}")
        logger.info(f"  New players with data: {self.players_collected}")
        logger.info(f"  Total games collected: {self.games_collected}")
        logger.info(f"{'='*60}\n")


async def main():
    parser = argparse.ArgumentParser(
        description='Collect MiLB data for Complex Leagues (ACL, FCL, DSL)'
    )
    parser.add_argument('--season', type=int, default=2025,
                       help='Season to collect (default: 2025)')

    args = parser.parse_args()

    async with ComplexLeagueCollector(season=args.season) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())