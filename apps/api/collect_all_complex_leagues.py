"""
Collect ALL Complex League (ACL, FCL, DSL) data for multiple seasons

This script collects complex league data across multiple years efficiently.
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
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
    """Collect MiLB game logs for Complex Leagues across multiple seasons."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    # Sports ID 16 contains the complex leagues
    COMPLEX_SPORTS_ID = 16

    def __init__(self, seasons: List[int]):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 0.2  # Faster rate to process more data
        self.seasons = seasons
        self.complex_teams_by_season = {}
        self.stats_by_season = {}
        # Track existing data across all seasons
        self.existing_player_seasons = set()  # Set of (player_id, season) tuples

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
        """Load existing complex league data for all target seasons."""
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text("""
                    SELECT DISTINCT mlb_player_id, season
                    FROM milb_game_logs
                    WHERE season = ANY(:seasons)
                    AND (team LIKE '%ACL%' OR team LIKE '%FCL%' OR team LIKE '%DSL%' OR level = 'Complex')
                """), {"seasons": self.seasons})

                self.existing_player_seasons = {(row[0], row[1]) for row in result}
                logger.info(f"Found {len(self.existing_player_seasons)} existing player-season combinations with complex league data")

                # Show breakdown by season
                for season in self.seasons:
                    count = len([ps for ps in self.existing_player_seasons if ps[1] == season])
                    logger.info(f"  {season}: {count} players with existing data")

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

    async def find_complex_teams_for_season(self, season: int) -> List[tuple]:
        """Find all complex league teams for a specific season."""
        logger.info(f"\nSearching for complex league teams in {season}...")

        data = await self.fetch_json("teams", {
            "season": season,
            "sportId": self.COMPLEX_SPORTS_ID
        })

        if not data or "teams" not in data:
            logger.warning(f"  No teams found for {season}")
            return []

        teams = data["teams"]
        complex_teams = []

        for team in teams:
            team_name = team.get('name', '')
            team_id = team.get('id')

            # Check if this is a complex league team
            if any(league in team_name for league in ['ACL', 'FCL', 'DSL', 'Complex', 'Arizona Complex', 'Florida Complex', 'Dominican Summer']):
                complex_teams.append((team_id, team_name))

        # Log summary by league type
        acl_teams = [t for t in complex_teams if 'ACL' in t[1]]
        fcl_teams = [t for t in complex_teams if 'FCL' in t[1]]
        dsl_teams = [t for t in complex_teams if 'DSL' in t[1]]

        logger.info(f"  Found {len(complex_teams)} complex league teams:")
        logger.info(f"    - ACL: {len(acl_teams)} teams")
        logger.info(f"    - FCL: {len(fcl_teams)} teams")
        logger.info(f"    - DSL: {len(dsl_teams)} teams")

        return complex_teams

    async def get_roster(self, team_id: int, season: int) -> List[Dict]:
        """Get roster for a specific team and season."""
        for roster_type in ["fullSeason", "active", "40Man", "fullRoster"]:
            data = await self.fetch_json(f"teams/{team_id}/roster", {
                "season": season,
                "rosterType": roster_type
            })

            if data and "roster" in data and len(data["roster"]) > 0:
                return data["roster"]

        return []

    async def collect_player_gamelogs(self, player_id: int, season: int, position_type: str) -> int:
        """Collect game logs for a single player in a specific season."""
        # Skip if we already have this player-season combination
        if (player_id, season) in self.existing_player_seasons:
            return 0

        # Determine stat group
        group = "hitting" if position_type != "Pitcher" else "pitching"

        data = await self.fetch_json(f"people/{player_id}/stats", {
            "stats": "gameLog",
            "season": season,
            "group": group,
            "sportId": self.COMPLEX_SPORTS_ID
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
                game_team_name = team_info.get("name", "")

                # Only process if this is a complex league game
                if not any(league in game_team_name for league in ['ACL', 'FCL', 'DSL', 'Complex']):
                    continue

                # Convert date string to date object
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
                    "season": season,
                    "game_date": game_date,
                    "game_pk": game_info.get("gamePk"),
                    "team_id": team_info.get("id"),
                    "team": game_team_name,
                    "level": "Complex",
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
                    return

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
            # Log error but continue processing
            logger.debug(f"Error storing game log: {e}")

    async def collect_season(self, season: int):
        """Collect all complex league data for a specific season."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {season} Season")
        logger.info(f"{'='*60}")

        # Find complex league teams for this season
        complex_teams = await self.find_complex_teams_for_season(season)
        self.complex_teams_by_season[season] = complex_teams

        if not complex_teams:
            logger.warning(f"No complex league teams found for {season}")
            return

        season_stats = {
            'teams_processed': 0,
            'players_processed': 0,
            'new_players': 0,
            'games_collected': 0
        }

        # Process each team
        for team_id, team_name in complex_teams:
            logger.info(f"\n  Processing: {team_name}")

            # Get roster
            roster = await self.get_roster(team_id, season)

            if not roster:
                logger.debug(f"    No roster found")
                continue

            season_stats['teams_processed'] += 1
            team_new_players = 0

            # Process each player
            for player_entry in roster:
                person = player_entry.get("person", {})
                player_id = person.get("id")
                player_name = person.get("fullName", "Unknown")
                position = player_entry.get("position", {}).get("type", "Unknown")

                if not player_id:
                    continue

                season_stats['players_processed'] += 1

                # Check if we need to collect this player-season
                if (player_id, season) not in self.existing_player_seasons:
                    games = await self.collect_player_gamelogs(player_id, season, position)

                    if games > 0:
                        team_new_players += 1
                        season_stats['new_players'] += 1
                        season_stats['games_collected'] += games
                        self.existing_player_seasons.add((player_id, season))
                        logger.info(f"    ✓ {player_name}: {games} games")

            if team_new_players > 0:
                logger.info(f"    Added {team_new_players} new players from {team_name}")

        self.stats_by_season[season] = season_stats

        logger.info(f"\n{season} Season Summary:")
        logger.info(f"  Teams processed: {season_stats['teams_processed']}")
        logger.info(f"  Players checked: {season_stats['players_processed']}")
        logger.info(f"  New players added: {season_stats['new_players']}")
        logger.info(f"  Games collected: {season_stats['games_collected']}")

    async def collect_all(self):
        """Main collection process for all seasons."""
        logger.info(f"\n{'='*70}")
        logger.info(f"Complex League Data Collection")
        logger.info(f"Seasons: {', '.join(map(str, self.seasons))}")
        logger.info(f"{'='*70}")

        # Process each season
        for season in self.seasons:
            await self.collect_season(season)

        # Final summary
        logger.info(f"\n{'='*70}")
        logger.info(f"COLLECTION COMPLETE")
        logger.info(f"{'='*70}")

        total_teams = sum(len(teams) for teams in self.complex_teams_by_season.values())
        total_new_players = sum(stats['new_players'] for stats in self.stats_by_season.values())
        total_games = sum(stats['games_collected'] for stats in self.stats_by_season.values())

        logger.info(f"\nOverall Summary:")
        logger.info(f"  Seasons processed: {len(self.seasons)}")
        logger.info(f"  Complex league teams found: {total_teams}")
        logger.info(f"  New players with data: {total_new_players}")
        logger.info(f"  Total games collected: {total_games}")

        logger.info(f"\nBy Season:")
        for season in self.seasons:
            if season in self.stats_by_season:
                stats = self.stats_by_season[season]
                logger.info(f"  {season}: {stats['new_players']} players, {stats['games_collected']} games")


async def main():
    parser = argparse.ArgumentParser(
        description='Collect Complex League (ACL, FCL, DSL) data for multiple seasons'
    )
    parser.add_argument('--seasons', nargs='+', type=int,
                       default=[2021, 2022, 2023, 2024, 2025],
                       help='Seasons to collect (default: 2021-2025)')
    parser.add_argument('--season', type=int, help='Single season to collect')

    args = parser.parse_args()

    # Handle single season or multiple seasons
    if args.season:
        seasons = [args.season]
    else:
        seasons = args.seasons

    async with ComplexLeagueCollector(seasons=seasons) as collector:
        await collector.collect_all()


if __name__ == "__main__":
    asyncio.run(main())