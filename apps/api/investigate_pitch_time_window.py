import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def investigate_time_windows():
    """Check pitch counts for different time windows and players"""

    with engine.connect() as conn:
        # Check Bryce Eldridge's data across different time windows
        print("=" * 70)
        print("BRYCE ELDRIDGE - PITCH COUNT BY TIME WINDOW")
        print("=" * 70)

        time_windows = [30, 60, 90, 120, 180, 365, 1000]  # days

        for days in time_windows:
            query = text("""
                SELECT
                    COUNT(*) as total_pitches,
                    COUNT(DISTINCT game_pk) as games,
                    MIN(game_date) as first_date,
                    MAX(game_date) as last_date,
                    array_agg(DISTINCT level ORDER BY level) as levels
                FROM milb_batter_pitches
                WHERE mlb_batter_id = 805811  -- Bryce Eldridge
                    AND game_date >= CURRENT_DATE - INTERVAL :days
            """)

            result = conn.execute(query, {'days': f'{days} days'}).fetchone()

            if result and result.total_pitches > 0:
                print(f"\nLast {days} days:")
                print(f"  Pitches: {result.total_pitches}")
                print(f"  Games: {result.games}")
                print(f"  Date range: {result.first_date} to {result.last_date}")
                print(f"  Levels: {result.levels}")

        # Check ALL 2025 data for Bryce
        print("\n" + "=" * 70)
        print("BRYCE ELDRIDGE - ALL 2025 DATA")
        print("=" * 70)

        query = text("""
            SELECT
                season,
                COUNT(*) as total_pitches,
                COUNT(DISTINCT game_pk) as games,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date,
                array_agg(DISTINCT level ORDER BY level) as levels
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 805811
                AND season = 2025
            GROUP BY season
        """)

        result = conn.execute(query).fetchone()
        if result:
            print(f"Season 2025 TOTAL:")
            print(f"  Pitches: {result.total_pitches}")
            print(f"  Games: {result.games}")
            print(f"  Date range: {result.first_date} to {result.last_date}")
            print(f"  Levels: {result.levels}")

        # Check other top prospects with multi-level data
        print("\n" + "=" * 70)
        print("OTHER TOP PROSPECTS - 60 DAYS VS FULL SEASON")
        print("=" * 70)

        query = text("""
            WITH player_comparison AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    -- Last 60 days
                    COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as pitches_60d,
                    COUNT(DISTINCT bp.game_pk) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as games_60d,
                    -- Full 2025 season
                    COUNT(*) FILTER (WHERE bp.season = 2025) as pitches_2025,
                    COUNT(DISTINCT bp.game_pk) FILTER (WHERE bp.season = 2025) as games_2025,
                    -- Levels
                    array_agg(DISTINCT bp.level) FILTER (WHERE bp.season = 2025) as levels_2025
                FROM prospects p
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
                WHERE p.ranking <= 100  -- Top 100 prospects
                    AND bp.mlb_batter_id IS NOT NULL
                GROUP BY p.name, p.mlb_player_id
                HAVING COUNT(*) FILTER (WHERE bp.season = 2025) > 1000  -- Has significant data
                ORDER BY COUNT(*) FILTER (WHERE bp.season = 2025) DESC
                LIMIT 20
            )
            SELECT * FROM player_comparison
        """)

        results = conn.execute(query).fetchall()

        print(f"\n{'Name':<25} {'60-Day':<10} {'2025 Total':<12} {'Difference':<12} {'Levels'}")
        print("-" * 80)

        for row in results:
            diff = row.pitches_2025 - row.pitches_60d
            pct = (row.pitches_60d / row.pitches_2025 * 100) if row.pitches_2025 > 0 else 0
            levels_str = ', '.join(row.levels_2025) if row.levels_2025 else 'N/A'
            print(f"{row.name:<25} {row.pitches_60d:<10} {row.pitches_2025:<12} {diff:<12} {levels_str}")
            if pct < 50:
                print(f"  ⚠️  Only showing {pct:.1f}% of season data!")

        # Check what the current date is vs the season
        print("\n" + "=" * 70)
        print("SEASON TIMING ANALYSIS")
        print("=" * 70)

        query = text("""
            SELECT
                CURRENT_DATE as today,
                MIN(game_date) as season_start,
                MAX(game_date) as season_end,
                CURRENT_DATE - MIN(game_date) as days_since_start,
                MAX(game_date) - CURRENT_DATE as days_since_end
            FROM milb_batter_pitches
            WHERE season = 2025
        """)

        result = conn.execute(query).fetchone()
        if result:
            print(f"Current date: {result.today}")
            print(f"2025 Season: {result.season_start} to {result.season_end}")
            print(f"Days since season start: {result.days_since_start}")
            print(f"Days since season end: {result.days_since_end}")

            if result.days_since_end and result.days_since_end > 30:
                print(f"\n⚠️  WARNING: Season ended {result.days_since_end} days ago!")
                print("The 60-day window is missing early season data!")

if __name__ == "__main__":
    investigate_time_windows()