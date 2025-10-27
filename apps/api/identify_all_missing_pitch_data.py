#!/usr/bin/env python3
"""
Identify all players with missing pitch data and prepare for collection.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime
import csv
import json

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def identify_missing_pitch_data():
    """Identify all players with game logs but missing pitch data"""

    with engine.connect() as conn:
        print("=" * 80)
        print("IDENTIFYING ALL PLAYERS WITH MISSING PITCH DATA")
        print("=" * 80)

        # Get all hitters with missing pitch data
        query = text("""
            WITH player_stats AS (
                SELECT
                    p.id as prospect_id,
                    p.name,
                    p.mlb_player_id,
                    p.position,
                    p.organization,
                    -- 2025 Season
                    COUNT(DISTINCT CASE WHEN gl.season = 2025 THEN gl.game_pk END) as games_2025,
                    COUNT(DISTINCT CASE WHEN bp.season = 2025 THEN bp.game_pk END) as games_with_pitches_2025,
                    COUNT(CASE WHEN bp.season = 2025 THEN 1 END) as pitches_2025,
                    SUM(CASE WHEN gl.season = 2025 THEN gl.plate_appearances ELSE 0 END) as pas_2025,
                    -- 2024 Season
                    COUNT(DISTINCT CASE WHEN gl.season = 2024 THEN gl.game_pk END) as games_2024,
                    COUNT(DISTINCT CASE WHEN bp.season = 2024 THEN bp.game_pk END) as games_with_pitches_2024,
                    COUNT(CASE WHEN bp.season = 2024 THEN 1 END) as pitches_2024,
                    SUM(CASE WHEN gl.season = 2024 THEN gl.plate_appearances ELSE 0 END) as pas_2024
                FROM prospects p
                LEFT JOIN milb_game_logs gl
                    ON p.mlb_player_id::text = gl.mlb_player_id::text
                    AND gl.season IN (2024, 2025)
                LEFT JOIN milb_batter_pitches bp
                    ON p.mlb_player_id::integer = bp.mlb_batter_id
                    AND bp.season IN (2024, 2025)
                WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                    AND p.mlb_player_id IS NOT NULL
                GROUP BY p.id, p.name, p.mlb_player_id, p.position, p.organization
                HAVING (COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk))
                    OR (COUNT(DISTINCT gl.game_pk) > 0 AND COUNT(DISTINCT bp.game_pk) = 0)
            )
            SELECT
                *,
                games_2025 - games_with_pitches_2025 as missing_2025,
                games_2024 - games_with_pitches_2024 as missing_2024,
                CASE
                    WHEN games_2025 > 0
                    THEN ROUND((games_with_pitches_2025::numeric / games_2025) * 100, 1)
                    ELSE 100
                END as coverage_2025,
                CASE
                    WHEN games_2024 > 0
                    THEN ROUND((games_with_pitches_2024::numeric / games_2024) * 100, 1)
                    ELSE 100
                END as coverage_2024
            FROM player_stats
            WHERE (games_2025 - games_with_pitches_2025 > 0)
               OR (games_2024 - games_with_pitches_2024 > 0)
            ORDER BY missing_2025 DESC, missing_2024 DESC
        """)

        results = conn.execute(query).fetchall()

        # Separate by priority
        critical_2025 = []  # Missing 50+ games in 2025
        high_priority_2025 = []  # Missing 20-50 games in 2025
        medium_priority_2025 = []  # Missing 5-20 games in 2025
        low_priority_2025 = []  # Missing 1-5 games in 2025
        only_2024_missing = []  # Only missing 2024 data

        for row in results:
            if row.missing_2025 >= 50:
                critical_2025.append(row)
            elif row.missing_2025 >= 20:
                high_priority_2025.append(row)
            elif row.missing_2025 >= 5:
                medium_priority_2025.append(row)
            elif row.missing_2025 > 0:
                low_priority_2025.append(row)
            elif row.missing_2024 > 0:
                only_2024_missing.append(row)

        # Print summary
        print(f"\nSUMMARY OF MISSING PITCH DATA:")
        print(f"  Critical (50+ games missing in 2025): {len(critical_2025)} players")
        print(f"  High Priority (20-50 games missing in 2025): {len(high_priority_2025)} players")
        print(f"  Medium Priority (5-20 games missing in 2025): {len(medium_priority_2025)} players")
        print(f"  Low Priority (1-5 games missing in 2025): {len(low_priority_2025)} players")
        print(f"  2024 Only: {len(only_2024_missing)} players")
        print(f"  TOTAL: {len(results)} players need pitch collection")

        # Show critical cases
        if critical_2025:
            print("\n" + "=" * 80)
            print("CRITICAL - PLAYERS MISSING 50+ GAMES OF PITCH DATA IN 2025:")
            print("-" * 80)
            print(f"{'Name':<30} {'Pos':<5} {'Team':<5} {'Games':<7} {'w/Pitch':<8} {'Missing':<8} {'Coverage':<10}")
            print("-" * 80)
            for row in critical_2025[:20]:
                print(f"{row.name:<30} {row.position:<5} {row.organization:<5} "
                      f"{row.games_2025:<7} {row.games_with_pitches_2025:<8} "
                      f"{row.missing_2025:<8} {row.coverage_2025:>9.1f}%")

        # Create collection list JSON
        collection_list = []

        # Add all players to collection list with priority
        for row in critical_2025:
            collection_list.append({
                'prospect_id': row.prospect_id,
                'name': row.name,
                'mlb_player_id': row.mlb_player_id,
                'position': row.position,
                'priority': 1,
                'missing_2025': row.missing_2025,
                'missing_2024': row.missing_2024
            })

        for row in high_priority_2025:
            collection_list.append({
                'prospect_id': row.prospect_id,
                'name': row.name,
                'mlb_player_id': row.mlb_player_id,
                'position': row.position,
                'priority': 2,
                'missing_2025': row.missing_2025,
                'missing_2024': row.missing_2024
            })

        for row in medium_priority_2025:
            collection_list.append({
                'prospect_id': row.prospect_id,
                'name': row.name,
                'mlb_player_id': row.mlb_player_id,
                'position': row.position,
                'priority': 3,
                'missing_2025': row.missing_2025,
                'missing_2024': row.missing_2024
            })

        # Save collection list
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pitch_collection_list_{timestamp}.json"
        with open(filename, 'w') as f:
            json.dump(collection_list, f, indent=2)

        print(f"\n✅ Saved collection list to: {filename}")
        print(f"   Total players to collect: {len(collection_list)}")

        # Also save detailed CSV
        csv_filename = f"pitch_collection_details_{timestamp}.csv"
        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'MLB_ID', 'Position', 'Team',
                           'Games_2025', 'With_Pitch_2025', 'Missing_2025', 'Coverage_2025',
                           'Games_2024', 'With_Pitch_2024', 'Missing_2024', 'Coverage_2024'])

            for row in results:
                writer.writerow([
                    row.name, row.mlb_player_id, row.position, row.organization,
                    row.games_2025, row.games_with_pitches_2025, row.missing_2025, f"{row.coverage_2025}%",
                    row.games_2024, row.games_with_pitches_2024, row.missing_2024, f"{row.coverage_2024}%"
                ])

        print(f"✅ Saved detailed CSV to: {csv_filename}")

        return collection_list

if __name__ == "__main__":
    collection_list = identify_missing_pitch_data()

    print("\n" + "=" * 80)
    print("READY TO START PITCH COLLECTION")
    print("=" * 80)
    print(f"Identified {len(collection_list)} players needing pitch data collection")
    print("\nNext step: Run collect_missing_pitch_data.py to start collection")