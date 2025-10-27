import os
import sys
import requests
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from datetime import datetime

# Database connection
DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
engine = create_engine(DATABASE_URL)

def clear_cache_and_test():
    """Clear cache and test composite rankings endpoint for pitch counts"""

    # First clear any cached data in Redis if applicable
    print("Testing composite rankings endpoint for pitch count issues...")
    print("=" * 60)

    # Check database directly first
    with engine.connect() as conn:
        query = text("""
            -- Get Bryce Eldridge's recent pitch-level data
            WITH pitch_data AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    COUNT(*) as total_pitches,
                    COUNT(*) FILTER (WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days') as last_60_days_pitches,
                    MAX(bp.level) as recent_level
                FROM prospects p
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
                WHERE p.name = 'Bryce Eldridge'
                GROUP BY p.name, p.mlb_player_id
            ),
            -- Check what the aggregator would query
            aggregator_query AS (
                SELECT
                    COUNT(*) as pitches_seen,
                    COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                    COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play
                FROM milb_batter_pitches
                WHERE mlb_batter_id = 805811  -- Bryce's ID
                    AND level = 'AAA'  -- His recent level
                    AND game_date >= CURRENT_DATE - CAST('60 days' AS INTERVAL)
            )
            SELECT
                pd.*,
                aq.pitches_seen as aggregator_pitches_60d,
                aq.swings,
                aq.balls_in_play
            FROM pitch_data pd
            CROSS JOIN aggregator_query aq
        """)

        result = conn.execute(query).fetchone()

        if result:
            print(f"DATABASE ANALYSIS FOR BRYCE ELDRIDGE:")
            print(f"  Name: {result.name}")
            print(f"  MLB Player ID: {result.mlb_player_id}")
            print(f"  Total Pitches (all time): {result.total_pitches}")
            print(f"  Last 60 Days Pitches: {result.last_60_days_pitches}")
            print(f"  Recent Level: {result.recent_level}")
            print(f"  Aggregator Query (60d at AAA): {result.aggregator_pitches_60d} pitches")
            print(f"    - Swings: {result.swings}")
            print(f"    - Balls in Play: {result.balls_in_play}")
            print()

        # Now let's check what levels Bryce has data for
        query2 = text("""
            SELECT
                level,
                COUNT(*) as pitches_at_level,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date,
                COUNT(*) FILTER (WHERE game_date >= CURRENT_DATE - INTERVAL '60 days') as last_60d
            FROM milb_batter_pitches
            WHERE mlb_batter_id = 805811
            GROUP BY level
            ORDER BY MAX(game_date) DESC
        """)

        print("BRYCE'S PITCH DATA BY LEVEL:")
        results = conn.execute(query2).fetchall()
        for row in results:
            print(f"  {row.level}: {row.pitches_at_level} pitches total, {row.last_60d} in last 60 days")
            print(f"    Date range: {row.first_date} to {row.last_date}")

        print()

        # Check if there's any issue with the pitch data aggregator logic
        # by simulating what it would return for different level parameters
        print("TESTING PITCH DATA AGGREGATOR LOGIC:")

        for test_level in ['AAA', 'AA', None]:
            if test_level:
                level_clause = f"AND level = '{test_level}'"
                level_desc = test_level
            else:
                level_clause = ""
                level_desc = "ALL LEVELS"

            query3 = text(f"""
                SELECT
                    COUNT(*) as pitches_seen,
                    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                        FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate
                FROM milb_batter_pitches
                WHERE mlb_batter_id = 805811
                    {level_clause}
                    AND game_date >= CURRENT_DATE - CAST('60 days' AS INTERVAL)
            """)

            result = conn.execute(query3).fetchone()
            print(f"  Level: {level_desc}")
            print(f"    Pitches (60d): {result.pitches_seen}")
            if result.exit_velo_90th:
                print(f"    Exit Velo 90th: {result.exit_velo_90th:.1f} mph")
            if result.hard_hit_rate:
                print(f"    Hard Hit Rate: {result.hard_hit_rate:.1f}%")
            print()

    # Now test the actual API endpoint
    print("=" * 60)
    print("TESTING API ENDPOINT RESPONSE:")
    print()

    # Note: Replace with actual API URL if different
    api_url = "http://localhost:8000/api/v1/prospects/composite-rankings"

    try:
        # Try to call the API
        response = requests.get(api_url, params={"page": 1, "page_size": 100})
        if response.status_code == 200:
            data = response.json()

            # Find Bryce Eldridge in the response
            bryce = None
            for prospect in data.get('prospects', []):
                if prospect.get('name') == 'Bryce Eldridge':
                    bryce = prospect
                    break

            if bryce:
                print(f"BRYCE ELDRIDGE IN API RESPONSE:")
                print(f"  Rank: {bryce.get('rank')}")
                print(f"  Composite Score: {bryce.get('composite_score')}")
                print(f"  Performance Modifier: {bryce.get('performance_modifier')}")

                breakdown = bryce.get('performance_breakdown')
                if breakdown:
                    print(f"\n  Performance Breakdown:")
                    print(f"    Source: {breakdown.get('source')}")
                    print(f"    Sample Size: {breakdown.get('sample_size')} pitches")
                    print(f"    Days Covered: {breakdown.get('days_covered')}")
                    print(f"    Level: {breakdown.get('level')}")
                    print(f"    Composite Percentile: {breakdown.get('composite_percentile')}")
                else:
                    print(f"  No performance breakdown in response")
            else:
                print("Bryce Eldridge not found in API response")
                print(f"Total prospects returned: {len(data.get('prospects', []))}")
        else:
            print(f"API call failed with status {response.status_code}")
            print(f"Response: {response.text[:500]}")
    except Exception as e:
        print(f"Could not test API endpoint: {e}")
        print("Note: Make sure the API server is running locally on port 8000")

if __name__ == "__main__":
    clear_cache_and_test()