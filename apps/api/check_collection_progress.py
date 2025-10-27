#!/usr/bin/env python3
"""Check real-time collection progress"""

import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def check_progress():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("PITCH DATA COLLECTION PROGRESS CHECK")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Check Leo De Vries specifically
    print("\nLEO DE VRIES STATUS:")
    cur.execute("""
        SELECT
            (SELECT COUNT(DISTINCT game_pk) FROM milb_game_logs
             WHERE mlb_player_id = 815888 AND season = 2025) as total_games,
            (SELECT COUNT(DISTINCT game_pk) FROM milb_batter_pitches
             WHERE mlb_batter_id = 815888 AND season = 2025) as games_with_pitches,
            (SELECT COUNT(*) FROM milb_batter_pitches
             WHERE mlb_batter_id = 815888 AND season = 2025) as total_pitches,
            (SELECT MAX(created_at) FROM milb_batter_pitches
             WHERE mlb_batter_id = 815888) as last_update
    """)

    result = cur.fetchone()
    print(f"  Total games in 2025: {result[0]}")
    print(f"  Games with pitch data: {result[1]}")
    print(f"  Missing games: {result[0] - result[1]}")
    print(f"  Total pitches: {result[2]}")
    print(f"  Last update: {result[3]}")

    # Check other key players
    print("\nOTHER KEY PLAYERS:")
    cur.execute("""
        WITH player_stats AS (
            SELECT
                p.name,
                COUNT(DISTINCT gl.game_pk) as total_games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                COUNT(bp.*) as total_pitches
            FROM prospects p
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id::text = gl.mlb_player_id::text
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp
                ON p.mlb_player_id::integer = bp.mlb_batter_id
                AND bp.season = 2025
            WHERE p.name IN ('Bryce Eldridge', 'Trey Lipscomb', 'Aidan Miller', 'Max Clark')
            GROUP BY p.name
        )
        SELECT * FROM player_stats ORDER BY name
    """)

    results = cur.fetchall()
    for row in results:
        coverage = (row[2] / row[1] * 100) if row[1] > 0 else 0
        print(f"  {row[0]:<20}: {row[2]}/{row[1]} games ({coverage:.1f}% coverage), {row[3]} pitches")

    # Check recent additions
    print("\nRECENT ADDITIONS (last 5 minutes):")
    cur.execute("""
        SELECT
            COUNT(*) as new_pitches,
            COUNT(DISTINCT mlb_batter_id) as players,
            COUNT(DISTINCT game_pk) as games
        FROM milb_batter_pitches
        WHERE created_at > NOW() - INTERVAL '5 minutes'
    """)

    result = cur.fetchone()
    print(f"  New pitches: {result[0]}")
    print(f"  Players updated: {result[1]}")
    print(f"  Games updated: {result[2]}")

    # Overall progress
    print("\nOVERALL DATABASE STATUS:")
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2025) as pitches_2025,
            (SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season = 2025) as players_2025,
            (SELECT COUNT(DISTINCT game_pk) FROM milb_batter_pitches WHERE season = 2025) as games_2025
    """)

    result = cur.fetchone()
    print(f"  Total 2025 pitches: {result[0]:,}")
    print(f"  Players with data: {result[1]}")
    print(f"  Games with data: {result[2]}")

    conn.close()

if __name__ == "__main__":
    check_progress()