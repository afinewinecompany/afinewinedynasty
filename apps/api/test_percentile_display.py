#!/usr/bin/env python3
"""
Test script to check percentile data in composite rankings
and identify display issues
"""

import psycopg2
import json
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def check_percentile_data():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 60)
    print("COMPOSITE RANKINGS PERCENTILE DATA CHECK")
    print("=" * 60)

    # Check if materialized views exist for percentiles
    cur.execute("""
        SELECT
            tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE '%percentile%'
        ORDER BY tablename
    """)

    print("\n1. Tables/Views with 'percentile' in name:")
    tables = cur.fetchall()
    if tables:
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("  None found")

    # Check a sample of prospects with pitch data
    cur.execute("""
        WITH prospect_pitch_stats AS (
            SELECT
                p.id,
                p.name,
                p.position,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                COUNT(bp.*) as total_pitches,
                AVG(CASE WHEN bp.start_speed IS NOT NULL THEN bp.start_speed END) as avg_velo,
                AVG(CASE WHEN bp.launch_speed IS NOT NULL THEN bp.launch_speed END) as avg_exit_velo
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE bp.season = 2025
            GROUP BY p.id, p.name, p.position
            HAVING COUNT(bp.*) > 100
            ORDER BY COUNT(bp.*) DESC
            LIMIT 5
        )
        SELECT * FROM prospect_pitch_stats
    """)

    print("\n2. Sample Prospects with Pitch Data:")
    prospects = cur.fetchall()
    for p in prospects:
        print(f"\n  {p[1]} ({p[2]})")
        print(f"    Games: {p[3]}, Pitches: {p[4]}")
        print(f"    Avg Velo: {f'{p[5]:.1f}' if p[5] else 'N/A'}")
        print(f"    Avg Exit Velo: {f'{p[6]:.1f}' if p[6] else 'N/A'}")

    # Check if we have percentile calculations stored
    cur.execute("""
        SELECT
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name IN ('milb_batter_pitches', 'milb_pitcher_pitches')
        AND column_name LIKE '%percentile%'
        ORDER BY column_name
    """)

    print("\n3. Percentile columns in pitch tables:")
    cols = cur.fetchall()
    if cols:
        for col in cols:
            print(f"  - {col[0]} ({col[1]})")
    else:
        print("  No percentile columns found in pitch tables")

    # Check how percentiles are being calculated (look for views or functions)
    cur.execute("""
        SELECT
            routine_name,
            routine_type
        FROM information_schema.routines
        WHERE routine_schema = 'public'
        AND (routine_name LIKE '%percentile%' OR routine_name LIKE '%composite%')
        ORDER BY routine_name
    """)

    print("\n4. Functions/Procedures with percentile/composite logic:")
    funcs = cur.fetchall()
    if funcs:
        for func in funcs:
            print(f"  - {func[0]} ({func[1]})")
    else:
        print("  No percentile functions found")

    # Check actual percentile values calculation
    print("\n5. Manual Percentile Calculation Test:")

    # For exit velocity percentiles
    cur.execute("""
        WITH exit_velo_stats AS (
            SELECT
                mlb_batter_id,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed) as exit_velo_90th
            FROM milb_batter_pitches
            WHERE season = 2025
            AND launch_speed IS NOT NULL
            AND launch_speed > 0
            GROUP BY mlb_batter_id
            HAVING COUNT(*) > 50
        ),
        percentiles AS (
            SELECT
                exit_velo_90th,
                PERCENT_RANK() OVER (ORDER BY exit_velo_90th) * 100 as percentile
            FROM exit_velo_stats
        )
        SELECT
            COUNT(*) as total_players,
            MIN(exit_velo_90th) as min_90th_velo,
            MAX(exit_velo_90th) as max_90th_velo,
            AVG(exit_velo_90th) as avg_90th_velo,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY exit_velo_90th) as median_90th_velo
        FROM exit_velo_stats
    """)

    result = cur.fetchone()
    if result and result[0] > 0:
        print(f"  Players with exit velo data: {result[0]}")
        print(f"  90th percentile exit velo range: {result[1]:.1f} - {result[2]:.1f} mph")
        print(f"  Average 90th percentile: {result[3]:.1f} mph")
        print(f"  Median 90th percentile: {result[4]:.1f} mph")
    else:
        print("  No exit velocity data found")

    # Check for NaN or null values that could cause display issues
    cur.execute("""
        SELECT
            COUNT(*) as total_pitches,
            SUM(CASE WHEN launch_speed IS NULL THEN 1 ELSE 0 END) as null_exit_velo,
            SUM(CASE WHEN launch_speed = 'NaN'::float THEN 1 ELSE 0 END) as nan_exit_velo,
            SUM(CASE WHEN launch_speed < 0 THEN 1 ELSE 0 END) as negative_exit_velo,
            SUM(CASE WHEN launch_speed > 120 THEN 1 ELSE 0 END) as extreme_exit_velo
        FROM milb_batter_pitches
        WHERE season = 2025
    """)

    print("\n6. Data Quality Check:")
    quality = cur.fetchone()
    print(f"  Total pitches: {quality[0]:,}")
    print(f"  NULL exit velocities: {quality[1]:,}")
    print(f"  NaN exit velocities: {quality[2]:,}")
    print(f"  Negative exit velocities: {quality[3]:,}")
    print(f"  Extreme exit velocities (>120mph): {quality[4]:,}")

    # Check Leo De Vries specifically since he was mentioned
    cur.execute("""
        WITH leo_stats AS (
            SELECT
                p.name,
                COUNT(DISTINCT bp.game_pk) as games,
                COUNT(bp.*) as pitches,
                AVG(CASE WHEN bp.launch_speed > 0 THEN bp.launch_speed END) as avg_exit_velo,
                PERCENTILE_CONT(0.9) WITHIN GROUP (
                    ORDER BY CASE WHEN bp.launch_speed > 0 THEN bp.launch_speed END
                ) as exit_velo_90th,
                SUM(CASE WHEN bp.description = 'hit_into_play' THEN 1 ELSE 0 END) as balls_in_play
            FROM prospects p
            JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE p.name = 'Leo De Vries'
            AND bp.season = 2025
            GROUP BY p.name
        )
        SELECT * FROM leo_stats
    """)

    print("\n7. Leo De Vries Specific Check:")
    leo = cur.fetchone()
    if leo:
        print(f"  Games: {leo[1]}, Pitches: {leo[2]}")
        print(f"  Avg Exit Velo: {leo[3]:.1f if leo[3] else 'N/A'}")
        print(f"  90th %ile Exit Velo: {leo[4]:.1f if leo[4] else 'N/A'}")
        print(f"  Balls in Play: {leo[5]}")
    else:
        print("  No data found for Leo De Vries")

    conn.close()

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    check_percentile_data()