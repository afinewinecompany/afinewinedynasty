#!/usr/bin/env python3
"""Check which collections are actively running."""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Convert async URL to sync
db_url = os.getenv('SQLALCHEMY_DATABASE_URI').replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(db_url)

print("\n" + "="*80)
print("ACTIVE COLLECTION CHECK")
print("="*80)

with engine.connect() as conn:
    # Check pitch collection - last 5 minutes
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_batter_id) as unique_batters,
            MIN(created_at) as first_insert,
            MAX(created_at) as last_insert
        FROM milb_batter_pitches
        WHERE created_at >= NOW() - INTERVAL '5 minutes'
    """))
    row = result.fetchone()

    print(f"\nPITCH COLLECTION (last 5 min):")
    if row[0] > 0:
        print(f"  ✓ ACTIVE - {row[0]:,} pitches from {row[1]} batters")
        print(f"  First: {row[2]}")
        print(f"  Last: {row[3]}")
    else:
        print(f"  ✗ NO ACTIVITY")

    # Check PA collection - last 5 minutes
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pas,
            COUNT(DISTINCT mlb_player_id) as unique_players,
            MIN(created_at) as first_insert,
            MAX(created_at) as last_insert
        FROM milb_plate_appearances
        WHERE created_at >= NOW() - INTERVAL '5 minutes'
    """))
    row = result.fetchone()

    print(f"\nPA COLLECTION (last 5 min):")
    if row[0] > 0:
        print(f"  ✓ ACTIVE - {row[0]:,} PAs from {row[1]} players")
        print(f"  First: {row[2]}")
        print(f"  Last: {row[3]}")
    else:
        print(f"  ✗ NO ACTIVITY")

    # Get most recently collected players
    print(f"\n" + "-"*80)
    print("RECENTLY COLLECTED BATTERS (Pitch data - last 10 min):")
    result = conn.execute(text("""
        SELECT
            p.name,
            COUNT(*) as pitch_count,
            MAX(bp.created_at) as last_pitch
        FROM milb_batter_pitches bp
        JOIN prospects p ON bp.mlb_batter_id = CAST(p.mlb_player_id AS INTEGER)
        WHERE bp.created_at >= NOW() - INTERVAL '10 minutes'
        GROUP BY p.name
        ORDER BY last_pitch DESC
        LIMIT 5
    """))

    for row in result:
        print(f"  {row[0]:<30} {row[1]:>6} pitches (last: {row[2]})")

    # Check PA collection progress
    print(f"\n" + "-"*80)
    print("RECENTLY COLLECTED PLAYERS (PA data - last 30 min):")
    result = conn.execute(text("""
        SELECT
            p.name,
            COUNT(*) as pa_count,
            MAX(pa.created_at) as last_pa
        FROM milb_plate_appearances pa
        JOIN prospects p ON pa.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
        WHERE pa.created_at >= NOW() - INTERVAL '30 minutes'
        GROUP BY p.name
        ORDER BY last_pa DESC
        LIMIT 5
    """))

    rows = list(result)
    if rows:
        for row in rows:
            print(f"  {row[0]:<30} {row[1]:>6} PAs (last: {row[2]})")
    else:
        print(f"  (No recent PA collection activity)")

print("\n" + "="*80)
