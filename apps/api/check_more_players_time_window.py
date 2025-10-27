import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def check_more_players():
    """Check more players to see the extent of the time window issue"""

    with engine.connect() as conn:
        # Get current date and season info
        query = text("""
            SELECT
                CURRENT_DATE as today,
                MAX(game_date) as last_game,
                CURRENT_DATE - MAX(game_date) as days_since_last_game
            FROM milb_batter_pitches
            WHERE season = 2025
        """)

        result = conn.execute(query).fetchone()
        print(f"Current date: {result.today}")
        print(f"Last 2025 game: {result.last_game}")
        print(f"Days since last game: {result.days_since_last_game} days")
        print(f"\n{'='*80}\n")

        # Check top prospects with lots of data
        query = text("""
            WITH player_comparison AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    p.organization,
                    p.position,
                    -- Last 60 days
                    COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as pitches_60d,
                    -- Full 2025 season
                    COUNT(*) FILTER (WHERE bp.season = 2025) as pitches_2025,
                    -- Percentage shown
                    CASE
                        WHEN COUNT(*) FILTER (WHERE bp.season = 2025) > 0
                        THEN ROUND(COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') * 100.0 /
                                  COUNT(*) FILTER (WHERE bp.season = 2025), 1)
                        ELSE 0
                    END as pct_shown,
                    -- Date ranges
                    MIN(bp.game_date) FILTER (WHERE bp.season = 2025) as season_start,
                    MAX(bp.game_date) FILTER (WHERE bp.season = 2025) as season_end
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
                        'Wyatt Langford'
                    )
                GROUP BY p.name, p.mlb_player_id, p.organization, p.position
                HAVING COUNT(*) FILTER (WHERE bp.season = 2025) > 0
                ORDER BY COUNT(*) FILTER (WHERE bp.season = 2025) DESC
            )
            SELECT * FROM player_comparison
        """)

        results = conn.execute(query).fetchall()

        print("TOP PROSPECTS - 60-DAY WINDOW VS FULL 2025 SEASON")
        print("="*80)
        print(f"{'Player':<25} {'Org':<10} {'60-Day':<8} {'2025':<8} {'%':<6} {'Season Dates'}")
        print("-"*80)

        for row in results:
            missing = row.pitches_2025 - row.pitches_60d
            date_range = f"{row.season_start} to {row.season_end}" if row.season_start else "N/A"

            indicator = "✓" if row.pct_shown >= 80 else "⚠️" if row.pct_shown >= 50 else "❌"

            print(f"{row.name:<25} {row.organization:<10} {row.pitches_60d:<8} {row.pitches_2025:<8} "
                  f"{row.pct_shown:>5.1f}% {indicator} {date_range}")

            if row.pct_shown < 30:
                print(f"  → Missing {missing} pitches ({100-row.pct_shown:.1f}% of season data!)")

        # Check what would happen with different time windows
        print(f"\n{'='*80}")
        print("ALTERNATIVE TIME WINDOW ANALYSIS")
        print("="*80)

        windows = [
            ('Current (60 days)', 60),
            ('90 days', 90),
            ('120 days', 120),
            ('Full 2025 Season', 365)
        ]

        for window_name, days in windows:
            if days == 365:
                # Full season query
                query = text("""
                    SELECT COUNT(DISTINCT mlb_batter_id) as players,
                           SUM(pitch_count) as total_pitches
                    FROM (
                        SELECT mlb_batter_id, COUNT(*) as pitch_count
                        FROM milb_batter_pitches
                        WHERE season = 2025
                        GROUP BY mlb_batter_id
                        HAVING COUNT(*) >= 50
                    ) t
                """)
            else:
                query = text(f"""
                    SELECT COUNT(DISTINCT mlb_batter_id) as players,
                           SUM(pitch_count) as total_pitches
                    FROM (
                        SELECT mlb_batter_id, COUNT(*) as pitch_count
                        FROM milb_batter_pitches
                        WHERE game_date >= CURRENT_DATE - INTERVAL '{days} days'
                        GROUP BY mlb_batter_id
                        HAVING COUNT(*) >= 50
                    ) t
                """)

            result = conn.execute(query).fetchone()
            print(f"{window_name:<20} {result.players:>6} players with 50+ pitches, "
                  f"{result.total_pitches:>10,} total pitches")

        print(f"\n{'='*80}")
        print("RECOMMENDATION")
        print("="*80)
        print("The 60-day window is problematic because:")
        print("1. The 2025 season ended ~27 days ago (late September)")
        print("2. This means we're only looking at the last ~33 days of the season")
        print("3. Most players are missing 50-75% of their season data")
        print("\nSUGGESTED FIX:")
        print("- Use FULL SEASON data when the season has ended (like now)")
        print("- Use rolling window (60/90 days) only during active season")
        print("- Or use a 'season-aware' window that captures the full current/recent season")

if __name__ == "__main__":
    check_more_players()