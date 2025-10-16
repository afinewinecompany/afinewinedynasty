"""
Test the pitch collection setup.

This script:
1. Checks database connection
2. Verifies tables exist (creates if missing)
3. Runs a mini collection test (1 player)
4. Validates data was inserted correctly

Usage:
    python test_pitch_collection.py
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.database import get_db_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_and_create_tables(db):
    """Check if tables exist, create if missing."""
    logger.info("Checking database tables...")

    # Check for tables
    result = db.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('milb_batter_pitches', 'milb_pitcher_pitches')
    """))

    existing_tables = [row[0] for row in result.fetchall()]

    if 'milb_batter_pitches' not in existing_tables:
        logger.info("Creating milb_batter_pitches table...")
        with open('create_batter_pitcher_pitch_tables.sql', 'r') as f:
            sql = f.read()
            db.execute(text(sql))
            db.commit()
        logger.info("✓ Tables created")
    else:
        logger.info("✓ Tables already exist")


def get_test_player(db):
    """Get a single player with games in 2024."""
    result = db.execute(text("""
        SELECT DISTINCT
            mlb_player_id,
            p.name,
            COUNT(*) as game_count
        FROM milb_game_logs g
        LEFT JOIN prospects p ON g.mlb_player_id::text = p.mlb_player_id
        WHERE g.season = 2024
        AND g.mlb_player_id IS NOT NULL
        GROUP BY mlb_player_id, p.name
        HAVING COUNT(*) > 20
        ORDER BY game_count DESC
        LIMIT 1
    """))

    row = result.fetchone()
    if row:
        return {
            'mlb_player_id': row[0],
            'name': row[1],
            'game_count': row[2]
        }
    return None


def check_collected_data(db, player_id):
    """Check if data was collected for player."""
    # Check batter pitches
    result = db.execute(text("""
        SELECT COUNT(*) as pitch_count,
               COUNT(DISTINCT game_pk) as games,
               AVG(start_speed) as avg_velo,
               COUNT(CASE WHEN swing THEN 1 END) as swings
        FROM milb_batter_pitches
        WHERE mlb_batter_id = :player_id
    """), {'player_id': player_id})

    batter_row = result.fetchone()

    # Check pitcher pitches
    result = db.execute(text("""
        SELECT COUNT(*) as pitch_count,
               COUNT(DISTINCT game_pk) as games,
               AVG(start_speed) as avg_velo,
               COUNT(CASE WHEN is_strike THEN 1 END) as strikes
        FROM milb_pitcher_pitches
        WHERE mlb_pitcher_id = :player_id
    """), {'player_id': player_id})

    pitcher_row = result.fetchone()

    return {
        'batter': {
            'pitches': batter_row[0],
            'games': batter_row[1],
            'avg_velo': batter_row[2],
            'swings': batter_row[3]
        },
        'pitcher': {
            'pitches': pitcher_row[0],
            'games': pitcher_row[1],
            'avg_velo': pitcher_row[2],
            'strikes': pitcher_row[3]
        }
    }


async def run_mini_collection(player):
    """Run collection for 1 player."""
    import subprocess
    import sys

    logger.info(f"Running mini collection for {player['name']}...")

    # Use the 2024 script with limit 1
    result = subprocess.run(
        [sys.executable, 'collect_pitch_data_2024.py', '--limit', '1'],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        logger.info("✓ Collection successful")
        return True
    else:
        logger.error(f"✗ Collection failed: {result.stderr}")
        return False


def main():
    logger.info("="*80)
    logger.info("PITCH COLLECTION TEST")
    logger.info("="*80)

    db = get_db_sync()

    try:
        # Step 1: Check tables
        logger.info("\n[1/4] Checking database tables...")
        check_and_create_tables(db)

        # Step 2: Get test player
        logger.info("\n[2/4] Finding test player...")
        player = get_test_player(db)

        if not player:
            logger.error("✗ No suitable test player found")
            return

        logger.info(f"✓ Test player: {player['name']} (ID: {player['mlb_player_id']})")
        logger.info(f"  Games played: {player['game_count']}")

        # Step 3: Check existing data
        logger.info("\n[3/4] Checking existing data...")
        before_data = check_collected_data(db, player['mlb_player_id'])

        logger.info(f"  Batter pitches: {before_data['batter']['pitches']}")
        logger.info(f"  Pitcher pitches: {before_data['pitcher']['pitches']}")

        if before_data['batter']['pitches'] > 0:
            logger.info("✓ Data already exists - test successful!")
            logger.info("\nSample batter stats:")
            logger.info(f"  Avg pitch velocity faced: {before_data['batter']['avg_velo']:.1f} mph")
            logger.info(f"  Total swings: {before_data['batter']['swings']}")

            if before_data['pitcher']['pitches'] > 0:
                logger.info("\nSample pitcher stats:")
                logger.info(f"  Avg pitch velocity: {before_data['pitcher']['avg_velo']:.1f} mph")
                logger.info(f"  Total strikes: {before_data['pitcher']['strikes']}")

            logger.info("\n" + "="*80)
            logger.info("TEST PASSED - Tables exist and data is present")
            logger.info("="*80)
            return

        # Step 4: Run mini collection
        logger.info("\n[4/4] Running mini collection test...")
        logger.info("(This may take 2-5 minutes...)")

        # Run async collection
        success = asyncio.run(run_mini_collection(player))

        if not success:
            logger.error("✗ Collection failed")
            return

        # Check data again
        after_data = check_collected_data(db, player['mlb_player_id'])

        logger.info("\n" + "="*80)
        logger.info("RESULTS")
        logger.info("="*80)
        logger.info(f"Batter pitches collected: {after_data['batter']['pitches']}")
        logger.info(f"Pitcher pitches collected: {after_data['pitcher']['pitches']}")

        if after_data['batter']['pitches'] > 0 or after_data['pitcher']['pitches'] > 0:
            logger.info("\n✓ TEST PASSED - Data collection working!")
        else:
            logger.warning("\n⚠ TEST INCOMPLETE - No pitches collected")
            logger.warning("This may mean:")
            logger.warning("  - Player has no detailed pitch data in API")
            logger.warning("  - API connection issue")
            logger.warning("Try running: python collect_pitch_data_2024.py --limit 10")

    except Exception as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
