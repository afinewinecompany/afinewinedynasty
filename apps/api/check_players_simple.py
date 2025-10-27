import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def check_players():
    """Check player pitch counts with simple output"""

    with engine.connect() as conn:
        # Check top prospects
        query = text("""
            WITH player_comparison AS (
                SELECT
                    p.name,
                    p.organization,
                    COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as pitches_60d,
                    COUNT(*) FILTER (WHERE bp.season = 2025) as pitches_2025,
                    ROUND(COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') * 100.0 /
                          NULLIF(COUNT(*) FILTER (WHERE bp.season = 2025), 0), 1) as pct_shown
                FROM prospects p
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
                WHERE bp.mlb_batter_id IS NOT NULL
                    AND p.name IN (
                        'Bryce Eldridge',
                        'Jackson Holliday',
                        'Junior Caminero',
                        'Jasson Dominguez',
                        'Jordan Walker',
                        'Matt Shaw',
                        'Pete Crow-Armstrong',
                        'Colton Cowser',
                        'Jackson Chourio',
                        'Wyatt Langford',
                        'Dylan Crews',
                        'James Wood',
                        'Marcelo Mayer',
                        'Jordan Lawlar',
                        'Colson Montgomery'
                    )
                GROUP BY p.name, p.organization
                HAVING COUNT(*) FILTER (WHERE bp.season = 2025) > 0
                ORDER BY COUNT(*) FILTER (WHERE bp.season = 2025) DESC
            )
            SELECT * FROM player_comparison
        """)

        results = conn.execute(query).fetchall()

        print("\nTOP PROSPECTS - 60-DAY WINDOW VS FULL 2025 SEASON")
        print("="*75)
        print(f"{'Player':<28} {'Team':<12} {'60-Day':<10} {'2025 Total':<12} {'% Shown'}")
        print("-"*75)

        problem_count = 0
        for row in results:
            missing = row.pitches_2025 - row.pitches_60d
            status = "OK" if row.pct_shown >= 80 else "MISSING DATA"

            print(f"{row.name:<28} {row.organization:<12} {row.pitches_60d:<10} "
                  f"{row.pitches_2025:<12} {row.pct_shown:>6.1f}%  {status}")

            if row.pct_shown < 50:
                problem_count += 1
                print(f"  --> Missing {missing} pitches from early season")

        print(f"\n{problem_count} players showing less than 50% of their season data!")

        # Check the solution with full season data
        print("\n" + "="*75)
        print("PROPOSED SOLUTION: Use full 2025 season data instead of 60-day window")
        print("="*75)

        query = text("""
            SELECT
                'Current (60-day window)' as method,
                COUNT(DISTINCT mlb_batter_id) as players_with_data,
                SUM(pitch_count) as total_pitches
            FROM (
                SELECT mlb_batter_id, COUNT(*) as pitch_count
                FROM milb_batter_pitches
                WHERE game_date >= CURRENT_DATE - INTERVAL '60 days'
                GROUP BY mlb_batter_id
                HAVING COUNT(*) >= 50
            ) t

            UNION ALL

            SELECT
                'Full 2025 Season' as method,
                COUNT(DISTINCT mlb_batter_id) as players_with_data,
                SUM(pitch_count) as total_pitches
            FROM (
                SELECT mlb_batter_id, COUNT(*) as pitch_count
                FROM milb_batter_pitches
                WHERE season = 2025
                GROUP BY mlb_batter_id
                HAVING COUNT(*) >= 50
            ) t
        """)

        results = conn.execute(query).fetchall()

        for row in results:
            print(f"{row.method:<30} {row.players_with_data:>6} players, {row.total_pitches:>10,} pitches")

        print("\nBENEFIT: Using full season data would include ALL performance data,")
        print("not just the final 60 days of the season.")

if __name__ == "__main__":
    check_players()