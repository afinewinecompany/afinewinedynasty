"""
Collect birth dates for all players in game logs from MLB Stats API.
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Optional
import logging

from sqlalchemy import text
from app.db.database import engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PlayerBirthDateCollector:
    """Collects birth dates for players from MLB Stats API."""

    BASE_URL = "https://statsapi.mlb.com/api/v1"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def fetch_player_info(self, player_id: int) -> Optional[dict]:
        """Fetch player information from MLB Stats API."""
        url = f"{self.BASE_URL}/people/{player_id}"

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'people' in data and len(data['people']) > 0:
                        return data['people'][0]
                elif response.status == 404:
                    logger.debug(f"Player {player_id} not found")
                else:
                    logger.warning(f"Error fetching player {player_id}: {response.status}")
        except Exception as e:
            logger.error(f"Exception fetching player {player_id}: {e}")

        return None

    async def get_all_player_ids(self) -> list:
        """Get all unique player IDs from game logs."""
        async with engine.begin() as conn:
            # Get from MiLB game logs
            result = await conn.execute(text("""
                SELECT DISTINCT mlb_player_id
                FROM milb_game_logs
                WHERE mlb_player_id IS NOT NULL
                ORDER BY mlb_player_id
            """))
            milb_ids = [row[0] for row in result.fetchall()]

            # Get from MLB game logs
            result = await conn.execute(text("""
                SELECT DISTINCT mlb_player_id
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
                ORDER BY mlb_player_id
            """))
            mlb_ids = [row[0] for row in result.fetchall()]

            # Combine and deduplicate
            all_ids = sorted(set(milb_ids + mlb_ids))
            logger.info(f"Found {len(all_ids)} unique player IDs in game logs")

            return all_ids

    async def update_prospect_birth_info(self, player_id: int, player_info: dict):
        """Update prospect record with birth information."""
        # Parse dates from strings to date objects
        birth_date_str = player_info.get('birthDate')
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date() if birth_date_str else None

        mlb_debut_str = player_info.get('mlbDebutDate')
        mlb_debut = datetime.strptime(mlb_debut_str, '%Y-%m-%d').date() if mlb_debut_str else None

        birth_city = player_info.get('birthCity')
        birth_country = player_info.get('birthCountry')
        full_name = player_info.get('fullName')
        height = player_info.get('height')
        weight = player_info.get('weight')
        bats = player_info.get('batSide', {}).get('code') if player_info.get('batSide') else None
        throws = player_info.get('pitchHand', {}).get('code') if player_info.get('pitchHand') else None
        position = player_info.get('primaryPosition', {}).get('abbreviation') if player_info.get('primaryPosition') else None

        async with engine.begin() as conn:
            # Check if prospect exists
            result = await conn.execute(
                text("SELECT id FROM prospects WHERE mlb_player_id = :player_id"),
                {"player_id": str(player_id)}
            )
            existing = result.fetchone()

            if existing:
                # Update existing prospect
                await conn.execute(text("""
                    UPDATE prospects
                    SET birth_date = :birth_date,
                        birth_city = :birth_city,
                        birth_country = :birth_country,
                        bats = COALESCE(:bats, bats),
                        throws = COALESCE(:throws, throws),
                        position = COALESCE(:position, position),
                        mlb_debut_date = :mlb_debut,
                        updated_at = NOW()
                    WHERE mlb_player_id = :player_id
                """), {
                    "player_id": str(player_id),
                    "birth_date": birth_date,
                    "birth_city": birth_city,
                    "birth_country": birth_country,
                    "bats": bats,
                    "throws": throws,
                    "position": position,
                    "mlb_debut": mlb_debut
                })
            else:
                # Insert new prospect
                # Extract height in inches
                height_inches = None
                if height:
                    try:
                        parts = height.replace("'", "").replace('"', '').split()
                        if len(parts) == 2:
                            feet = int(parts[0])
                            inches = int(parts[1])
                            height_inches = (feet * 12) + inches
                    except:
                        pass

                await conn.execute(text("""
                    INSERT INTO prospects
                    (mlb_player_id, name, birth_date, birth_city, birth_country,
                     position, bats, throws, height_inches, weight_lbs, mlb_debut_date,
                     created_at, updated_at)
                    VALUES
                    (:player_id, :name, :birth_date, :birth_city, :birth_country,
                     :position, :bats, :throws, :height_inches, :weight, :mlb_debut,
                     NOW(), NOW())
                """), {
                    "player_id": str(player_id),
                    "name": full_name or f"Player {player_id}",
                    "birth_date": birth_date,
                    "birth_city": birth_city,
                    "birth_country": birth_country,
                    "position": position,
                    "bats": bats,
                    "throws": throws,
                    "height_inches": height_inches,
                    "weight": weight,
                    "mlb_debut": mlb_debut
                })

    async def collect_birth_dates(self):
        """Main collection process."""
        player_ids = await self.get_all_player_ids()

        logger.info(f"Collecting birth dates for {len(player_ids)} players...")

        success_count = 0
        error_count = 0

        for i, player_id in enumerate(player_ids, 1):
            if i % 100 == 0:
                logger.info(f"Progress: {i}/{len(player_ids)} ({success_count} successful, {error_count} errors)")

            player_info = await self.fetch_player_info(player_id)

            if player_info and player_info.get('birthDate'):
                try:
                    await self.update_prospect_birth_info(player_id, player_info)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error updating player {player_id}: {e}")
                    error_count += 1
            else:
                error_count += 1

            # Rate limiting
            await asyncio.sleep(0.1)

        logger.info(f"\nCollection complete!")
        logger.info(f"Success: {success_count}")
        logger.info(f"Errors: {error_count}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Player Birth Date Collection")
    logger.info("="*80)

    async with PlayerBirthDateCollector() as collector:
        await collector.collect_birth_dates()

    # Verify results
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(birth_date) as with_birth_date,
                COUNT(birth_city) as with_birth_city
            FROM prospects
        """))
        row = result.fetchone()
        logger.info(f"\nProspects table: {row[0]} total, {row[1]} with birth_date, {row[2]} with birth_city")


if __name__ == "__main__":
    asyncio.run(main())
