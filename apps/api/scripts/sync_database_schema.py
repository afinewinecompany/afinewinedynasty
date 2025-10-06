#!/usr/bin/env python3
"""
Synchronize Database Schema with ORM Models
============================================
Adds all missing columns to match the ORM models.

Usage:
    python sync_database_schema.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db_sync
from sqlalchemy import text


def get_existing_columns(db, table_name):
    """Get list of existing columns for a table."""
    query = text(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
    """)
    result = db.execute(query)
    return {row[0] for row in result.fetchall()}


def sync_prospects_table(db):
    """Synchronize prospects table with ORM model."""
    print("\nSyncing prospects table...")

    existing = get_existing_columns(db, 'prospects')

    # Define all columns that should exist (matching ORM model exactly)
    required_columns = {
        # External IDs
        'fg_player_id': 'VARCHAR(50)',
        'fg_prospect_id': 'VARCHAR(50)',
        'ba_player_id': 'VARCHAR(50)',

        # Bio
        'bats': 'VARCHAR(1)',
        'throws': 'VARCHAR(1)',

        # Physical
        'height_inches': 'INTEGER',
        'weight_lbs': 'INTEGER',
        'birth_date': 'DATE',
        'birth_country': 'VARCHAR(100)',
        'birth_city': 'VARCHAR(100)',

        # Draft
        'draft_year': 'INTEGER',
        'draft_round': 'INTEGER',
        'draft_pick': 'INTEGER',
        'draft_team': 'VARCHAR(100)',
        'signing_bonus_usd': 'INTEGER',

        # Current status
        'current_team': 'VARCHAR(100)',
        'current_organization': 'VARCHAR(100)',
        'current_level': 'VARCHAR(20)',

        # Metadata
        'last_stats_update': 'TIMESTAMP',
        'data_sources': 'JSON DEFAULT \'{}\'::json',
    }

    added = 0
    for column, col_type in required_columns.items():
        if column not in existing:
            print(f"  Adding {column}...")
            db.execute(text(f"ALTER TABLE prospects ADD COLUMN {column} {col_type}"))
            added += 1

    # Add indexes
    if 'fg_player_id' not in existing:
        print("  Adding index on fg_player_id...")
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_fg_player_id ON prospects(fg_player_id)"))

    db.commit()
    print(f"  Added {added} columns to prospects table")
    return added


def sync_scouting_grades_table(db):
    """Synchronize scouting_grades table with ORM model."""
    print("\nSyncing scouting_grades table...")

    # Check if table exists
    check_table = text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'scouting_grades'
        )
    """)
    table_exists = db.execute(check_table).scalar()

    if not table_exists:
        print("  Table doesn't exist - skipping")
        return 0

    existing = get_existing_columns(db, 'scouting_grades')

    required_columns = {
        'ranking_year': 'INTEGER NOT NULL DEFAULT 2024',
        'rank_overall': 'INTEGER',
        'future_value': 'INTEGER',
        'risk_level': 'VARCHAR(10)',
        'eta_year': 'INTEGER',
        'eta_season': 'VARCHAR(20)',
        'hit_present': 'INTEGER',
        'power_present': 'INTEGER',
        'raw_power_present': 'INTEGER',
        'speed_present': 'INTEGER',
        'field_present': 'INTEGER',
        'arm_present': 'INTEGER',
        'hit_future': 'INTEGER',
        'power_future': 'INTEGER',
        'raw_power_future': 'INTEGER',
        'speed_future': 'INTEGER',
        'field_future': 'INTEGER',
        'arm_future': 'INTEGER',
        'fastball_grade': 'INTEGER',
        'slider_grade': 'INTEGER',
        'curveball_grade': 'INTEGER',
        'changeup_grade': 'INTEGER',
        'control_grade': 'INTEGER',
        'command_grade': 'INTEGER',
        'dynasty_rank': 'INTEGER',
        'redraft_rank': 'INTEGER',
        'scouting_report': 'TEXT',
        'date_recorded': 'DATE NOT NULL DEFAULT CURRENT_DATE',
    }

    added = 0
    for column, col_type in required_columns.items():
        if column not in existing:
            print(f"  Adding {column}...")
            try:
                db.execute(text(f"ALTER TABLE scouting_grades ADD COLUMN {column} {col_type}"))
                added += 1
            except Exception as e:
                print(f"  Warning: Could not add {column}: {e}")

    db.commit()
    print(f"  Added {added} columns to scouting_grades table")
    return added


def fix_position_constraint(db):
    """Fix position constraint to allow OF and all valid positions."""
    print("\nFixing position constraint...")

    try:
        # Drop old constraint if it exists
        print("  Dropping old valid_position constraint...")
        db.execute(text("ALTER TABLE prospects DROP CONSTRAINT IF EXISTS valid_position"))

        # Add new constraint with all valid positions
        print("  Adding new valid_position constraint...")
        db.execute(text("""
            ALTER TABLE prospects ADD CONSTRAINT valid_position CHECK (
                position IN ('P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'OF', 'IF', 'DH', 'SP', 'RP', 'RHP', 'LHP')
            )
        """))

        db.commit()
        print("  Position constraint updated successfully")
        return True
    except Exception as e:
        print(f"  Error fixing constraint: {e}")
        db.rollback()
        return False


def fix_scouting_source_constraint(db):
    """Fix scouting source constraint to allow 'fangraphs'."""
    print("\nFixing scouting source constraint...")

    try:
        # Drop old constraint if it exists
        print("  Dropping old valid_source constraint...")
        db.execute(text("ALTER TABLE scouting_grades DROP CONSTRAINT IF EXISTS valid_source"))

        # Add new constraint with valid sources
        print("  Adding new valid_source constraint...")
        db.execute(text("""
            ALTER TABLE scouting_grades ADD CONSTRAINT valid_source CHECK (
                source IN ('fangraphs', 'baseball_america', 'mlb_pipeline', 'other')
            )
        """))

        db.commit()
        print("  Scouting source constraint updated successfully")
        return True
    except Exception as e:
        print(f"  Error fixing constraint: {e}")
        db.rollback()
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Database Schema Synchronization")
    print("=" * 60)

    db = get_db_sync()
    total_added = 0

    try:
        # Sync each table
        total_added += sync_prospects_table(db)
        total_added += sync_scouting_grades_table(db)

        # Fix constraints
        fix_position_constraint(db)
        fix_scouting_source_constraint(db)

        print("\n" + "=" * 60)
        print(f"Schema sync complete! Added {total_added} columns total.")
        print("=" * 60)

        # Verify prospects table
        print("\nVerifying prospects table columns:")
        verify_sql = text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'prospects'
            ORDER BY ordinal_position
        """)
        result = db.execute(verify_sql)
        for row in result:
            print(f"  - {row[0]}: {row[1]}")

    except Exception as e:
        print(f"\nError: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
