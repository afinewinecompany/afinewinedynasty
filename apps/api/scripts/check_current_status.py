#!/usr/bin/env python3
"""Quick status check on current collections."""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Convert async URL to sync
db_url = os.getenv('SQLALCHEMY_DATABASE_URI').replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(db_url)

with engine.connect() as conn:
    print("\n" + "="*80)
    print("CURRENT COLLECTION STATUS")
    print("="*80)

    # Check PA collection activity
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pas,
            COUNT(DISTINCT mlb_player_id) as unique_prospects,
            MAX(created_at) as last_insert
        FROM milb_plate_appearances
        WHERE created_at >= NOW() - INTERVAL '10 minutes'
    """))
    row = result.fetchone()

    print(f"\nPA Collection (last 10 min):")
    print(f"  Total PAs: {row[0]:,}")
    print(f"  Prospects: {row[1]}")
    print(f"  Last insert: {row[2]}")

    # Check pitch collection activity
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_batter_id) as unique_batters,
            MAX(created_at) as last_insert
        FROM milb_batter_pitches
        WHERE created_at >= NOW() - INTERVAL '10 minutes'
    """))
    row = result.fetchone()

    print(f"\nPitch Collection (last 10 min):")
    print(f"  Total pitches: {row[0]:,}")
    print(f"  Batters: {row[1]}")
    print(f"  Last insert: {row[2]}")

    # Total PA count
    result = conn.execute(text("SELECT COUNT(*) FROM milb_plate_appearances"))
    total_pas = result.fetchone()[0]

    # PA coverage
    result = conn.execute(text("""
        SELECT
            COUNT(DISTINCT mlb_player_id) as prospects_with_pas
        FROM milb_plate_appearances
        WHERE mlb_player_id IN (
            SELECT CAST(mlb_player_id AS INTEGER)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL AND mlb_player_id != ''
        )
    """))
    prospects_with_pas = result.fetchone()[0]

    print(f"\n\nOVERALL STATUS:")
    print(f"  Total PAs in database: {total_pas:,}")
    print(f"  Prospects with PA data: {prospects_with_pas} / 1,251")
    print(f"  Coverage: {prospects_with_pas/1251*100:.1f}%")

print("\n" + "="*80)
