#!/usr/bin/env python3
"""
Simple Data Audit for A Fine Wine Dynasty Prospects
Focuses on the data that actually exists in the database
"""

import asyncio
import asyncpg
import pandas as pd
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

async def run_audit():
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
    conn = await asyncpg.connect(DATABASE_URL)

    print("="*80)
    print("A FINE WINE DYNASTY - PROSPECT DATA AUDIT")
    print("="*80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. PROSPECTS
    print("\n[1] PROSPECTS OVERVIEW")
    print("-" * 80)

    prospect_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT mlb_id) as with_mlb_id,
            COUNT(DISTINCT mlb_player_id) as with_player_id,
            COUNT(DISTINCT fg_player_id) as with_fg_id,
            COUNT(DISTINCT position) as positions,
            COUNT(DISTINCT organization) as organizations
        FROM prospects
    """)

    print(f"Total Prospects: {prospect_stats['total']:,}")
    print(f"  - With MLB ID: {prospect_stats['with_mlb_id']:,}")
    print(f"  - With Player ID: {prospect_stats['with_player_id']:,}")
    print(f"  - With Fangraphs ID: {prospect_stats['with_fg_id']:,}")
    print(f"  - Unique Positions: {prospect_stats['positions']}")
    print(f"  - Unique Organizations: {prospect_stats['organizations']}")

    # Position breakdown
    positions = await conn.fetch("""
        SELECT position, COUNT(*) as count
        FROM prospects
        GROUP BY position
        ORDER BY count DESC
        LIMIT 10
    """)

    print("\nTop Positions:")
    for pos in positions:
        print(f"  {pos['position'] or 'Unknown':15s}: {pos['count']:4d} prospects")

    # 2. MILB GAME LOGS
    print("\n\n[2] MILB GAME LOGS (Performance Data)")
    print("-" * 80)

    game_log_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_records,
            COUNT(DISTINCT mlb_player_id) as unique_players,
            COUNT(DISTINCT season) as seasons,
            MIN(season) as earliest_season,
            MAX(season) as latest_season,
            COUNT(CASE WHEN at_bats > 0 THEN 1 END) as batting_records,
            COUNT(CASE WHEN innings_pitched > 0 THEN 1 END) as pitching_records
        FROM milb_game_logs
    """)

    print(f"Total Game Log Records: {game_log_stats['total_records']:,}")
    print(f"  - Unique Players: {game_log_stats['unique_players']:,}")
    print(f"  - Seasons Covered: {game_log_stats['earliest_season']} - {game_log_stats['latest_season']}")
    print(f"  - Batting Records: {game_log_stats['batting_records']:,}")
    print(f"  - Pitching Records: {game_log_stats['pitching_records']:,}")

    # Season breakdown
    seasons = await conn.fetch("""
        SELECT season,
               COUNT(*) as records,
               COUNT(DISTINCT mlb_player_id) as players
        FROM milb_game_logs
        GROUP BY season
        ORDER BY season DESC
    """)

    print("\nBy Season:")
    for s in seasons:
        print(f"  {s['season']}: {s['records']:,} records, {s['players']} players")

    # Level breakdown
    levels = await conn.fetch("""
        SELECT level,
               COUNT(*) as records,
               COUNT(DISTINCT mlb_player_id) as players
        FROM milb_game_logs
        WHERE level IS NOT NULL
        GROUP BY level
        ORDER BY records DESC
    """)

    print("\nBy Level:")
    for l in levels:
        print(f"  {l['level']:10s}: {l['records']:,} records, {l['players']} players")

    # 3. PITCH DATA
    print("\n\n[3] PITCH-BY-PITCH DATA")
    print("-" * 80)

    pitcher_pitch_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_pitcher_id) as pitchers,
            COUNT(DISTINCT season) as seasons,
            MIN(season) as earliest,
            MAX(season) as latest,
            COUNT(DISTINCT pitch_type) as pitch_types,
            COUNT(CASE WHEN start_speed IS NOT NULL THEN 1 END) as with_velo,
            COUNT(CASE WHEN spin_rate IS NOT NULL THEN 1 END) as with_spin
        FROM milb_pitcher_pitches
    """)

    print(f"Pitcher Pitches: {pitcher_pitch_stats['total_pitches']:,}")
    print(f"  - Unique Pitchers: {pitcher_pitch_stats['pitchers']:,}")
    print(f"  - Seasons: {pitcher_pitch_stats['earliest']} - {pitcher_pitch_stats['latest']}")
    print(f"  - Pitch Types: {pitcher_pitch_stats['pitch_types']}")
    print(f"  - With Velocity: {pitcher_pitch_stats['with_velo']:,}")
    print(f"  - With Spin Rate: {pitcher_pitch_stats['with_spin']:,}")

    batter_pitch_stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as total_pitches,
            COUNT(DISTINCT mlb_batter_id) as batters,
            COUNT(CASE WHEN swing = true THEN 1 END) as swings,
            COUNT(CASE WHEN contact = true THEN 1 END) as contacts
        FROM milb_batter_pitches
    """)

    print(f"\nBatter Pitches: {batter_pitch_stats['total_pitches']:,}")
    print(f"  - Unique Batters: {batter_pitch_stats['batters']:,}")
    print(f"  - Swings: {batter_pitch_stats['swings']:,}")
    print(f"  - Contacts: {batter_pitch_stats['contacts']:,}")

    # Pitch types
    pitch_types = await conn.fetch("""
        SELECT pitch_type,
               pitch_type_description,
               COUNT(*) as count,
               AVG(start_speed) as avg_velo
        FROM milb_pitcher_pitches
        WHERE pitch_type IS NOT NULL
        GROUP BY pitch_type, pitch_type_description
        ORDER BY count DESC
        LIMIT 10
    """)

    print("\nTop Pitch Types:")
    for pt in pitch_types:
        avg_velo = f"{pt['avg_velo']:.1f} mph" if pt['avg_velo'] else "N/A"
        desc = pt['pitch_type_description'] or "Unknown"
        print(f"  {pt['pitch_type']:3s} - {desc:20s}: {pt['count']:,} pitches, {avg_velo}")

    # 4. DATA COVERAGE
    print("\n\n[4] DATA COVERAGE BY PROSPECT")
    print("-" * 80)

    coverage = await conn.fetchrow("""
        WITH coverage_data AS (
            SELECT
                p.id,
                p.name,
                p.position,
                CASE WHEN gl.player_id IS NOT NULL THEN 1 ELSE 0 END as has_game_logs,
                CASE WHEN pp.pitcher_id IS NOT NULL THEN 1 ELSE 0 END as has_pitcher_pitches,
                CASE WHEN bp.batter_id IS NOT NULL THEN 1 ELSE 0 END as has_batter_pitches
            FROM prospects p
            LEFT JOIN (SELECT DISTINCT mlb_player_id as player_id FROM milb_game_logs) gl ON p.mlb_player_id = gl.player_id
            LEFT JOIN (SELECT DISTINCT mlb_pitcher_id as pitcher_id FROM milb_pitcher_pitches) pp ON p.mlb_player_id = pp.pitcher_id
            LEFT JOIN (SELECT DISTINCT mlb_batter_id as batter_id FROM milb_batter_pitches) bp ON p.mlb_player_id = bp.batter_id
        )
        SELECT
            COUNT(*) as total_prospects,
            SUM(has_game_logs) as with_game_logs,
            SUM(has_pitcher_pitches) as with_pitcher_pitches,
            SUM(has_batter_pitches) as with_batter_pitches,
            SUM(CASE WHEN has_game_logs = 1 AND (has_pitcher_pitches = 1 OR has_batter_pitches = 1) THEN 1 ELSE 0 END) as with_complete_data
        FROM coverage_data
    """)

    total = coverage['total_prospects']
    print(f"Total Prospects: {total:,}")
    print(f"  - With Game Logs: {coverage['with_game_logs']:,} ({coverage['with_game_logs']/total*100:.1f}%)")
    print(f"  - With Pitcher Pitches: {coverage['with_pitcher_pitches']:,} ({coverage['with_pitcher_pitches']/total*100:.1f}%)")
    print(f"  - With Batter Pitches: {coverage['with_batter_pitches']:,} ({coverage['with_batter_pitches']/total*100:.1f}%)")
    print(f"  - With Complete Data (Game Logs + Pitch Data): {coverage['with_complete_data']:,} ({coverage['with_complete_data']/total*100:.1f}%)")

    # Get sample of prospects with complete data
    complete_prospects = await conn.fetch("""
        WITH coverage_data AS (
            SELECT
                p.id,
                p.name,
                p.position,
                p.organization,
                CASE WHEN gl.player_id IS NOT NULL THEN 1 ELSE 0 END as has_game_logs,
                CASE WHEN pp.pitcher_id IS NOT NULL THEN 1 ELSE 0 END as has_pitcher_pitches,
                CASE WHEN bp.batter_id IS NOT NULL THEN 1 ELSE 0 END as has_batter_pitches
            FROM prospects p
            LEFT JOIN (SELECT DISTINCT mlb_player_id as player_id FROM milb_game_logs) gl ON p.mlb_player_id = gl.player_id
            LEFT JOIN (SELECT DISTINCT mlb_pitcher_id as pitcher_id FROM milb_pitcher_pitches) pp ON p.mlb_player_id = pp.pitcher_id
            LEFT JOIN (SELECT DISTINCT mlb_batter_id as batter_id FROM milb_batter_pitches) bp ON p.mlb_player_id = bp.batter_id
        )
        SELECT name, position, organization
        FROM coverage_data
        WHERE has_game_logs = 1
            AND (has_pitcher_pitches = 1 OR has_batter_pitches = 1)
        LIMIT 15
    """)

    print("\nSample Prospects with Complete Data:")
    for p in complete_prospects:
        print(f"  - {p['name']} ({p['position']}, {p['organization']})")

    # 5. EXPORT CSV
    print("\n\n[5] GENERATING DETAILED CSV...")
    print("-" * 80)

    csv_data = await conn.fetch("""
        SELECT
            p.id,
            p.name,
            p.position,
            p.organization,
            p.level,
            p.age,
            COALESCE(gl.game_count, 0) as game_log_count,
            COALESCE(gl.seasons, '') as seasons,
            COALESCE(pp.pitch_count, 0) as pitches_thrown,
            COALESCE(bp.pitch_count, 0) as pitches_faced
        FROM prospects p
        LEFT JOIN (
            SELECT mlb_player_id,
                   COUNT(*) as game_count,
                   STRING_AGG(DISTINCT season::text, ', ' ORDER BY season::text) as seasons
            FROM milb_game_logs
            GROUP BY mlb_player_id
        ) gl ON p.mlb_player_id = gl.mlb_player_id
        LEFT JOIN (
            SELECT mlb_pitcher_id,
                   COUNT(*) as pitch_count
            FROM milb_pitcher_pitches
            GROUP BY mlb_pitcher_id
        ) pp ON p.mlb_player_id = pp.mlb_pitcher_id
        LEFT JOIN (
            SELECT mlb_batter_id,
                   COUNT(*) as pitch_count
            FROM milb_batter_pitches
            GROUP BY mlb_batter_id
        ) bp ON p.mlb_player_id = bp.mlb_batter_id
        ORDER BY
            CASE WHEN gl.game_count > 0 THEN 1 ELSE 0 END DESC,
            p.name
    """)

    df = pd.DataFrame(csv_data)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"prospect_data_coverage_{timestamp}.csv"
    df.to_csv(csv_filename, index=False)

    print(f"CSV saved: {csv_filename}")
    print(f"  - Total rows: {len(df):,}")

    await conn.close()

    print("\n" + "="*80)
    print("AUDIT COMPLETE!")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(run_audit())
