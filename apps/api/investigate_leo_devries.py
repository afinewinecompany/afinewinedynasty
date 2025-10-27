import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def investigate_pitch_counts():
    """Investigate pitch count issues for Leo De Vries and other pitchers"""

    with engine.connect() as conn:
        print("=" * 80)
        print("INVESTIGATING PITCHER PITCH COUNTS")
        print("=" * 80)

        # Check Leo De Vries specifically
        print("\nLEO DE VRIES ANALYSIS:")
        print("-" * 40)

        # Get prospect info
        query = text("""
            SELECT
                p.id,
                p.name,
                p.mlb_player_id,
                p.position,
                p.organization
            FROM prospects p
            WHERE LOWER(p.name) LIKE '%leo%de%vries%'
        """)

        result = conn.execute(query).fetchone()
        if result:
            print(f"Prospect ID: {result.id}")
            print(f"Name: {result.name}")
            print(f"MLB Player ID: {result.mlb_player_id}")
            print(f"Position: {result.position}")
            print(f"Team: {result.organization}")

            mlb_id = result.mlb_player_id

            # Check pitcher pitch data
            print(f"\nPITCHER PITCH DATA FOR {result.name}:")
            print("-" * 40)

            # Check different time windows
            windows = [
                ('Last 60 days', 'game_date >= CURRENT_DATE - INTERVAL \'60 days\''),
                ('Last 90 days', 'game_date >= CURRENT_DATE - INTERVAL \'90 days\''),
                ('Full 2025 season', 'season = 2025'),
                ('All time', '1=1')
            ]

            for window_name, condition in windows:
                query = text(f"""
                    SELECT
                        COUNT(*) as pitch_count,
                        COUNT(DISTINCT game_pk) as games,
                        MIN(game_date) as first_date,
                        MAX(game_date) as last_date,
                        array_agg(DISTINCT level ORDER BY level) as levels
                    FROM milb_pitcher_pitches
                    WHERE mlb_pitcher_id = :mlb_id
                        AND {condition}
                """)

                result = conn.execute(query, {'mlb_id': int(mlb_id)}).fetchone()

                if result and result.pitch_count > 0:
                    print(f"\n{window_name}:")
                    print(f"  Pitches: {result.pitch_count}")
                    print(f"  Games: {result.games}")
                    print(f"  Date range: {result.first_date} to {result.last_date}")
                    print(f"  Levels: {result.levels}")

        # Check other pitchers with large discrepancies
        print("\n" + "=" * 80)
        print("OTHER PITCHERS - COMPARING 60-DAY VS FULL SEASON:")
        print("=" * 80)

        query = text("""
            WITH pitcher_comparison AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    p.organization,
                    -- Last 60 days
                    COUNT(*) FILTER (WHERE pp.game_date >= CURRENT_DATE - INTERVAL '60 days') as pitches_60d,
                    -- Full 2025 season
                    COUNT(*) FILTER (WHERE pp.season = 2025) as pitches_2025,
                    -- Percentage
                    CASE
                        WHEN COUNT(*) FILTER (WHERE pp.season = 2025) > 0
                        THEN ROUND(COUNT(*) FILTER (WHERE pp.game_date >= CURRENT_DATE - INTERVAL '60 days') * 100.0 /
                                  COUNT(*) FILTER (WHERE pp.season = 2025), 1)
                        ELSE 0
                    END as pct_shown,
                    -- Levels
                    array_agg(DISTINCT pp.level) FILTER (WHERE pp.season = 2025) as levels_2025
                FROM prospects p
                LEFT JOIN milb_pitcher_pitches pp ON p.mlb_player_id::integer = pp.mlb_pitcher_id
                WHERE p.position IN ('SP', 'RP', 'P')
                    AND pp.mlb_pitcher_id IS NOT NULL
                GROUP BY p.name, p.mlb_player_id, p.organization
                HAVING COUNT(*) FILTER (WHERE pp.season = 2025) > 1500  -- Significant data
                ORDER BY COUNT(*) FILTER (WHERE pp.season = 2025) DESC
                LIMIT 20
            )
            SELECT * FROM pitcher_comparison
        """)

        results = conn.execute(query).fetchall()

        print(f"\n{'Pitcher':<25} {'Team':<8} {'60-Day':<10} {'2025 Total':<12} {'%':<8} {'Levels'}")
        print("-" * 80)

        problem_count = 0
        for row in results:
            levels_str = ', '.join(row.levels_2025) if row.levels_2025 else 'N/A'
            status = "OK" if row.pct_shown >= 80 else "ISSUE"

            print(f"{row.name:<25} {row.organization:<8} {row.pitches_60d:<10} "
                  f"{row.pitches_2025:<12} {row.pct_shown:>6.1f}%  {status}")

            if row.pct_shown < 30:
                problem_count += 1
                missing = row.pitches_2025 - row.pitches_60d
                print(f"  --> Missing {missing} pitches!")

        print(f"\n{problem_count} pitchers showing less than 30% of their season data!")

        # Check the actual query being used by the aggregator
        print("\n" + "=" * 80)
        print("TESTING AGGREGATOR LOGIC FOR LEO DE VRIES:")
        print("=" * 80)

        # Simulate what the aggregator would do
        query = text("""
            SELECT
                EXTRACT(YEAR FROM CURRENT_DATE)::integer as current_year,
                MAX(game_date) as last_game_date,
                CURRENT_DATE - MAX(game_date) as days_since_last_game
            FROM milb_pitcher_pitches
            WHERE season = EXTRACT(YEAR FROM CURRENT_DATE)
        """)

        result = conn.execute(query).fetchone()
        use_full_season = result.days_since_last_game and result.days_since_last_game > 14

        print(f"Season check: Last game was {result.days_since_last_game} days ago")
        print(f"Should use full season: {use_full_season}")

        if use_full_season:
            print("\nThe aggregator SHOULD be using full season data, but Leo still shows 165 pitches.")
            print("This suggests the fix might not be working correctly!")

if __name__ == "__main__":
    investigate_pitch_counts()