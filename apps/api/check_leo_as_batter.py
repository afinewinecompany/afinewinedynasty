import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def check_leo_devries():
    """Check Leo De Vries as a batter"""

    with engine.connect() as conn:
        print("=" * 80)
        print("LEO DE VRIES - BATTER PITCH DATA ANALYSIS")
        print("=" * 80)

        # Check as a batter
        query = text("""
            SELECT
                p.name,
                p.mlb_player_id,
                p.position,
                COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as pitches_60d,
                COUNT(*) FILTER (WHERE bp.season = 2025) as pitches_2025,
                MIN(bp.game_date) FILTER (WHERE bp.season = 2025) as first_date_2025,
                MAX(bp.game_date) FILTER (WHERE bp.season = 2025) as last_date_2025,
                array_agg(DISTINCT bp.level) FILTER (WHERE bp.season = 2025) as levels
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE p.mlb_player_id = '815888'  -- Leo De Vries
            GROUP BY p.name, p.mlb_player_id, p.position
        """)

        result = conn.execute(query).fetchone()

        if result:
            print(f"Name: {result.name}")
            print(f"Position: {result.position}")
            print(f"MLB ID: {result.mlb_player_id}")
            print(f"\n2025 Season Total: {result.pitches_2025} pitches")
            print(f"Last 60 days: {result.pitches_60d} pitches")
            print(f"Date range: {result.first_date_2025} to {result.last_date_2025}")
            print(f"Levels: {result.levels}")

            if result.pitches_2025 > 0:
                pct = (result.pitches_60d / result.pitches_2025 * 100)
                print(f"\nShowing only {pct:.1f}% of season data!")

        # Check what the issue might be
        print("\n" + "=" * 80)
        print("DEBUGGING THE ISSUE:")
        print("=" * 80)

        # Check if the API/frontend is still using old logic
        print("\nPOSSIBLE CAUSES:")
        print("1. The API server hasn't been restarted with the new code")
        print("2. There's caching (Redis/browser) showing old data")
        print("3. The fix isn't being applied correctly in production")
        print("4. The CASE WHEN logic in the query might have syntax issues")

        # Test the actual query with the fix
        print("\n" + "=" * 80)
        print("TESTING THE FIXED QUERY:")
        print("=" * 80)

        # Test with the CASE WHEN logic that was in our fix
        query_test = text("""
            WITH test_data AS (
                SELECT
                    815888 as mlb_batter_id,
                    COUNT(*) as pitch_count,
                    'Test' as test_type
                FROM milb_batter_pitches
                WHERE mlb_batter_id = 815888
                    AND (
                        CASE WHEN TRUE THEN season = 2025
                        ELSE game_date >= CURRENT_DATE - INTERVAL '60 days'
                        END
                    )
            )
            SELECT * FROM test_data
        """)

        try:
            result = conn.execute(query_test).fetchone()
            print(f"CASE WHEN test result: {result.pitch_count} pitches")
        except Exception as e:
            print(f"ERROR with CASE WHEN: {e}")
            print("This might be the problem - the CASE WHEN syntax might not work as expected!")

        # Test alternative approach
        print("\nTesting alternative approach (separate queries):")

        # Full season
        query_season = text("""
            SELECT COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 815888 AND season = 2025
        """)

        result = conn.execute(query_season).fetchone()
        print(f"Full season query: {result.pitch_count} pitches")

        # 60-day window
        query_60d = text("""
            SELECT COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 815888
                AND game_date >= CURRENT_DATE - INTERVAL '60 days'
        """)

        result = conn.execute(query_60d).fetchone()
        print(f"60-day query: {result.pitch_count} pitches")

if __name__ == "__main__":
    check_leo_devries()