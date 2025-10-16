"""
Setup pitch-by-pitch tables in the database.

This script reads the SQL schema file and creates the tables.
Can be run multiple times safely (uses IF NOT EXISTS).

Usage:
    python setup_pitch_tables.py
"""

import logging
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
sys.path.insert(0, str(api_dir))

from app.db.database import get_db_sync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("="*80)
    logger.info("PITCH-BY-PITCH TABLE SETUP")
    logger.info("="*80)

    # Read SQL file
    sql_file = Path(__file__).parent / 'create_batter_pitcher_pitch_tables.sql'

    if not sql_file.exists():
        logger.error(f"SQL file not found: {sql_file}")
        return

    logger.info(f"Reading SQL from: {sql_file}")

    with open(sql_file, 'r') as f:
        sql_content = f.read()

    # Get database connection
    db = get_db_sync()

    try:
        # Split SQL into individual statements
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]

        logger.info(f"Found {len(statements)} SQL statements")
        logger.info("")

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            # Skip comments
            if statement.startswith('--') or statement.startswith('/*'):
                continue

            # Get statement type
            statement_type = statement.split()[0].upper() if statement else ""

            if statement_type in ['CREATE', 'COMMENT']:
                # Extract table/view name for logging
                if 'TABLE' in statement:
                    try:
                        table_name = statement.split('TABLE')[1].split('(')[0].strip().split()[0]
                        logger.info(f"[{i}/{len(statements)}] Creating table: {table_name}")
                    except:
                        logger.info(f"[{i}/{len(statements)}] Creating table...")
                elif 'VIEW' in statement:
                    try:
                        view_name = statement.split('VIEW')[1].split('AS')[0].strip().split()[0]
                        logger.info(f"[{i}/{len(statements)}] Creating view: {view_name}")
                    except:
                        logger.info(f"[{i}/{len(statements)}] Creating view...")
                elif 'INDEX' in statement:
                    try:
                        index_name = statement.split('INDEX')[1].split('ON')[0].strip().split()[0]
                        logger.info(f"[{i}/{len(statements)}] Creating index: {index_name}")
                    except:
                        logger.info(f"[{i}/{len(statements)}] Creating index...")
                else:
                    logger.info(f"[{i}/{len(statements)}] Executing statement...")

                try:
                    db.execute(text(statement))
                    db.commit()
                    logger.info("  ✓ Success")
                except Exception as e:
                    # Check if error is "already exists"
                    error_msg = str(e).lower()
                    if 'already exists' in error_msg:
                        logger.info("  → Already exists (skipped)")
                    else:
                        logger.error(f"  ✗ Error: {e}")
                        db.rollback()

        logger.info("")
        logger.info("="*80)
        logger.info("SETUP COMPLETE")
        logger.info("="*80)

        # Verify tables were created
        result = db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('milb_batter_pitches', 'milb_pitcher_pitches')
            ORDER BY table_name
        """))

        tables = [row[0] for row in result.fetchall()]

        logger.info("")
        logger.info("Tables created:")
        for table in tables:
            logger.info(f"  ✓ {table}")

        # Check views
        result = db.execute(text("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            AND table_name IN ('batter_pitch_summary', 'pitcher_pitch_summary')
            ORDER BY table_name
        """))

        views = [row[0] for row in result.fetchall()]

        logger.info("")
        logger.info("Views created:")
        for view in views:
            logger.info(f"  ✓ {view}")

        logger.info("")
        logger.info("="*80)
        logger.info("READY TO COLLECT DATA")
        logger.info("="*80)
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Test: python test_pitch_collection.py")
        logger.info("  2. Small test: python run_all_pitch_collections.py --test")
        logger.info("  3. Full collection: python run_all_pitch_collections.py")

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


if __name__ == "__main__":
    main()
