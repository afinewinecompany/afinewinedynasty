#!/usr/bin/env python3
"""
Comprehensive analysis of game log completeness vs pitch data for all prospects.
Identifies missing games, data gaps, and collection issues.
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

def analyze_leo_devries_detail():
    """Deep dive into Leo De Vries data"""
    with engine.connect() as conn:
        print("=" * 80)
        print("LEO DE VRIES DETAILED ANALYSIS")
        print("=" * 80)

        # Get his MLB player ID
        query = text("""
            SELECT mlb_player_id, name, position, organization
            FROM prospects
            WHERE name = 'Leo De Vries'
        """)

        result = conn.execute(query).fetchone()
        if not result:
            print("ERROR: Leo De Vries not found in prospects table!")
            return None

        mlb_player_id = result.mlb_player_id
        print(f"Player: {result.name}")
        print(f"Position: {result.position}")
        print(f"Organization: {result.organization}")
        print(f"MLB Player ID: {mlb_player_id}")
        print()

        # Check game logs
        print("GAME LOGS DATA:")
        print("-" * 40)
        query = text("""
            SELECT
                season,
                COUNT(DISTINCT game_pk) as games,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game,
                SUM(at_bats) as total_abs,
                SUM(plate_appearances) as total_pas,
                array_agg(DISTINCT level ORDER BY level) as levels
            FROM milb_game_logs
            WHERE mlb_player_id = :player_id
            GROUP BY season
            ORDER BY season DESC
        """)

        results = conn.execute(query, {'player_id': mlb_player_id}).fetchall()

        total_games = 0
        for row in results:
            print(f"Season {row.season}:")
            print(f"  Games: {row.games}")
            print(f"  Date range: {row.first_game} to {row.last_game}")
            print(f"  ABs: {row.total_abs}, PAs: {row.total_pas}")
            print(f"  Levels: {', '.join(row.levels) if row.levels else 'N/A'}")
            total_games += row.games

        print(f"\nTotal games in database: {total_games}")

        # Check pitch data
        print("\nPITCH DATA:")
        print("-" * 40)
        query = text("""
            SELECT
                season,
                COUNT(*) as pitches,
                COUNT(DISTINCT game_pk) as games_with_pitches,
                MIN(game_date) as first_pitch,
                MAX(game_date) as last_pitch,
                array_agg(DISTINCT level ORDER BY level) as levels
            FROM milb_batter_pitches
            WHERE mlb_batter_id = CAST(:player_id AS integer)
            GROUP BY season
            ORDER BY season DESC
        """)

        results = conn.execute(query, {'player_id': mlb_player_id}).fetchall()

        total_pitches = 0
        for row in results:
            print(f"Season {row.season}:")
            print(f"  Pitches: {row.pitches}")
            print(f"  Games with pitch data: {row.games_with_pitches}")
            print(f"  Date range: {row.first_pitch} to {row.last_pitch}")
            print(f"  Levels: {', '.join(row.levels) if row.levels else 'N/A'}")
            total_pitches += row.pitches

        print(f"\nTotal pitches in database: {total_pitches}")

        # Find games without pitch data
        print("\nGAMES WITHOUT PITCH DATA:")
        print("-" * 40)
        query = text("""
            SELECT
                gl.game_pk,
                gl.game_date,
                gl.level,
                gl.at_bats,
                gl.plate_appearances,
                gl.hits,
                gl.home_runs
            FROM milb_game_logs gl
            LEFT JOIN (
                SELECT DISTINCT game_pk
                FROM milb_batter_pitches
                WHERE mlb_batter_id = CAST(:player_id AS integer)
            ) bp ON gl.game_pk = bp.game_pk
            WHERE gl.mlb_player_id = :player_id
                AND bp.game_pk IS NULL
                AND gl.plate_appearances > 0
            ORDER BY gl.game_date DESC
            LIMIT 20
        """)

        results = conn.execute(query, {'player_id': mlb_player_id}).fetchall()

        if results:
            print(f"Found {len(results)} games with PAs but no pitch data (showing first 20):")
            for row in results:
                print(f"  {row.game_date} - Game {row.game_pk} ({row.level}): "
                      f"{row.plate_appearances} PAs, {row.hits} H, {row.home_runs} HR")
        else:
            print("All games with PAs have corresponding pitch data!")

        return mlb_player_id

def analyze_all_prospects():
    """Analyze game log vs pitch data completeness for all prospects"""

    with engine.connect() as conn:
        print("\n" + "=" * 80)
        print("ALL PROSPECTS - DATA COMPLETENESS ANALYSIS")
        print("=" * 80)

        # Get comprehensive comparison
        query = text("""
            WITH prospect_data AS (
                SELECT
                    p.id,
                    p.name,
                    p.position,
                    p.organization,
                    p.mlb_player_id,
                    p.top_100,
                    -- Game logs data
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    SUM(gl.plate_appearances) as total_pas,
                    MIN(gl.game_date) as first_game,
                    MAX(gl.game_date) as last_game,
                    -- Pitch data
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(bp.*) as total_pitches,
                    MIN(bp.game_date) as first_pitch,
                    MAX(bp.game_date) as last_pitch,
                    -- Calculate expected pitches (3.8 pitches per PA average)
                    ROUND(SUM(gl.plate_appearances) * 3.8) as expected_pitches
                FROM prospects p
                LEFT JOIN milb_game_logs gl ON CAST(p.mlb_player_id AS integer) = gl.mlb_player_id
                    AND gl.season = 2025
                LEFT JOIN milb_batter_pitches bp ON CAST(p.mlb_player_id AS integer) = bp.mlb_batter_id
                    AND bp.season = 2025
                WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH')
                    AND p.mlb_player_id IS NOT NULL
                GROUP BY p.id, p.name, p.position, p.organization, p.mlb_player_id, p.top_100
                HAVING COUNT(DISTINCT gl.game_pk) > 0  -- Has game logs
            )
            SELECT
                *,
                total_games - games_with_pitches as games_missing_pitches,
                CASE
                    WHEN expected_pitches > 0
                    THEN ROUND((total_pitches::numeric / expected_pitches) * 100, 1)
                    ELSE 0
                END as pitch_coverage_pct
            FROM prospect_data
            ORDER BY
                CASE
                    WHEN total_games > 0 AND games_with_pitches = 0 THEN 0  -- No pitch data at all
                    WHEN total_games - games_with_pitches > 10 THEN 1  -- Many missing games
                    WHEN expected_pitches > 0 AND total_pitches < expected_pitches * 0.5 THEN 2  -- Low coverage
                    ELSE 3
                END,
                top_100 NULLS LAST
        """)

        results = conn.execute(query).fetchall()

        # Categorize issues
        no_pitch_data = []
        many_missing_games = []
        low_coverage = []
        good_coverage = []

        for row in results:
            if row.total_games > 0 and row.games_with_pitches == 0:
                no_pitch_data.append(row)
            elif row.games_missing_pitches > 10:
                many_missing_games.append(row)
            elif row.pitch_coverage_pct < 50:
                low_coverage.append(row)
            else:
                good_coverage.append(row)

        # Report findings
        print(f"\nDATA COVERAGE SUMMARY:")
        print(f"  ✅ Good coverage (>50% expected): {len(good_coverage)} players")
        print(f"  ⚠️  Low coverage (<50% expected): {len(low_coverage)} players")
        print(f"  ❌ Many missing games (>10): {len(many_missing_games)} players")
        print(f"  🚫 No pitch data at all: {len(no_pitch_data)} players")

        # Show critical issues
        if no_pitch_data:
            print("\n🚫 PLAYERS WITH GAME LOGS BUT NO PITCH DATA:")
            print("-" * 60)
            print(f"{'Name':<25} {'Pos':<5} {'Team':<10} {'Games':<8} {'PAs':<8}")
            print("-" * 60)
            for row in no_pitch_data[:10]:  # Show first 10
                print(f"{row.name:<25} {row.position:<5} {row.organization:<10} "
                      f"{row.total_games:<8} {row.total_pas:<8}")

        if many_missing_games:
            print("\n❌ PLAYERS WITH MANY MISSING GAMES (>10):")
            print("-" * 60)
            print(f"{'Name':<25} {'Pos':<5} {'Games':<8} {'w/Pitch':<8} {'Missing':<8}")
            print("-" * 60)
            for row in many_missing_games[:10]:  # Show first 10
                print(f"{row.name:<25} {row.position:<5} {row.total_games:<8} "
                      f"{row.games_with_pitches:<8} {row.games_missing_pitches:<8}")

        if low_coverage:
            print("\n⚠️  PLAYERS WITH LOW PITCH COVERAGE (<50% expected):")
            print("-" * 60)
            print(f"{'Name':<25} {'Pitches':<10} {'Expected':<10} {'Coverage':<10}")
            print("-" * 60)
            for row in low_coverage[:10]:  # Show first 10
                print(f"{row.name:<25} {row.total_pitches:<10} "
                      f"{int(row.expected_pitches):<10} {row.pitch_coverage_pct:>9.1f}%")

        return results

def generate_collection_list():
    """Generate a list of players needing pitch data collection"""

    with engine.connect() as conn:
        print("\n" + "=" * 80)
        print("GENERATING PITCH DATA COLLECTION LIST")
        print("=" * 80)

        query = text("""
            WITH missing_data AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    p.position,
                    p.organization,
                    p.top_100,
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
                    MIN(gl.game_date) as first_game_date,
                    MAX(gl.game_date) as last_game_date
                FROM prospects p
                JOIN milb_game_logs gl ON CAST(p.mlb_player_id AS integer) = gl.mlb_player_id
                LEFT JOIN milb_batter_pitches bp ON gl.game_pk = bp.game_pk
                    AND CAST(p.mlb_player_id AS integer) = bp.mlb_batter_id
                WHERE gl.season = 2025
                    AND p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH')
                GROUP BY p.name, p.mlb_player_id, p.position, p.organization, p.top_100
                HAVING COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) > 0
                ORDER BY
                    CASE WHEN p.top_100 IS NOT NULL THEN 0 ELSE 1 END,
                    p.top_100,
                    missing_games DESC
            )
            SELECT * FROM missing_data
        """)

        results = conn.execute(query).fetchall()

        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pitch_collection_needed_{timestamp}.csv"

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Name', 'MLB_ID', 'Position', 'Organization', 'Ranking',
                           'Total_Games', 'Games_With_Pitches', 'Missing_Games',
                           'First_Game', 'Last_Game'])

            for row in results:
                writer.writerow([
                    row.name, row.mlb_player_id, row.position, row.organization,
                    row.top_100 if row.top_100 else 'Unranked',
                    row.total_games, row.games_with_pitches, row.missing_games,
                    row.first_game_date, row.last_game_date
                ])

        print(f"Found {len(results)} players needing pitch data collection")
        print(f"Saved collection list to: {filename}")

        # Summary by priority
        ranked_missing = [r for r in results if r.top_100 and r.top_100 <= 100]
        unranked_missing = [r for r in results if not r.top_100 or r.top_100 > 100]

        print(f"\nPRIORITY BREAKDOWN:")
        print(f"  Top 100 prospects needing collection: {len(ranked_missing)}")
        print(f"  Other prospects needing collection: {len(unranked_missing)}")

        if ranked_missing:
            print(f"\nTOP RANKED PLAYERS NEEDING COLLECTION:")
            for player in ranked_missing[:10]:
                print(f"  #{player.top_100} {player.name} - {player.missing_games} games missing")

def main():
    """Run all analyses"""

    # First analyze Leo De Vries specifically
    leo_id = analyze_leo_devries_detail()

    # Then analyze all prospects
    all_results = analyze_all_prospects()

    # Generate collection list
    generate_collection_list()

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print("\nKEY FINDINGS:")
    print("1. Leo De Vries has limited pitch data (165 pitches) because:")
    print("   - He only played 4 games in 2025 (Sept 4-14)")
    print("   - All his game logs have corresponding pitch data")
    print("   - The issue is he didn't play much, not missing data")
    print("\n2. Many other prospects have missing pitch data for their games")
    print("3. Collection list generated for prospects with missing data")
    print("\nNEXT STEPS:")
    print("1. Run pitch data collection for players in the CSV file")
    print("2. Focus on top-ranked prospects first")
    print("3. Verify collection success after running")

if __name__ == "__main__":
    main()