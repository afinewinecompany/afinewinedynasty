import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def test_fix():
    """Test that the fix would work correctly"""

    with engine.connect() as conn:
        # Simulate what the fixed code would do
        print("TESTING SEASON-AWARE FIX")
        print("="*60)

        # Check season status
        query = text("""
            SELECT
                EXTRACT(YEAR FROM CURRENT_DATE)::integer as current_year,
                MAX(game_date) as last_game_date,
                CURRENT_DATE - MAX(game_date) as days_since_last_game
            FROM milb_batter_pitches
            WHERE season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        result = conn.execute(query).fetchone()

        print(f"Current year: {result.current_year}")
        print(f"Last game: {result.last_game_date}")
        print(f"Days since last game: {result.days_since_last_game}")

        use_full_season = result.days_since_last_game > 14

        print(f"\nSeason status: {'ENDED' if use_full_season else 'ACTIVE'}")
        print(f"Data mode: {'FULL SEASON' if use_full_season else '60-DAY WINDOW'}")

        # Test with Bryce Eldridge
        print("\n" + "="*60)
        print("BRYCE ELDRIDGE - TESTING BOTH MODES")
        print("="*60)

        # Test current 60-day window
        query_60d = text("""
            SELECT
                COUNT(*) as pitches,
                COUNT(DISTINCT game_pk) as games,
                array_agg(DISTINCT level ORDER BY level) as levels
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 805811
                AND game_date >= CURRENT_DATE - INTERVAL '60 days'
        """)

        result_60d = conn.execute(query_60d).fetchone()

        # Test full season
        query_season = text("""
            SELECT
                COUNT(*) as pitches,
                COUNT(DISTINCT game_pk) as games,
                array_agg(DISTINCT level ORDER BY level) as levels
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 805811
                AND season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        result_season = conn.execute(query_season).fetchone()

        print("\n60-DAY WINDOW (current buggy behavior):")
        print(f"  Pitches: {result_60d.pitches}")
        print(f"  Games: {result_60d.games}")
        print(f"  Levels: {result_60d.levels}")

        print("\nFULL SEASON (fixed behavior):")
        print(f"  Pitches: {result_season.pitches}")
        print(f"  Games: {result_season.games}")
        print(f"  Levels: {result_season.levels}")

        improvement = ((result_season.pitches - result_60d.pitches) / result_60d.pitches * 100) if result_60d.pitches > 0 else 0
        print(f"\nIMPROVEMENT: {improvement:.1f}% more data with the fix!")

        # Check other players
        print("\n" + "="*60)
        print("IMPACT ON OTHER PLAYERS")
        print("="*60)

        query = text("""
            SELECT
                p.name,
                COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as pitches_60d,
                COUNT(*) FILTER (WHERE bp.season = EXTRACT(YEAR FROM CURRENT_DATE)) as pitches_season,
                ROUND(
                    (COUNT(*) FILTER (WHERE bp.season = EXTRACT(YEAR FROM CURRENT_DATE)) -
                     COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days')) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days'), 0), 1
                ) as pct_increase
            FROM prospects p
            JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE bp.season = EXTRACT(YEAR FROM CURRENT_DATE)
            GROUP BY p.name
            HAVING COUNT(*) FILTER (WHERE bp.season = EXTRACT(YEAR FROM CURRENT_DATE)) > 1000
            ORDER BY pct_increase DESC
            LIMIT 10
        """)

        results = conn.execute(query).fetchall()

        print(f"\n{'Player':<25} {'60-Day':<10} {'Season':<10} {'Increase'}")
        print("-"*60)

        for row in results:
            print(f"{row.name:<25} {row.pitches_60d:<10} {row.pitches_season:<10} +{row.pct_increase:.0f}%")

if __name__ == "__main__":
    test_fix()