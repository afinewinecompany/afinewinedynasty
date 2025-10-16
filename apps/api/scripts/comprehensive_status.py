#!/usr/bin/env python3
"""Comprehensive collection status report."""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Convert async URL to sync
db_url = os.getenv('SQLALCHEMY_DATABASE_URI').replace('postgresql+asyncpg://', 'postgresql://')
engine = create_engine(db_url)

print("\n" + "="*80)
print("COMPREHENSIVE COLLECTION STATUS REPORT")
print("="*80)
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*80)

with engine.connect() as conn:
    # Overall PA statistics
    print("\n[1] PLATE APPEARANCE (PA) COLLECTION")
    print("-"*80)

    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pas,
            COUNT(DISTINCT mlb_player_id) as unique_players,
            COUNT(DISTINCT game_pk) as unique_games,
            MIN(created_at) as first_insert,
            MAX(created_at) as last_insert
        FROM milb_plate_appearances
    """))
    row = result.fetchone()

    print(f"Total PAs in database: {row[0]:,}")
    print(f"Unique players: {row[1]:,}")
    print(f"Unique games: {row[2]:,}")
    print(f"First insert: {row[3]}")
    print(f"Last insert: {row[4]}")

    # PA activity in last hour
    result = conn.execute(text("""
        SELECT
            COUNT(*) as pas_last_hour,
            COUNT(DISTINCT mlb_player_id) as players_last_hour
        FROM milb_plate_appearances
        WHERE created_at >= NOW() - INTERVAL '1 hour'
    """))
    row = result.fetchone()

    print(f"\nLast Hour Activity:")
    print(f"  PAs collected: {row[0]:,}")
    print(f"  Players: {row[1]}")

    # PA coverage by season
    result = conn.execute(text("""
        SELECT
            season,
            COUNT(DISTINCT mlb_player_id) as prospects_with_pas,
            COUNT(*) as total_pas
        FROM milb_plate_appearances
        WHERE mlb_player_id IN (
            SELECT CAST(mlb_player_id AS INTEGER)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL AND mlb_player_id != ''
        )
        GROUP BY season
        ORDER BY season DESC
    """))

    print(f"\nPA Coverage by Season (Prospects Only):")
    print(f"{'Season':<8} {'Prospects':<12} {'Total PAs':<12}")
    print("-"*40)
    for row in result:
        print(f"{row[0]:<8} {row[1]:<12} {row[2]:<12,}")

    # Overall prospect PA coverage
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

    result = conn.execute(text("""
        SELECT COUNT(*) FROM prospects
        WHERE mlb_player_id IS NOT NULL AND mlb_player_id != ''
    """))
    total_prospects = result.fetchone()[0]

    print(f"\nOverall Prospect Coverage:")
    print(f"  Prospects with PA data: {prospects_with_pas} / {total_prospects} ({prospects_with_pas/total_prospects*100:.1f}%)")
    print(f"  Prospects missing PA data: {total_prospects - prospects_with_pas}")

    # Pitch collection statistics
    print("\n[2] PITCH-BY-PITCH COLLECTION")
    print("-"*80)

    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_batter_id) as unique_batters,
            COUNT(DISTINCT game_pk) as unique_games,
            MIN(created_at) as first_insert,
            MAX(created_at) as last_insert
        FROM milb_batter_pitches
    """))
    row = result.fetchone()

    print(f"Total pitches in database: {row[0]:,}")
    print(f"Unique batters: {row[1]:,}")
    print(f"Unique games: {row[2]:,}")
    print(f"First insert: {row[3]}")
    print(f"Last insert: {row[4]}")

    # Pitch activity in last hour
    result = conn.execute(text("""
        SELECT
            COUNT(*) as pitches_last_hour,
            COUNT(DISTINCT mlb_batter_id) as batters_last_hour
        FROM milb_batter_pitches
        WHERE created_at >= NOW() - INTERVAL '1 hour'
    """))
    row = result.fetchone()

    print(f"\nLast Hour Activity:")
    print(f"  Pitches collected: {row[0]:,}")
    print(f"  Batters: {row[1]}")

    # Pitch coverage by season
    result = conn.execute(text("""
        SELECT
            season,
            COUNT(DISTINCT mlb_batter_id) as batters_with_pitches,
            COUNT(*) as total_pitches,
            COUNT(*) FILTER (WHERE is_final_pitch = true) as final_pitches
        FROM milb_batter_pitches
        WHERE mlb_batter_id IN (
            SELECT CAST(mlb_player_id AS INTEGER)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL AND mlb_player_id != ''
        )
        GROUP BY season
        ORDER BY season DESC
    """))

    print(f"\nPitch Coverage by Season (Prospects Only):")
    print(f"{'Season':<8} {'Prospects':<12} {'Total Pitches':<15} {'Final Pitches':<15}")
    print("-"*60)
    for row in result:
        print(f"{row[0]:<8} {row[1]:<12} {row[2]:<15,} {row[3]:<15,}")

    # Overall prospect pitch coverage
    result = conn.execute(text("""
        SELECT
            COUNT(DISTINCT mlb_batter_id) as prospects_with_pitches
        FROM milb_batter_pitches
        WHERE mlb_batter_id IN (
            SELECT CAST(mlb_player_id AS INTEGER)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL AND mlb_player_id != ''
        )
    """))
    prospects_with_pitches = result.fetchone()[0]

    print(f"\nOverall Prospect Coverage:")
    print(f"  Prospects with pitch data: {prospects_with_pitches} / {total_prospects} ({prospects_with_pitches/total_prospects*100:.1f}%)")
    print(f"  Prospects missing pitch data: {total_prospects - prospects_with_pitches}")

    # Combined coverage
    print("\n[3] COMBINED COVERAGE (PA + Pitch Data)")
    print("-"*80)

    result = conn.execute(text("""
        WITH coverage AS (
            SELECT
                CAST(p.mlb_player_id AS INTEGER) as player_id,
                CASE WHEN pa.mlb_player_id IS NOT NULL THEN 1 ELSE 0 END as has_pa,
                CASE WHEN bp.mlb_batter_id IS NOT NULL THEN 1 ELSE 0 END as has_pitch
            FROM prospects p
            LEFT JOIN (SELECT DISTINCT mlb_player_id FROM milb_plate_appearances) pa
                ON pa.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            LEFT JOIN (SELECT DISTINCT mlb_batter_id FROM milb_batter_pitches) bp
                ON bp.mlb_batter_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE p.mlb_player_id IS NOT NULL AND p.mlb_player_id != ''
        )
        SELECT
            SUM(CASE WHEN has_pa = 1 AND has_pitch = 1 THEN 1 ELSE 0 END) as both,
            SUM(CASE WHEN has_pa = 1 AND has_pitch = 0 THEN 1 ELSE 0 END) as pa_only,
            SUM(CASE WHEN has_pa = 0 AND has_pitch = 1 THEN 1 ELSE 0 END) as pitch_only,
            SUM(CASE WHEN has_pa = 0 AND has_pitch = 0 THEN 1 ELSE 0 END) as neither,
            SUM(CASE WHEN has_pa = 1 OR has_pitch = 1 THEN 1 ELSE 0 END) as either
        FROM coverage
    """))
    row = result.fetchone()

    print(f"Prospects with BOTH PA and Pitch data: {row[0]} ({row[0]/total_prospects*100:.1f}%)")
    print(f"Prospects with ONLY PA data: {row[1]} ({row[1]/total_prospects*100:.1f}%)")
    print(f"Prospects with ONLY Pitch data: {row[2]} ({row[2]/total_prospects*100:.1f}%)")
    print(f"Prospects with EITHER PA or Pitch: {row[4]} ({row[4]/total_prospects*100:.1f}%)")
    print(f"Prospects with NO data: {row[3]} ({row[3]/total_prospects*100:.1f}%)")

print("\n" + "="*80)
print("END OF REPORT")
print("="*80)
