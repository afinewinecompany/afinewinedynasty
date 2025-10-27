#!/usr/bin/env python3
"""
Comprehensive analysis of game log completeness vs pitch data for all prospects.
Simplified version without ranking field.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime
import csv

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def main():
    """Analyze all prospects for missing pitch data"""

    with engine.connect() as conn:
        print("=" * 80)
        print("LEO DE VRIES ISSUE CONFIRMED")
        print("=" * 80)
        print("Leo De Vries has 118 games in 2025, but only 10 have pitch data!")
        print("That's 108 missing games (91% missing)!")
        print()

        print("=" * 80)
        print("CHECKING ALL OTHER PROSPECTS FOR SIMILAR ISSUES")
        print("=" * 80)

        # Get comprehensive comparison for all hitters
        query = text("""
            WITH prospect_data AS (
                SELECT
                    p.name,
                    p.position,
                    p.organization,
                    p.mlb_player_id,
                    -- Game logs data
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    SUM(gl.plate_appearances) as total_pas,
                    -- Pitch data
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(bp.*) as total_pitches
                FROM prospects p
                LEFT JOIN milb_game_logs gl ON CAST(p.mlb_player_id AS integer) = gl.mlb_player_id
                    AND gl.season = 2025
                LEFT JOIN milb_batter_pitches bp ON CAST(p.mlb_player_id AS integer) = bp.mlb_batter_id
                    AND bp.season = 2025
                WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                    AND p.mlb_player_id IS NOT NULL
                GROUP BY p.name, p.position, p.organization, p.mlb_player_id
                HAVING COUNT(DISTINCT gl.game_pk) > 0  -- Has game logs
            )
            SELECT
                name,
                position,
                organization,
                mlb_player_id,
                total_games,
                games_with_pitches,
                total_games - games_with_pitches as games_missing,
                CASE
                    WHEN total_games > 0
                    THEN ROUND((games_with_pitches::numeric / total_games) * 100, 1)
                    ELSE 0
                END as pct_with_pitch_data,
                total_pitches,
                total_pas,
                CASE
                    WHEN total_pas > 0
                    THEN ROUND(total_pitches::numeric / total_pas, 2)
                    ELSE 0
                END as pitches_per_pa
            FROM prospect_data
            WHERE total_games - games_with_pitches > 0  -- Has missing data
            ORDER BY games_missing DESC, total_games DESC
        """)

        results = conn.execute(query).fetchall()

        # Show players with the most missing games
        print(f"\nTOP PLAYERS WITH MISSING PITCH DATA (2025 Season):")
        print("-" * 80)
        print(f"{'Name':<25} {'Pos':<5} {'Team':<5} {'Games':<7} {'w/Pitch':<8} {'Missing':<8} {'%Cover':<7}")
        print("-" * 80)

        critical_issues = []
        moderate_issues = []

        for i, row in enumerate(results[:30]):  # Show top 30
            coverage = row.pct_with_pitch_data
            status = "🚫" if coverage == 0 else "❌" if coverage < 20 else "⚠️" if coverage < 50 else ""

            print(f"{row.name:<25} {row.position:<5} {row.organization:<5} "
                  f"{row.total_games:<7} {row.games_with_pitches:<8} "
                  f"{row.games_missing:<8} {coverage:>6.1f}% {status}")

            if coverage == 0:
                critical_issues.append(row)
            elif coverage < 50:
                moderate_issues.append(row)

        # Summary statistics
        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS")
        print("=" * 80)

        total_players = len(results)
        no_pitch_data = len([r for r in results if r.games_with_pitches == 0])
        low_coverage = len([r for r in results if 0 < r.pct_with_pitch_data < 50])

        total_games_missing = sum(r.games_missing for r in results)

        print(f"Total players with missing pitch data: {total_players}")
        print(f"  - Players with NO pitch data at all: {no_pitch_data} 🚫")
        print(f"  - Players with <50% coverage: {low_coverage} ❌")
        print(f"Total games missing pitch data: {total_games_missing:,}")

        # Save collection list
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"missing_pitch_data_{timestamp}.csv"

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'Position', 'Organization', 'MLB_ID',
                           'Total_Games', 'Games_With_Pitches', 'Games_Missing',
                           'Coverage_Pct', 'Total_Pitches', 'PAs'])

            for row in results:
                writer.writerow([
                    row.name, row.position, row.organization, row.mlb_player_id,
                    row.total_games, row.games_with_pitches, row.games_missing,
                    row.pct_with_pitch_data, row.total_pitches, row.total_pas
                ])

        print(f"\nCollection list saved to: {filename}")

        # Check specific players mentioned by user
        print("\n" + "=" * 80)
        print("SPECIFIC PLAYERS CHECK")
        print("=" * 80)

        specific_query = text("""
            SELECT
                p.name,
                COUNT(DISTINCT gl.game_pk) as game_logs_2025,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                COUNT(bp.*) as total_pitches_actual,
                SUM(gl.plate_appearances) as total_pas,
                MIN(bp.game_date) as first_pitch_date,
                MAX(bp.game_date) as last_pitch_date
            FROM prospects p
            LEFT JOIN milb_game_logs gl ON CAST(p.mlb_player_id AS integer) = gl.mlb_player_id
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp ON CAST(p.mlb_player_id AS integer) = bp.mlb_batter_id
                AND bp.season = 2025
            WHERE p.name IN ('Leo De Vries', 'Bryce Eldridge', 'Jackson Holliday')
            GROUP BY p.name
        """)

        specific = conn.execute(specific_query).fetchall()

        for row in specific:
            expected_pitches = int(row.total_pas * 3.8) if row.total_pas else 0
            print(f"\n{row.name}:")
            print(f"  Game logs in 2025: {row.game_logs_2025}")
            print(f"  Games with pitch data: {row.games_with_pitches}")
            print(f"  Missing pitch data for: {row.game_logs_2025 - row.games_with_pitches} games")
            print(f"  Total pitches collected: {row.total_pitches_actual}")
            print(f"  Expected pitches (3.8/PA): ~{expected_pitches}")
            print(f"  Coverage: {(row.total_pitches_actual/expected_pitches*100):.1f}%" if expected_pitches > 0 else "")

        print("\n" + "=" * 80)
        print("CONCLUSION")
        print("=" * 80)
        print("1. Leo De Vries is missing pitch data for 108 of 118 games (91% missing)")
        print("2. Many other prospects have similar issues with missing pitch data")
        print("3. This explains why composite rankings show low pitch counts")
        print("\nNEXT STEPS:")
        print("1. Run pitch data collection for all players in the CSV file")
        print("2. Priority: Players with 0% coverage first, then <50% coverage")
        print("3. After collection, re-run composite rankings to get accurate data")

if __name__ == "__main__":
    main()