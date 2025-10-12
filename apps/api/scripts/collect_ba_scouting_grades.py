"""
Collect Baseball America Scouting Grades for MiLB Players

This script:
1. Gets all unique MLB player IDs from milb_game_logs
2. Fetches player names from MLB Stats API
3. Searches Baseball America for each player
4. Scrapes scouting grades (Hit/Power/Run/Field/Arm, OFP, etc.)
5. Stores in ba_scouting_grades table

Usage:
    python collect_ba_scouting_grades.py
"""

import argparse
import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup
from sqlalchemy import text

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BAScoringGradesCollector:
    """Collect Baseball America scouting grades for MiLB players."""

    MLB_API_URL = "https://statsapi.mlb.com/api/v1"
    BA_BASE_URL = "https://www.baseballamerica.com"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.request_delay = 1.0  # Be respectful to BA servers
        self.grades_collected = 0
        self.players_processed = 0
        self.players_not_found = 0

    async def create_session(self):
        """Create aiohttp session with proper headers."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self.session = aiohttp.ClientSession(headers=headers)

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
                    logger.warning(f"Failed to fetch {url}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML from URL with error handling."""
        try:
            await asyncio.sleep(self.request_delay)
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Failed to fetch {url}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def get_player_name(self, mlb_player_id: int) -> Optional[str]:
        """Get player name from MLB Stats API."""
        url = f"{self.MLB_API_URL}/people/{mlb_player_id}"
        data = await self.fetch_json(url)

        if data and data.get('people'):
            player = data['people'][0]
            return player.get('fullName')
        return None

    async def search_ba_player(self, player_name: str, mlb_player_id: int) -> Optional[str]:
        """
        Search Baseball America for player and return BA player ID.

        Strategy:
        1. Try direct URL construction from name
        2. Search BA site if needed
        """
        # Try common BA URL patterns
        name_slug = player_name.lower().replace(' ', '-').replace('.', '').replace("'", '')

        # We don't know the BA ID, so we'll need to search
        # For now, try a search approach or use MLB player ID in image URL pattern
        # BA pages have MLB player IDs in image URLs like: img.mlbstatic.com/mlb-photos/image/upload/.../{mlb_id}.jpg

        # Try searching BA's player directory (this may not work perfectly)
        search_url = f"{self.BA_BASE_URL}/players/"

        # For now, we'll return None and rely on manual mapping or different approach
        # The challenge is BA uses their own IDs and we need a mapping
        return None

    async def scrape_ba_grades(self, ba_player_url: str, mlb_player_id: int) -> Optional[Dict[str, Any]]:
        """
        Scrape scouting grades from Baseball America player page.

        Returns dict with:
        - hit_grade, power_grade, run_grade, field_grade, arm_grade (current)
        - ofp (overall future potential)
        - ba_grade, ba_risk
        - scouting_report (text)
        - draft_year, draft_round, draft_pick
        """
        html = await self.fetch_html(ba_player_url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        grades_data = {
            'mlb_player_id': mlb_player_id,
            'ba_player_url': ba_player_url,
            'scraped_at': datetime.utcnow()
        }

        # Extract MLB player ID from page to verify match
        # Look for MLB player ID in image URLs or data attributes
        img_tags = soup.find_all('img')
        for img in img_tags:
            src = img.get('src', '')
            if 'mlbstatic.com' in src or 'mlb-photos' in src:
                # Try to extract player ID from URL
                match = re.search(r'/(\d{6,7})\.', src)
                if match:
                    found_mlb_id = int(match.group(1))
                    grades_data['mlb_player_id_verified'] = found_mlb_id
                    if found_mlb_id != mlb_player_id:
                        logger.warning(f"MLB ID mismatch: expected {mlb_player_id}, found {found_mlb_id}")
                    break

        # Extract scouting grades
        # Look for grade patterns like "Hit: 50", "Power: 60", etc.
        grade_pattern = re.compile(r'(Hit|Power|Run|Field|Arm):\s*(\d{2})')

        text_content = soup.get_text()
        for match in grade_pattern.finditer(text_content):
            tool = match.group(1).lower()
            grade = int(match.group(2))
            grades_data[f'{tool}_grade'] = grade

        # Extract BA Grade and Risk (e.g., "60/Extreme", "70/High")
        ba_grade_pattern = re.compile(r'BA Grade:\s*(\d{2})/(\w+)')
        match = ba_grade_pattern.search(text_content)
        if match:
            grades_data['ba_grade'] = int(match.group(1))
            grades_data['ba_risk'] = match.group(2)

        # Extract OFP (Overall Future Potential)
        ofp_pattern = re.compile(r'OFP:\s*(\d{2})')
        match = ofp_pattern.search(text_content)
        if match:
            grades_data['ofp'] = int(match.group(1))

        # Extract draft info
        draft_pattern = re.compile(r'(\d{4})\s+MLB\s+Draft.*?(\d+)(?:st|nd|rd|th)\s+overall')
        match = draft_pattern.search(text_content)
        if match:
            grades_data['draft_year'] = int(match.group(1))
            grades_data['draft_pick'] = int(match.group(2))

        # Extract scouting report text
        # Look for report sections
        report_section = soup.find('div', class_=re.compile(r'report|scouting|evaluation', re.I))
        if report_section:
            grades_data['scouting_report'] = report_section.get_text(strip=True)

        return grades_data if len(grades_data) > 3 else None  # Must have more than just metadata

    async def save_grades(self, grades_data: Dict[str, Any]):
        """Save scouting grades to database."""
        try:
            async with engine.begin() as conn:
                # Check if table exists, create if not
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ba_scouting_grades (
                        id SERIAL PRIMARY KEY,
                        mlb_player_id INTEGER NOT NULL,
                        ba_player_url VARCHAR(500),
                        mlb_player_id_verified INTEGER,
                        hit_grade INTEGER,
                        power_grade INTEGER,
                        run_grade INTEGER,
                        field_grade INTEGER,
                        arm_grade INTEGER,
                        ofp INTEGER,
                        ba_grade INTEGER,
                        ba_risk VARCHAR(50),
                        draft_year INTEGER,
                        draft_round INTEGER,
                        draft_pick INTEGER,
                        scouting_report TEXT,
                        scraped_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(mlb_player_id, scraped_at)
                    )
                """))

                # Insert grades
                await conn.execute(text("""
                    INSERT INTO ba_scouting_grades (
                        mlb_player_id, ba_player_url, mlb_player_id_verified,
                        hit_grade, power_grade, run_grade, field_grade, arm_grade,
                        ofp, ba_grade, ba_risk,
                        draft_year, draft_round, draft_pick,
                        scouting_report, scraped_at
                    ) VALUES (
                        :mlb_player_id, :ba_player_url, :mlb_player_id_verified,
                        :hit_grade, :power_grade, :run_grade, :field_grade, :arm_grade,
                        :ofp, :ba_grade, :ba_risk,
                        :draft_year, :draft_round, :draft_pick,
                        :scouting_report, :scraped_at
                    )
                    ON CONFLICT (mlb_player_id, scraped_at) DO NOTHING
                """), grades_data)

                self.grades_collected += 1

        except Exception as e:
            logger.error(f"Error saving grades for player {grades_data.get('mlb_player_id')}: {e}")

    async def get_milb_players(self) -> List[int]:
        """Get unique MLB player IDs from milb_game_logs."""
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT DISTINCT mlb_player_id, COUNT(*) as games
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                AND data_source = 'mlb_stats_api_gamelog'
                GROUP BY mlb_player_id
                ORDER BY games DESC
            """))

            players = [row[0] for row in result.fetchall()]
            logger.info(f"Found {len(players)} unique MiLB players to lookup")
            return players

    async def process_player(self, mlb_player_id: int):
        """Process a single player - get name, search BA, scrape grades."""
        self.players_processed += 1

        # Get player name from MLB API
        player_name = await self.get_player_name(mlb_player_id)
        if not player_name:
            logger.warning(f"Could not get name for MLB ID {mlb_player_id}")
            return

        logger.info(f"[{self.players_processed}] Processing: {player_name} (MLB ID: {mlb_player_id})")

        # For now, we'll use a known BA URL pattern to test
        # In production, you'd need a mapping of MLB ID -> BA ID
        # or implement a search function

        # Test with Konnor Griffin as example
        if mlb_player_id == 804606:
            ba_url = "https://www.baseballamerica.com/players/1500861-konnor-griffin/"
            grades = await self.scrape_ba_grades(ba_url, mlb_player_id)

            if grades:
                logger.info(f"  Found grades: Hit={grades.get('hit_grade')}, Power={grades.get('power_grade')}, "
                          f"Run={grades.get('run_grade')}, Field={grades.get('field_grade')}, Arm={grades.get('arm_grade')}")
                await self.save_grades(grades)
            else:
                logger.warning(f"  No grades found")
                self.players_not_found += 1
        else:
            # For other players, we need BA player IDs
            # This would require either:
            # 1. Manual mapping table
            # 2. BA search API
            # 3. Web scraping BA's player search
            self.players_not_found += 1

        if self.players_processed % 10 == 0:
            logger.info(f"Progress: {self.players_processed} processed, {self.grades_collected} grades collected, "
                       f"{self.players_not_found} not found")

    async def collect_all_grades(self):
        """Main collection loop."""
        logger.info("="*80)
        logger.info("Baseball America Scouting Grades Collection")
        logger.info("="*80)

        # Get all MiLB players
        players = await self.get_milb_players()

        logger.info(f"\nProcessing {len(players)} players...")

        # Process each player
        for player_id in players[:100]:  # Limit to first 100 for testing
            await self.process_player(player_id)

        logger.info("="*80)
        logger.info(f"Collection complete!")
        logger.info(f"  Total processed: {self.players_processed}")
        logger.info(f"  Grades collected: {self.grades_collected}")
        logger.info(f"  Players not found: {self.players_not_found}")
        logger.info("="*80)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Collect Baseball America scouting grades')
    parser.add_argument('--limit', type=int, help='Limit number of players to process')
    args = parser.parse_args()

    collector = BAScoringGradesCollector()

    try:
        await collector.create_session()
        await collector.collect_all_grades()
    finally:
        await collector.close_session()


if __name__ == "__main__":
    asyncio.run(main())
