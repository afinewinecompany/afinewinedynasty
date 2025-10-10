"""
Collect FanGraphs prospect grades and scouting reports.

FanGraphs provides professional scouting grades on the 20-80 scale:
- Future Value (FV): Overall projection (40=org player, 50=avg, 60=all-star, 70+=superstar)
- Hit Tool: Ability to make contact and hit for average
- Power Tool: Raw power and game power
- Run Tool: Speed and baserunning
- Field Tool: Defensive ability
- Arm Tool: Arm strength and accuracy

API Endpoint: https://www.fangraphs.com/api/prospects/board/prospects-list-combined
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import aiohttp
from sqlalchemy import text
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FanGraphsProspectCollector:
    """Collect FanGraphs prospect grades and rankings."""

    BASE_URL = "https://www.fangraphs.com/api/prospects/board"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.prospects_collected = 0
        self.prospects_updated = 0

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
            await asyncio.sleep(0.25)

    async def fetch_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Fetch JSON from FanGraphs API."""
        try:
            logger.info(f"Fetching: {url}")
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"HTTP {response.status}: {url}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    async def get_prospect_list(self) -> List[Dict[str, Any]]:
        """Fetch complete FanGraphs prospect list with grades."""

        # Working endpoint as of 2025
        url = "https://www.fangraphs.com/api/prospects/team-box/combined"
        params = {
            'curseason': '2025',
            'prevseason': '2024',
            'curreporttermid': '4089',
            'curprelimtermid': '4090',
            'prevtermid': '4064'
        }

        data = await self.fetch_json(url, params)

        if not data:
            logger.error("Could not fetch prospect list from FanGraphs API")
            return []

        # Handle different response formats
        prospects = []

        if isinstance(data, list):
            prospects = data
        elif isinstance(data, dict):
            # Try common keys
            for key in ['prospects', 'data', 'results', 'players', 'board']:
                if key in data:
                    if isinstance(data[key], list):
                        prospects = data[key]
                        break
                    elif isinstance(data[key], dict):
                        # Nested structure - try to find list
                        for nested_key in data[key]:
                            if isinstance(data[key][nested_key], list):
                                prospects = data[key][nested_key]
                                break

            # If still no prospects, the entire dict might be keyed by team
            if not prospects:
                # Check if it's team-keyed data
                for value in data.values():
                    if isinstance(value, list):
                        prospects.extend(value)
                    elif isinstance(value, dict) and 'prospects' in value:
                        if isinstance(value['prospects'], list):
                            prospects.extend(value['prospects'])

        if prospects:
            logger.info(f"Found {len(prospects)} prospects from FanGraphs API")
        else:
            logger.error("No prospects found in API response")
            logger.info(f"Response structure: {list(data.keys()) if isinstance(data, dict) else type(data)}")

        return prospects

    async def create_grades_table(self):
        """Create table for FanGraphs prospect grades."""
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS fangraphs_prospect_grades (
                    id SERIAL PRIMARY KEY,
                    fg_prospect_id INTEGER UNIQUE,
                    fg_player_id INTEGER,
                    player_name VARCHAR(255),
                    mlb_player_id INTEGER,

                    -- Rankings
                    fg_rank INTEGER,
                    org_rank INTEGER,

                    -- Future Value (Overall Grade)
                    future_value INTEGER,  -- 20-80 scale

                    -- Tool Grades (20-80 scale)
                    hit_tool INTEGER,
                    power_tool INTEGER,
                    run_tool INTEGER,
                    field_tool INTEGER,
                    arm_tool INTEGER,

                    -- Additional Info
                    position VARCHAR(50),
                    organization VARCHAR(100),
                    age FLOAT,
                    eta VARCHAR(20),
                    risk VARCHAR(50),

                    -- Metadata
                    report_date DATE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))

            # Create index on mlb_player_id for joins
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_fg_grades_mlb_player_id
                ON fangraphs_prospect_grades(mlb_player_id)
            """))

            logger.info("Created/verified fangraphs_prospect_grades table")

    def parse_tool_grade(self, value: Any) -> Optional[int]:
        """Parse tool grade to integer (20-80 scale)."""
        if value is None:
            return None

        # Handle string grades like "50/55" (present/future)
        if isinstance(value, str):
            if '/' in value:
                # Take future grade (second number)
                parts = value.split('/')
                try:
                    return int(parts[-1].strip())
                except (ValueError, IndexError):
                    return None
            try:
                return int(value)
            except ValueError:
                return None

        # Handle numeric
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    async def match_to_prospects_table(self, fg_name: str, fg_player_id: Optional[int] = None) -> Optional[int]:
        """Try to match FanGraphs prospect to our prospects table."""
        async with engine.begin() as conn:
            # Try exact name match first
            result = await conn.execute(text("""
                SELECT mlb_player_id FROM prospects
                WHERE LOWER(name) = LOWER(:name)
                LIMIT 1
            """), {'name': fg_name})

            row = result.fetchone()
            if row:
                return row[0]

            # Try FanGraphs player ID match
            if fg_player_id:
                result = await conn.execute(text("""
                    SELECT mlb_player_id FROM prospects
                    WHERE fg_player_id = :fg_player_id
                    LIMIT 1
                """), {'fg_player_id': fg_player_id})

                row = result.fetchone()
                if row:
                    return row[0]

            # Try fuzzy name match (first/last name)
            name_parts = fg_name.split()
            if len(name_parts) >= 2:
                first = name_parts[0]
                last = name_parts[-1]
                result = await conn.execute(text("""
                    SELECT mlb_player_id FROM prospects
                    WHERE name ILIKE :pattern
                    LIMIT 1
                """), {'pattern': f'%{first}%{last}%'})

                row = result.fetchone()
                if row:
                    logger.info(f"Fuzzy matched: {fg_name} -> mlb_player_id {row[0]}")
                    return row[0]

        return None

    async def save_prospect_grade(self, prospect_data: Dict[str, Any]):
        """Save individual prospect grade to database."""
        try:
            # Extract fields (FanGraphs API field names may vary)
            fg_prospect_id = prospect_data.get('prospectid') or prospect_data.get('prospect_id')
            fg_player_id = prospect_data.get('playerid') or prospect_data.get('player_id')
            player_name = prospect_data.get('playername') or prospect_data.get('name')

            if not player_name:
                logger.warning(f"Skipping prospect with no name: {prospect_data}")
                return

            # Try to match to our prospects table
            mlb_player_id = await self.match_to_prospects_table(player_name, fg_player_id)

            # Extract grades
            future_value = self.parse_tool_grade(prospect_data.get('fv') or prospect_data.get('future_value'))
            hit_tool = self.parse_tool_grade(prospect_data.get('hit') or prospect_data.get('hit_tool'))
            power_tool = self.parse_tool_grade(prospect_data.get('power') or prospect_data.get('power_tool') or prospect_data.get('pwr'))
            run_tool = self.parse_tool_grade(prospect_data.get('run') or prospect_data.get('run_tool') or prospect_data.get('spd'))
            field_tool = self.parse_tool_grade(prospect_data.get('field') or prospect_data.get('field_tool') or prospect_data.get('fld'))
            arm_tool = self.parse_tool_grade(prospect_data.get('arm') or prospect_data.get('arm_tool'))

            # Rankings
            fg_rank = prospect_data.get('rank') or prospect_data.get('fg_rank')
            org_rank = prospect_data.get('org_rank') or prospect_data.get('orgrank')

            # Other info
            position = prospect_data.get('pos') or prospect_data.get('position')
            organization = prospect_data.get('org') or prospect_data.get('organization') or prospect_data.get('team')
            age = prospect_data.get('age')
            eta = prospect_data.get('eta')
            risk = prospect_data.get('risk')

            # Save to database
            async with engine.begin() as conn:
                await conn.execute(text("""
                    INSERT INTO fangraphs_prospect_grades
                    (fg_prospect_id, fg_player_id, player_name, mlb_player_id,
                     fg_rank, org_rank, future_value,
                     hit_tool, power_tool, run_tool, field_tool, arm_tool,
                     position, organization, age, eta, risk, report_date, updated_at)
                    VALUES
                    (:fg_prospect_id, :fg_player_id, :player_name, :mlb_player_id,
                     :fg_rank, :org_rank, :future_value,
                     :hit_tool, :power_tool, :run_tool, :field_tool, :arm_tool,
                     :position, :organization, :age, :eta, :risk, :report_date, NOW())
                    ON CONFLICT (fg_prospect_id) DO UPDATE SET
                        fg_player_id = EXCLUDED.fg_player_id,
                        player_name = EXCLUDED.player_name,
                        mlb_player_id = EXCLUDED.mlb_player_id,
                        fg_rank = EXCLUDED.fg_rank,
                        org_rank = EXCLUDED.org_rank,
                        future_value = EXCLUDED.future_value,
                        hit_tool = EXCLUDED.hit_tool,
                        power_tool = EXCLUDED.power_tool,
                        run_tool = EXCLUDED.run_tool,
                        field_tool = EXCLUDED.field_tool,
                        arm_tool = EXCLUDED.arm_tool,
                        position = EXCLUDED.position,
                        organization = EXCLUDED.organization,
                        age = EXCLUDED.age,
                        eta = EXCLUDED.eta,
                        risk = EXCLUDED.risk,
                        report_date = EXCLUDED.report_date,
                        updated_at = NOW()
                """), {
                    'fg_prospect_id': fg_prospect_id,
                    'fg_player_id': fg_player_id,
                    'player_name': player_name,
                    'mlb_player_id': mlb_player_id,
                    'fg_rank': fg_rank,
                    'org_rank': org_rank,
                    'future_value': future_value,
                    'hit_tool': hit_tool,
                    'power_tool': power_tool,
                    'run_tool': run_tool,
                    'field_tool': field_tool,
                    'arm_tool': arm_tool,
                    'position': position,
                    'organization': organization,
                    'age': float(age) if age else None,
                    'eta': eta,
                    'risk': risk,
                    'report_date': datetime.now().date()
                })

            self.prospects_collected += 1

            if mlb_player_id:
                logger.info(f"✓ {player_name} (FV: {future_value}) - Matched to mlb_player_id {mlb_player_id}")
            else:
                logger.info(f"✓ {player_name} (FV: {future_value}) - No MLB ID match")

        except Exception as e:
            logger.error(f"Error saving prospect {prospect_data.get('playername', 'unknown')}: {e}")

    async def collect_all_grades(self):
        """Main collection process."""
        logger.info("="*80)
        logger.info("FanGraphs Prospect Grade Collection")
        logger.info("="*80)

        # Create table
        await self.create_grades_table()

        # Fetch prospect list
        prospects = await self.get_prospect_list()

        if not prospects:
            logger.error("No prospects found. API may have changed or be unavailable.")
            return

        logger.info(f"Processing {len(prospects)} prospects...")

        # Save each prospect
        for prospect in prospects:
            await self.save_prospect_grade(prospect)
            await asyncio.sleep(0.1)  # Be respectful to API

        logger.info("="*80)
        logger.info(f"Collection Complete!")
        logger.info(f"  Prospects Collected: {self.prospects_collected}")
        logger.info("="*80)


async def main():
    """Execute FanGraphs grade collection."""
    async with FanGraphsProspectCollector() as collector:
        await collector.collect_all_grades()


if __name__ == "__main__":
    asyncio.run(main())
