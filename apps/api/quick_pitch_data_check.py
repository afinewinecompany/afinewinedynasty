#!/usr/bin/env python3
"""Quick check for pitch data completeness"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Check Leo De Vries
    print("LEO DE VRIES ANALYSIS:")
    print("=" * 60)

    query = text("""
        SELECT
            (SELECT COUNT(DISTINCT game_pk) FROM milb_game_logs
             WHERE mlb_player_id = 815888 AND season = 2025) as total_games,
            (SELECT COUNT(DISTINCT game_pk) FROM milb_batter_pitches
             WHERE mlb_batter_id = 815888 AND season = 2025) as games_with_pitches,
            (SELECT COUNT(*) FROM milb_batter_pitches
             WHERE mlb_batter_id = 815888 AND season = 2025) as total_pitches,
            (SELECT SUM(plate_appearances) FROM milb_game_logs
             WHERE mlb_player_id = 815888 AND season = 2025) as total_pas
    """)

    result = conn.execute(query).fetchone()

    print(f"2025 Season Stats:")
    print(f"  Total games played: {result.total_games}")
    print(f"  Games with pitch data: {result.games_with_pitches}")
    print(f"  Missing pitch data: {result.total_games - result.games_with_pitches} games")
    print(f"  Total pitches collected: {result.total_pitches}")
    print(f"  Total plate appearances: {result.total_pas}")

    if result.total_pas:
        expected = int(result.total_pas * 3.8)
        coverage = (result.total_pitches / expected * 100) if expected > 0 else 0
        print(f"  Expected pitches (3.8/PA): ~{expected}")
        print(f"  Coverage: {coverage:.1f}%")

    # Check a few more players
    print("\n" + "=" * 60)
    print("OTHER TOP PROSPECTS:")
    print("=" * 60)

    query = text("""
        WITH player_stats AS (
            SELECT
                p.name,
                COUNT(DISTINCT gl.game_pk) as games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                COUNT(bp.*) as pitches,
                SUM(gl.plate_appearances) as pas
            FROM prospects p
            LEFT JOIN milb_game_logs gl ON p.mlb_player_id::text = gl.mlb_player_id::text
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
                AND bp.season = 2025
            WHERE p.name IN ('Bryce Eldridge', 'Jackson Holliday', 'Junior Caminero')
            GROUP BY p.name
        )
        SELECT * FROM player_stats
    """)

    results = conn.execute(query).fetchall()

    for row in results:
        missing = row.games - row.games_with_pitches if row.games else 0
        print(f"\n{row.name}:")
        print(f"  Games: {row.games}, With pitch data: {row.games_with_pitches}")
        print(f"  Missing: {missing} games")
        print(f"  Pitches: {row.pitches}, PAs: {row.pas}")
        if row.pas:
            coverage = (row.pitches / (row.pas * 3.8) * 100) if row.pas else 0
            print(f"  Coverage: {coverage:.1f}%")

print("\n" + "=" * 60)
print("CONCLUSION:")
print("Leo De Vries is missing pitch data for most of his games!")
print("This needs to be collected to show accurate rankings.")