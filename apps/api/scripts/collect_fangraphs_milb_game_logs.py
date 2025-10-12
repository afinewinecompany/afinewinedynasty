"""
Collect MiLB game logs from FanGraphs for prospects.

This script scrapes game-by-game MiLB statistics from FanGraphs player pages
and stores them in the comprehensive milb_game_logs table.

FanGraphs provides detailed MiLB stats at:
https://www.fangraphs.com/players/{player-name}-{fg_id}/game-log?position=ALL&season=2024&type=minors

Usage:
    python collect_fangraphs_milb_game_logs.py --seasons 2024 2023 2022
    python collect_fangraphs_milb_game_logs.py --prospect-id 508 --seasons 2024
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

# Add parent directory to path for imports
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

from app.db.database import get_db_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FanGraphsMiLBCollector:
    """Collect MiLB game logs from FanGraphs."""

    BASE_URL = "https://www.fangraphs.com"
    USER_AGENT = "A Fine Wine Dynasty Bot 1.0 (Research/Educational)"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 3.0  # Be respectful with rate limiting
        self.games_collected = 0
        self.errors = 0

    async def __aenter__(self):
        """Initialize aiohttp session."""
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close session."""
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    def get_prospects_with_fg_ids(self, db, prospect_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get prospects that have FanGraphs IDs."""
        query = text("""
            SELECT
                id as prospect_id,
                name,
                fg_player_id,
                mlb_player_id,
                position
            FROM prospects
            WHERE fg_player_id IS NOT NULL
                AND fg_player_id NOT LIKE 'sa%'  -- Exclude international amateurs
        """)

        if prospect_id:
            query = text("""
                SELECT
                    id as prospect_id,
                    name,
                    fg_player_id,
                    mlb_player_id,
                    position
                FROM prospects
                WHERE id = :prospect_id
                    AND fg_player_id IS NOT NULL
                    AND fg_player_id NOT LIKE 'sa%'
            """)
            result = db.execute(query, {"prospect_id": prospect_id})
        else:
            result = db.execute(query)

        prospects = []
        for row in result:
            prospects.append({
                "prospect_id": row.prospect_id,
                "name": row.name,
                "fg_id": row.fg_player_id,  # Map to fg_id for consistency in code
                "mlb_player_id": row.mlb_player_id,
                "position": row.position
            })

        return prospects

    def format_player_url(self, name: str, fg_id: str) -> str:
        """Format FanGraphs player name for URL."""
        # FanGraphs uses format: firstname-lastname-{fg_id}
        # e.g., jackson-holliday-32050
        name_clean = name.lower().replace("'", "").replace(".", "")
        name_url = "-".join(name_clean.split())
        return f"{name_url}-{fg_id}"

    async def fetch_game_log_page(self, player_url: str, season: int) -> Optional[str]:
        """Fetch game log page HTML from FanGraphs."""
        url = f"{self.BASE_URL}/players/{player_url}/game-log?position=ALL&season={season}&type=minors"

        try:
            await asyncio.sleep(self.request_delay)  # Rate limiting

            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    logger.debug(f"  Successfully fetched {url}")
                    return html
                elif response.status == 404:
                    logger.debug(f"  Page not found: {url}")
                    return None
                else:
                    logger.warning(f"  HTTP {response.status} for {url}")
                    return None

        except Exception as e:
            logger.error(f"  Error fetching {url}: {str(e)}")
            self.errors += 1
            return None

    def parse_game_logs(self, html: str, prospect_id: int, season: int) -> List[Dict[str, Any]]:
        """Parse game log table from FanGraphs HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Find the game log table
            # FanGraphs uses <table class="rgMasterTable" id="GameLogTable">
            table = soup.find('table', {'id': 'GameLogTable'})
            if not table:
                logger.debug("  No game log table found in HTML")
                return []

            # Extract headers
            headers = []
            header_row = table.find('thead')
            if header_row:
                for th in header_row.find_all('th'):
                    headers.append(th.text.strip())

            if not headers:
                logger.warning("  No headers found in game log table")
                return []

            # Parse each game row
            games = []
            tbody = table.find('tbody')
            if not tbody:
                return []

            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < len(headers):
                    continue

                game_data = {}
                for i, header in enumerate(headers):
                    if i < len(cells):
                        value = cells[i].text.strip()
                        game_data[header] = value if value else None

                # Convert to database format
                try:
                    db_record = self.map_to_database_format(game_data, prospect_id, season)
                    if db_record:
                        games.append(db_record)
                except Exception as e:
                    logger.warning(f"  Error mapping game data: {str(e)}")
                    continue

            return games

        except Exception as e:
            logger.error(f"  Error parsing game logs: {str(e)}")
            return []

    def parse_stat(self, value: Any, as_float: bool = False) -> Optional[float]:
        """Parse stat value, handling FanGraphs formatting."""
        if value is None or value == '' or value == '-':
            return None

        # Remove % signs
        if isinstance(value, str):
            value = value.replace('%', '').replace(',', '').strip()

        try:
            if as_float:
                return float(value)
            else:
                # Try int first, fall back to float
                if '.' in str(value):
                    return float(value)
                else:
                    return int(value)
        except (ValueError, TypeError):
            return None

    def map_to_database_format(self, game: Dict[str, Any], prospect_id: int, season: int) -> Optional[Dict[str, Any]]:
        """Map FanGraphs game data to database schema."""
        try:
            # Parse game date
            date_str = game.get('Date', '')
            if not date_str or date_str == '-':
                return None

            try:
                # FanGraphs format: "Jul 15" or "Jul 15, 2024"
                if ',' in date_str:
                    game_date = datetime.strptime(date_str, '%b %d, %Y').date()
                else:
                    # Add year if not present
                    game_date = datetime.strptime(f"{date_str}, {season}", '%b %d, %Y').date()
            except ValueError:
                logger.warning(f"  Could not parse date: {date_str}")
                return None

            # Determine if hitting or pitching stats
            # FanGraphs shows position (C, SS, P, etc.)
            position = game.get('Pos', '')
            is_pitcher = position == 'P'

            # Base record
            record = {
                'prospect_id': prospect_id,
                'season': season,
                'game_date': game_date,
                'game_type': 'R',  # Regular season (FanGraphs doesn't distinguish)
                'data_source': 'fangraphs',
            }

            # Parse hitting stats (if available)
            if not is_pitcher or game.get('AB'):  # Some pitchers have hitting stats
                record.update({
                    'games_played': 1,
                    'at_bats': self.parse_stat(game.get('AB')),
                    'plate_appearances': self.parse_stat(game.get('PA')),
                    'runs': self.parse_stat(game.get('R')),
                    'hits': self.parse_stat(game.get('H')),
                    'doubles': self.parse_stat(game.get('2B')),
                    'triples': self.parse_stat(game.get('3B')),
                    'home_runs': self.parse_stat(game.get('HR')),
                    'rbi': self.parse_stat(game.get('RBI')),
                    'walks': self.parse_stat(game.get('BB')),
                    'strikeouts': self.parse_stat(game.get('SO')),
                    'hit_by_pitch': self.parse_stat(game.get('HBP')),
                    'stolen_bases': self.parse_stat(game.get('SB')),
                    'caught_stealing': self.parse_stat(game.get('CS')),
                    'batting_avg': self.parse_stat(game.get('AVG'), as_float=True),
                    'obp': self.parse_stat(game.get('OBP'), as_float=True),
                    'slg': self.parse_stat(game.get('SLG'), as_float=True),
                    'ops': self.parse_stat(game.get('OPS'), as_float=True),
                })

            # Parse pitching stats (if available)
            if is_pitcher or game.get('IP'):
                record.update({
                    'innings_pitched': self.parse_stat(game.get('IP'), as_float=True),
                    'hits_allowed': self.parse_stat(game.get('H')),
                    'runs_allowed': self.parse_stat(game.get('R')),
                    'earned_runs': self.parse_stat(game.get('ER')),
                    'walks_allowed': self.parse_stat(game.get('BB')),
                    'strikeouts_pitched': self.parse_stat(game.get('SO')),
                    'home_runs_allowed': self.parse_stat(game.get('HR')),
                    'era': self.parse_stat(game.get('ERA'), as_float=True),
                    'whip': self.parse_stat(game.get('WHIP'), as_float=True),
                })

            return record

        except Exception as e:
            logger.error(f"  Error in map_to_database_format: {str(e)}")
            return None

    def save_game_log(self, db, game: Dict[str, Any]) -> bool:
        """Save a single game log to database."""
        try:
            # Build INSERT query dynamically based on available fields
            columns = list(game.keys())
            placeholders = [f":{col}" for col in columns]

            query = text(f"""
                INSERT INTO milb_game_logs ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """)

            db.execute(query, game)
            db.commit()
            return True

        except IntegrityError:
            # Duplicate game - already exists
            db.rollback()
            return False
        except Exception as e:
            logger.error(f"  Error saving game: {str(e)}")
            db.rollback()
            self.errors += 1
            return False

    async def collect_prospect_game_logs(
        self,
        db,
        prospect: Dict[str, Any],
        seasons: List[int]
    ) -> int:
        """Collect all game logs for a prospect across specified seasons."""
        name = prospect['name']
        fg_id = prospect['fg_id']
        prospect_id = prospect['prospect_id']

        logger.info(f"Processing {name} (FG ID: {fg_id})")

        player_url = self.format_player_url(name, fg_id)
        total_games = 0

        for season in seasons:
            logger.info(f"  Fetching {season} game logs...")

            # Fetch HTML
            html = await self.fetch_game_log_page(player_url, season)
            if not html:
                logger.info(f"  No data found for {season}")
                continue

            # Parse games
            games = self.parse_game_logs(html, prospect_id, season)
            logger.info(f"  Found {len(games)} games for {season}")

            # Save to database
            saved = 0
            for game in games:
                if self.save_game_log(db, game):
                    saved += 1

            logger.info(f"  Saved {saved} new games (skipped {len(games) - saved} duplicates)")
            total_games += saved
            self.games_collected += saved

        return total_games


async def main():
    """Main collection function."""
    parser = argparse.ArgumentParser(
        description="Collect MiLB game logs from FanGraphs"
    )
    parser.add_argument(
        '--seasons',
        type=int,
        nargs='+',
        default=[2024, 2023],
        help='Seasons to collect (e.g., 2024 2023 2022)'
    )
    parser.add_argument(
        '--prospect-id',
        type=int,
        help='Collect for specific prospect ID only (for testing)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of prospects to process (for testing)'
    )

    args = parser.parse_args()

    logger.info("Starting FanGraphs MiLB game log collection")
    logger.info(f"Seasons: {args.seasons}")

    # Get database connection
    db = get_db_sync()

    try:
        # Initialize collector
        async with FanGraphsMiLBCollector() as collector:
            # Get prospects
            prospects = collector.get_prospects_with_fg_ids(db, args.prospect_id)

            if args.limit:
                prospects = prospects[:args.limit]

            logger.info(f"Found {len(prospects)} prospects with FanGraphs IDs")

            if not prospects:
                logger.warning("No prospects found with FanGraphs IDs")
                return

            # Process each prospect
            start_time = time.time()

            for i, prospect in enumerate(prospects, 1):
                logger.info(f"[{i}/{len(prospects)}] Processing {prospect['name']}")

                try:
                    games_collected = await collector.collect_prospect_game_logs(
                        db,
                        prospect,
                        args.seasons
                    )

                    if games_collected > 0:
                        logger.info(f"  ✓ Collected {games_collected} total games")
                    else:
                        logger.info(f"  No new games found")

                except Exception as e:
                    logger.error(f"  Error processing {prospect['name']}: {str(e)}")
                    collector.errors += 1
                    continue

            # Summary
            elapsed = time.time() - start_time
            logger.info("")
            logger.info("Collection complete!")
            logger.info(f"Total games collected: {collector.games_collected}")
            logger.info(f"Errors: {collector.errors}")
            logger.info(f"Time elapsed: {elapsed:.1f}s")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
