import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def test_fix():
    """Test that the fixed queries work correctly"""

    with engine.connect() as conn:
        print("=" * 80)
        print("TESTING FIXED QUERIES")
        print("=" * 80)

        # Test players
        test_cases = [
            ('Bryce Eldridge', 805811, 'batter'),
            ('Logan Workman', None, 'pitcher'),  # Need to find his ID
        ]

        # Get Logan Workman's ID
        query = text("""
            SELECT mlb_player_id
            FROM prospects
            WHERE name = 'Logan Workman'
        """)
        result = conn.execute(query).fetchone()
        if result:
            test_cases[1] = ('Logan Workman', int(result.mlb_player_id), 'pitcher')

        for name, mlb_id, player_type in test_cases:
            if mlb_id is None:
                continue

            print(f"\n{name} ({player_type}):")
            print("-" * 40)

            if player_type == 'batter':
                table = 'milb_batter_pitches'
                id_col = 'mlb_batter_id'
            else:
                table = 'milb_pitcher_pitches'
                id_col = 'mlb_pitcher_id'

            # Test full season query
            query_season = text(f"""
                SELECT COUNT(*) as pitch_count
                FROM {table}
                WHERE {id_col} = :mlb_id
                    AND season = 2025
            """)

            result = conn.execute(query_season, {'mlb_id': mlb_id}).fetchone()
            season_count = result.pitch_count

            # Test 60-day query
            query_60d = text(f"""
                SELECT COUNT(*) as pitch_count
                FROM {table}
                WHERE {id_col} = :mlb_id
                    AND game_date >= CURRENT_DATE - INTERVAL '60 days'
            """)

            result = conn.execute(query_60d, {'mlb_id': mlb_id}).fetchone()
            window_count = result.pitch_count

            print(f"Full 2025 season: {season_count} pitches")
            print(f"Last 60 days: {window_count} pitches")

            if season_count > 0:
                pct = (window_count / season_count * 100)
                print(f"Currently showing: {pct:.1f}%")

                if pct < 50:
                    print(f"⚠️  NEEDS FIX: Missing {season_count - window_count} pitches!")

        print("\n" + "=" * 80)
        print("EXPECTED BEHAVIOR AFTER FIX:")
        print("=" * 80)
        print("Since the season ended >14 days ago, ALL players should show")
        print("their FULL SEASON pitch counts, not just the last 60 days.")

if __name__ == "__main__":
    test_fix()