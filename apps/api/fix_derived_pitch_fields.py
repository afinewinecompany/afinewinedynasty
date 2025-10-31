"""
Fix derived pitch data fields (swing, contact, swing_and_miss, etc.)

This script populates the boolean fields from the raw pitch_call and pitch_result data.
Handles BOTH milb_batter_pitches and milb_pitcher_pitches tables.
"""

from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"

def update_table_derived_fields(conn, table_name: str):
    """
    Update derived boolean fields from raw pitch data for a specific table.

    Args:
        conn: Database connection
        table_name: Either 'milb_batter_pitches' or 'milb_pitcher_pitches'
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"Processing table: {table_name}")
    logger.info(f"{'='*80}")

    # First, check current state
    check_query = text(f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE swing IS NOT NULL) as swing_populated,
            COUNT(*) FILTER (WHERE contact IS NOT NULL) as contact_populated,
            COUNT(*) FILTER (WHERE swing_and_miss IS NOT NULL) as swing_miss_populated
        FROM {table_name}
        WHERE season = 2025
    """)

    result = conn.execute(check_query).fetchone()
    logger.info(f"Current state: {result.total:,} total pitches")
    logger.info(f"  Swing populated: {result.swing_populated:,} ({result.swing_populated/result.total*100:.1f}%)")
    logger.info(f"  Contact populated: {result.contact_populated:,}")
    logger.info(f"  Swing & Miss populated: {result.swing_miss_populated:,}")

    # Update all fields in a single query (more efficient and avoids deadlocks)
    logger.info("Updating all derived fields in one pass...")
    update_all_query = text(f"""
        UPDATE {table_name}
        SET
            swing = (
                pitch_result LIKE '%Swinging%' OR
                pitch_result LIKE '%Foul%' OR
                pitch_result LIKE '%In play%'
            ),
            swing_and_miss = (
                pitch_result = 'Swinging Strike' OR
                pitch_result = 'Swinging Strike (Blocked)'
            ),
            foul = (pitch_result LIKE '%Foul%'),
            contact = (
                (pitch_result LIKE '%Swinging%' OR
                 pitch_result LIKE '%Foul%' OR
                 pitch_result LIKE '%In play%')
                AND (
                    pitch_result LIKE '%Foul%' OR
                    pitch_result LIKE '%In play%'
                )
            )
        WHERE season = 2025
            AND swing IS DISTINCT FROM (
                pitch_result LIKE '%Swinging%' OR
                pitch_result LIKE '%Foul%' OR
                pitch_result LIKE '%In play%'
            )
    """)
    result = conn.execute(update_all_query)
    logger.info(f"Updated {result.rowcount:,} rows")

    # Verify results
    verify_query = text(f"""
        SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE swing = TRUE) as swings,
            COUNT(*) FILTER (WHERE contact = TRUE) as contacts,
            COUNT(*) FILTER (WHERE swing_and_miss = TRUE) as swing_misses,
            COUNT(*) FILTER (WHERE foul = TRUE) as fouls
        FROM {table_name}
        WHERE season = 2025
    """)

    result = conn.execute(verify_query).fetchone()
    logger.info(f"\nVerification results for {table_name}:")
    logger.info(f"  Total pitches: {result.total:,}")
    logger.info(f"  Swings: {result.swings:,} ({result.swings/result.total*100:.1f}%)")
    logger.info(f"  Contacts: {result.contacts:,} ({result.contacts/result.total*100:.1f}%)")
    logger.info(f"  Swing & Misses: {result.swing_misses:,} ({result.swing_misses/result.total*100:.1f}%)")
    logger.info(f"  Fouls: {result.fouls:,} ({result.fouls/result.total*100:.1f}%)")


def update_derived_fields():
    """Update derived fields for both batter and pitcher pitch tables."""
    engine = create_engine(DATABASE_URL)

    with engine.begin() as conn:
        # Update both tables
        update_table_derived_fields(conn, 'milb_batter_pitches')
        update_table_derived_fields(conn, 'milb_pitcher_pitches')

if __name__ == "__main__":
    logger.info("Starting derived field update...")
    update_derived_fields()
    logger.info("Done!")
