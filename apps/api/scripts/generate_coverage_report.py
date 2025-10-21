import psycopg2
from datetime import datetime
import csv

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def generate_coverage_report():
    """Generate comprehensive data coverage report for all prospects"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("GENERATING PROSPECT DATA COVERAGE REPORT")
    print(f"Generated: {datetime.now()}")
    print("=" * 80)

    # Get comprehensive coverage data for all prospects
    cur.execute("""
        WITH batter_pitch_data AS (
            SELECT
                mlb_batter_id,
                season,
                COUNT(*) as pitch_count,
                COUNT(DISTINCT game_pk) as game_count
            FROM milb_batter_pitches
            GROUP BY mlb_batter_id, season
        ),
        pitcher_pitch_data AS (
            SELECT
                mlb_pitcher_id,
                season,
                COUNT(*) as pitch_count,
                COUNT(DISTINCT game_pk) as game_count
            FROM milb_pitcher_pitches
            GROUP BY mlb_pitcher_id, season
        ),
        plate_appearance_data AS (
            SELECT
                mlb_player_id,
                season,
                COUNT(*) as pa_count,
                COUNT(DISTINCT game_pk) as game_count
            FROM milb_plate_appearances
            GROUP BY mlb_player_id, season
        )
        SELECT
            p.name,
            p.mlb_player_id,
            p.organization,
            p.position,

            -- 2025 Batter Data
            COALESCE(bp25.pitch_count, 0) as pitches_faced_2025,
            COALESCE(bp25.game_count, 0) as games_as_batter_2025,

            -- 2024 Batter Data
            COALESCE(bp24.pitch_count, 0) as pitches_faced_2024,
            COALESCE(bp24.game_count, 0) as games_as_batter_2024,

            -- 2023 Batter Data
            COALESCE(bp23.pitch_count, 0) as pitches_faced_2023,
            COALESCE(bp23.game_count, 0) as games_as_batter_2023,

            -- 2025 Pitcher Data
            COALESCE(pp25.pitch_count, 0) as pitches_thrown_2025,
            COALESCE(pp25.game_count, 0) as games_as_pitcher_2025,

            -- 2024 Pitcher Data
            COALESCE(pp24.pitch_count, 0) as pitches_thrown_2024,
            COALESCE(pp24.game_count, 0) as games_as_pitcher_2024,

            -- 2023 Pitcher Data
            COALESCE(pp23.pitch_count, 0) as pitches_thrown_2023,
            COALESCE(pp23.game_count, 0) as games_as_pitcher_2023,

            -- 2025 Plate Appearances
            COALESCE(pa25.pa_count, 0) as plate_appearances_2025,
            COALESCE(pa25.game_count, 0) as pa_games_2025,

            -- 2024 Plate Appearances
            COALESCE(pa24.pa_count, 0) as plate_appearances_2024,
            COALESCE(pa24.game_count, 0) as pa_games_2024,

            -- 2023 Plate Appearances
            COALESCE(pa23.pa_count, 0) as plate_appearances_2023,
            COALESCE(pa23.game_count, 0) as pa_games_2023,

            -- Calculate totals
            COALESCE(bp25.pitch_count, 0) + COALESCE(bp24.pitch_count, 0) + COALESCE(bp23.pitch_count, 0) as total_pitches_faced,
            COALESCE(pp25.pitch_count, 0) + COALESCE(pp24.pitch_count, 0) + COALESCE(pp23.pitch_count, 0) as total_pitches_thrown,
            COALESCE(pa25.pa_count, 0) + COALESCE(pa24.pa_count, 0) + COALESCE(pa23.pa_count, 0) as total_plate_appearances

        FROM prospects p

        LEFT JOIN batter_pitch_data bp25 ON p.mlb_player_id::INTEGER = bp25.mlb_batter_id AND bp25.season = 2025
        LEFT JOIN batter_pitch_data bp24 ON p.mlb_player_id::INTEGER = bp24.mlb_batter_id AND bp24.season = 2024
        LEFT JOIN batter_pitch_data bp23 ON p.mlb_player_id::INTEGER = bp23.mlb_batter_id AND bp23.season = 2023

        LEFT JOIN pitcher_pitch_data pp25 ON p.mlb_player_id::INTEGER = pp25.mlb_pitcher_id AND pp25.season = 2025
        LEFT JOIN pitcher_pitch_data pp24 ON p.mlb_player_id::INTEGER = pp24.mlb_pitcher_id AND pp24.season = 2024
        LEFT JOIN pitcher_pitch_data pp23 ON p.mlb_player_id::INTEGER = pp23.mlb_pitcher_id AND pp23.season = 2023

        LEFT JOIN plate_appearance_data pa25 ON p.mlb_player_id::INTEGER = pa25.mlb_player_id AND pa25.season = 2025
        LEFT JOIN plate_appearance_data pa24 ON p.mlb_player_id::INTEGER = pa24.mlb_player_id AND pa24.season = 2024
        LEFT JOIN plate_appearance_data pa23 ON p.mlb_player_id::INTEGER = pa23.mlb_player_id AND pa23.season = 2023

        WHERE p.mlb_player_id IS NOT NULL
        ORDER BY
            (COALESCE(bp25.pitch_count, 0) + COALESCE(bp24.pitch_count, 0) + COALESCE(bp23.pitch_count, 0) +
             COALESCE(pp25.pitch_count, 0) + COALESCE(pp24.pitch_count, 0) + COALESCE(pp23.pitch_count, 0) +
             COALESCE(pa25.pa_count, 0) + COALESCE(pa24.pa_count, 0) + COALESCE(pa23.pa_count, 0)) DESC,
            p.name
    """)

    results = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    print(f"\nFound {len(results)} prospects with MLB Player IDs")

    # Write to CSV
    csv_filename = 'prospect_data_coverage_report.csv'
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(columns)
        writer.writerows(results)

    print(f"\nCSV file created: {csv_filename}")

    # Generate summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)

    # Overall totals
    cur.execute("""
        SELECT
            COUNT(*) as total_prospects,
            COUNT(DISTINCT CASE WHEN position IN ('P', 'SP', 'RP', 'LHP', 'RHP') THEN mlb_player_id END) as pitchers,
            COUNT(DISTINCT CASE WHEN position NOT IN ('P', 'SP', 'RP', 'LHP', 'RHP') THEN mlb_player_id END) as position_players
        FROM prospects
        WHERE mlb_player_id IS NOT NULL
    """)
    total_prospects, pitchers, position_players = cur.fetchone()

    print(f"\nTotal Prospects: {total_prospects}")
    print(f"  Pitchers: {pitchers}")
    print(f"  Position Players: {position_players}")

    # Coverage by year and data type
    for year in [2025, 2024, 2023]:
        print(f"\n{year} Data Coverage:")

        # Batter pitch data
        cur.execute("""
            SELECT
                COUNT(DISTINCT p.mlb_player_id) as prospects,
                SUM(pitch_count) as total_pitches,
                SUM(game_count) as total_games
            FROM prospects p
            JOIN (
                SELECT mlb_batter_id, COUNT(*) as pitch_count, COUNT(DISTINCT game_pk) as game_count
                FROM milb_batter_pitches
                WHERE season = %s
                GROUP BY mlb_batter_id
            ) bp ON p.mlb_player_id::INTEGER = bp.mlb_batter_id
            WHERE p.mlb_player_id IS NOT NULL
        """, (year,))
        result = cur.fetchone()
        if result[0]:
            print(f"  Batter Pitch Data: {result[0]} prospects, {result[1]:,} pitches, {result[2]:,} games")
        else:
            print(f"  Batter Pitch Data: No data")

        # Pitcher pitch data
        cur.execute("""
            SELECT
                COUNT(DISTINCT p.mlb_player_id) as prospects,
                SUM(pitch_count) as total_pitches,
                SUM(game_count) as total_games
            FROM prospects p
            JOIN (
                SELECT mlb_pitcher_id, COUNT(*) as pitch_count, COUNT(DISTINCT game_pk) as game_count
                FROM milb_pitcher_pitches
                WHERE season = %s
                GROUP BY mlb_pitcher_id
            ) pp ON p.mlb_player_id::INTEGER = pp.mlb_pitcher_id
            WHERE p.mlb_player_id IS NOT NULL
        """, (year,))
        result = cur.fetchone()
        if result[0]:
            print(f"  Pitcher Pitch Data: {result[0]} prospects, {result[1]:,} pitches, {result[2]:,} games")
        else:
            print(f"  Pitcher Pitch Data: No data")

        # Plate appearances
        cur.execute("""
            SELECT
                COUNT(DISTINCT p.mlb_player_id) as prospects,
                SUM(pa_count) as total_pas,
                SUM(game_count) as total_games
            FROM prospects p
            JOIN (
                SELECT mlb_player_id, COUNT(*) as pa_count, COUNT(DISTINCT game_pk) as game_count
                FROM milb_plate_appearances
                WHERE season = %s
                GROUP BY mlb_player_id
            ) pa ON p.mlb_player_id::INTEGER = pa.mlb_player_id
            WHERE p.mlb_player_id IS NOT NULL
        """, (year,))
        result = cur.fetchone()
        if result[0]:
            print(f"  Plate Appearances: {result[0]} prospects, {result[1]:,} PAs, {result[2]:,} games")
        else:
            print(f"  Plate Appearances: No data")

    # Top prospects by data coverage
    print("\n" + "=" * 80)
    print("TOP 20 PROSPECTS BY TOTAL DATA COVERAGE")
    print("=" * 80)

    for i, row in enumerate(results[:20], 1):
        name = row[0]
        org = row[2]
        pos = row[3]
        total_pitches_faced = row[23]
        total_pitches_thrown = row[24]
        total_pas = row[25]

        print(f"\n{i}. {name} ({org}) - {pos}")
        if total_pitches_faced > 0:
            print(f"   Batter: {total_pitches_faced:,} pitches faced")
        if total_pitches_thrown > 0:
            print(f"   Pitcher: {total_pitches_thrown:,} pitches thrown")
        if total_pas > 0:
            print(f"   Plate Appearances: {total_pas:,}")

    # Prospects with no data
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches bp WHERE bp.mlb_batter_id = p.mlb_player_id::INTEGER
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_pitches pp WHERE pp.mlb_pitcher_id = p.mlb_player_id::INTEGER
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_plate_appearances pa WHERE pa.mlb_player_id = p.mlb_player_id::INTEGER
        )
    """)
    no_data_count = cur.fetchone()[0]

    print("\n" + "=" * 80)
    print(f"Prospects with NO data: {no_data_count} ({no_data_count/total_prospects*100:.1f}%)")
    print("=" * 80)

    conn.close()

    return csv_filename

if __name__ == "__main__":
    filename = generate_coverage_report()
    print(f"\n\nReport complete! Data saved to: {filename}")
