import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def check_pitch_counts():
    """Check actual pitch counts for prospects, especially Bryce Eldridge"""

    with engine.connect() as conn:
        # Check Bryce Eldridge's pitch count
        query = text("""
            SELECT
                p.name,
                p.mlb_player_id,
                COUNT(DISTINCT bp.game_pk) as unique_games,
                COUNT(*) as total_pitches,
                MIN(bp.game_date) as first_pitch_date,
                MAX(bp.game_date) as last_pitch_date,
                array_agg(DISTINCT bp.season ORDER BY bp.season) as seasons
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE p.name = 'Bryce Eldridge'
            GROUP BY p.name, p.mlb_player_id
        """)

        result = conn.execute(query).fetchone()

        if result:
            print(f"\n{'='*60}")
            print(f"BRYCE ELDRIDGE - ACTUAL DATABASE PITCH COUNT")
            print(f"{'='*60}")
            print(f"Name: {result.name}")
            print(f"MLB Player ID: {result.mlb_player_id}")
            print(f"Total Pitches: {result.total_pitches}")
            print(f"Unique Games: {result.unique_games}")
            print(f"Date Range: {result.first_pitch_date} to {result.last_pitch_date}")
            print(f"Seasons: {result.seasons}")

        # Check top 10 prospects by pitch count to see the data scale
        print(f"\n{'='*60}")
        print(f"TOP 10 PROSPECTS BY PITCH COUNT")
        print(f"{'='*60}")

        query2 = text("""
            SELECT
                p.name,
                p.mlb_player_id,
                COUNT(*) as total_pitches,
                COUNT(DISTINCT bp.game_pk) as games
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE bp.mlb_batter_id IS NOT NULL
            GROUP BY p.name, p.mlb_player_id
            ORDER BY total_pitches DESC
            LIMIT 10
        """)

        results = conn.execute(query2).fetchall()
        for i, row in enumerate(results, 1):
            print(f"{i}. {row.name}: {row.total_pitches} pitches ({row.games} games)")

        # Now check what the composite rankings endpoint is showing
        print(f"\n{'='*60}")
        print(f"CHECKING COMPOSITE RANKINGS QUERY")
        print(f"{'='*60}")

        # This mimics what the composite rankings might be using
        query3 = text("""
            SELECT
                p.id,
                p.name,
                p.mlb_player_id,
                (SELECT COUNT(*) FROM milb_batter_pitches WHERE mlb_batter_id = p.mlb_player_id::integer) as pitch_count_direct,
                COUNT(bp.*) as pitch_count_join
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON bp.mlb_batter_id = p.mlb_player_id::integer
            WHERE p.name = 'Bryce Eldridge'
            GROUP BY p.id, p.name, p.mlb_player_id
        """)

        result = conn.execute(query3).fetchone()
        if result:
            print(f"Prospect ID: {result.id}")
            print(f"Name: {result.name}")
            print(f"MLB Player ID: {result.mlb_player_id}")
            print(f"Pitch Count (Direct Query): {result.pitch_count_direct}")
            print(f"Pitch Count (Join): {result.pitch_count_join}")

if __name__ == "__main__":
    check_pitch_counts()