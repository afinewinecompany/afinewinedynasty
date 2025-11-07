"""Check MILB tables and data availability."""

import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

def check_milb_data():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        print("\n=== Checking MILB Tables ===")

        # List all MILB-related tables
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE '%milb%'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()

        print("\nMILB-related tables found:")
        for table in tables:
            print(f"  - {table['table_name']}")

        # Check milb_batter_pitches data for 2025
        print("\n=== Checking milb_batter_pitches for 2025 ===")
        cursor.execute("""
            SELECT
                COUNT(*) as total_rows,
                COUNT(DISTINCT mlb_batter_id) as unique_batters,
                COUNT(DISTINCT game_id) as unique_games,
                COUNT(DISTINCT level) as unique_levels,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game
            FROM milb_batter_pitches
            WHERE season = 2025
        """)
        stats = cursor.fetchone()

        print(f"\n2025 milb_batter_pitches stats:")
        print(f"  Total pitch records: {stats['total_rows']:,}")
        print(f"  Unique batters: {stats['unique_batters']:,}")
        print(f"  Unique games: {stats['unique_games']:,}")
        print(f"  Unique levels: {stats['unique_levels']:,}")
        print(f"  Date range: {stats['first_game']} to {stats['last_game']}")

        # Show sample of players with most data
        print("\n=== Top 10 Players by Pitch Count (2025) ===")
        cursor.execute("""
            SELECT
                mlb_batter_id,
                mlb_batter_name,
                level,
                COUNT(*) as pitch_count,
                COUNT(DISTINCT game_id) as games,
                COUNT(DISTINCT CASE
                    WHEN event_result IS NOT NULL
                    THEN game_id || '_' || pa_of_inning
                END) as plate_appearances
            FROM milb_batter_pitches
            WHERE season = 2025
            GROUP BY mlb_batter_id, mlb_batter_name, level
            ORDER BY pitch_count DESC
            LIMIT 10
        """)

        players = cursor.fetchall()
        for i, player in enumerate(players, 1):
            print(f"{i:2}. {player['mlb_batter_name']:<25} (ID: {player['mlb_batter_id']}) - "
                  f"Level: {player['level']}, Pitches: {player['pitch_count']:,}, "
                  f"Games: {player['games']}, PAs: {player['plate_appearances']}")

        # Check for discipline/power metrics availability
        print("\n=== Checking Available Pitch Metrics ===")
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE zone IS NOT NULL) as has_zone,
                COUNT(*) FILTER (WHERE swing IS NOT NULL) as has_swing,
                COUNT(*) FILTER (WHERE contact IS NOT NULL) as has_contact,
                COUNT(*) FILTER (WHERE hardness IS NOT NULL) as has_hardness,
                COUNT(*) FILTER (WHERE trajectory IS NOT NULL) as has_trajectory,
                COUNT(*) FILTER (WHERE event_result IS NOT NULL) as has_result,
                COUNT(*) as total
            FROM milb_batter_pitches
            WHERE season = 2025
            LIMIT 10000
        """)

        metrics = cursor.fetchone()
        print(f"\nData completeness (sample of 10,000 pitches):")
        for key, value in metrics.items():
            if key != 'total':
                pct = (value / metrics['total'] * 100) if metrics['total'] > 0 else 0
                print(f"  {key}: {value:,} ({pct:.1f}%)")

        # Check levels distribution
        print("\n=== 2025 Data by Level ===")
        cursor.execute("""
            SELECT
                level,
                COUNT(DISTINCT mlb_batter_id) as unique_batters,
                COUNT(DISTINCT game_id) as games,
                COUNT(*) as pitches
            FROM milb_batter_pitches
            WHERE season = 2025
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    WHEN 'ROK' THEN 5
                    ELSE 6
                END
        """)

        levels = cursor.fetchall()
        for level in levels:
            print(f"  {level['level']:<5} - Batters: {level['unique_batters']:,}, "
                  f"Games: {level['games']:,}, Pitches: {level['pitches']:,}")

        cursor.close()
        conn.close()

        print("\n=== Check Complete ===")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_milb_data()
