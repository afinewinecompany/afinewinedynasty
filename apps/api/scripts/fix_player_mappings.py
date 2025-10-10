"""
Fix MLB Player ID Mappings and Data Collection

This script:
1. Maps known MLB player IDs to prospect records
2. Links milb_game_logs to correct prospect_ids
3. Identifies missing data for collection
"""

import asyncio
from sqlalchemy import text
from app.db.database import engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Known MLB ID mappings for key prospects
PLAYER_MAPPINGS = {
    'Chase DeLauter': '800050',
    'Sal Stewart': '701398',
    'Travis Bazzana': '683953',
    'Max Clark': '703601',
    'JJ Wetherholt': '802419',
    'Braden Montgomery': '806968',
    'Walker Jenkins': '805805',
    'Jeferson Quero': '691620',
    'Charlie Condon': '808001',
}

async def fix_mappings():
    """Fix MLB ID mappings and link game logs."""
    async with engine.begin() as conn:
        # Step 1: Update prospects with MLB IDs
        logger.info("Step 1: Mapping MLB IDs to prospects...")
        for name, mlb_id in PLAYER_MAPPINGS.items():
            result = await conn.execute(text("""
                UPDATE prospects
                SET mlb_id = :mlb_id
                WHERE name = :name AND (mlb_id IS NULL OR mlb_id = '')
                RETURNING id, name
            """), {'mlb_id': mlb_id, 'name': name})

            if result.rowcount > 0:
                logger.info(f"  Mapped {name} to MLB ID {mlb_id}")

        # Step 2: Link orphaned game logs using mlb_player_id
        logger.info("\nStep 2: Linking orphaned game logs...")
        result = await conn.execute(text("""
            UPDATE milb_game_logs gl
            SET prospect_id = p.id
            FROM prospects p
            WHERE gl.mlb_player_id = p.mlb_id::integer
              AND gl.prospect_id IS NULL
              AND p.mlb_id IS NOT NULL
            RETURNING gl.mlb_player_id, p.name
        """))

        if result.rowcount > 0:
            logger.info(f"  Linked {result.rowcount} game log records")

        # Step 3: Report on data coverage
        logger.info("\nStep 3: Data coverage report...")
        result = await conn.execute(text("""
            SELECT
                p.name,
                p.mlb_id,
                COUNT(DISTINCT CASE WHEN gl.season = 2024 THEN gl.game_date END) as games_2024,
                COUNT(DISTINCT CASE WHEN gl.season = 2025 THEN gl.game_date END) as games_2025,
                SUM(CASE WHEN gl.season = 2024 THEN gl.plate_appearances ELSE 0 END) as pa_2024,
                SUM(CASE WHEN gl.season = 2025 THEN gl.plate_appearances ELSE 0 END) as pa_2025
            FROM prospects p
            LEFT JOIN milb_game_logs gl ON p.id = gl.prospect_id
            WHERE p.name IN :names
            GROUP BY p.name, p.mlb_id
            ORDER BY p.name
        """), {'names': tuple(PLAYER_MAPPINGS.keys())})

        logger.info("\nPlayer Data Coverage:")
        logger.info("-" * 70)
        for row in result.fetchall():
            logger.info(f"{row[0]:20s} (MLB: {row[1] or 'None':6s}) - 2024: {row[2]:3d}g {row[4]:4.0f}PA | 2025: {row[3]:3d}g {row[5]:4.0f}PA")

if __name__ == "__main__":
    asyncio.run(fix_mappings())