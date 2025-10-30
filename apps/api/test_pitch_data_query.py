"""Test the actual pitch data queries to see what's failing"""
import asyncio
import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def test_pitch_queries():
    """Test pitch data queries directly"""

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    print("="*80)
    print("TESTING PITCH DATA QUERIES")
    print("="*80)

    # Test prospect: Bryce Eldridge
    mlb_player_id = 805811

    # 1. Check what levels he played at
    print(f"\n1. Checking levels for player {mlb_player_id}:")
    cursor.execute("""
        SELECT level, COUNT(*) as pitch_count
        FROM milb_batter_pitches
        WHERE mlb_batter_id = %s
            AND season = 2025
        GROUP BY level
        ORDER BY pitch_count DESC
    """, (mlb_player_id,))

    levels_data = cursor.fetchall()
    print(f"   Found {len(levels_data)} levels:")
    for level, count in levels_data:
        print(f"   - {level}: {count} pitches")

    if not levels_data:
        print("   NO DATA FOUND!")
        return

    levels_played = [row[0] for row in levels_data]
    total_pitches = sum(row[1] for row in levels_data)

    # 2. Test the actual metrics query
    print(f"\n2. Testing metrics query for {total_pitches} total pitches:")

    # Use the same query structure as PitchDataAggregator
    cursor.execute("""
        WITH player_stats AS (
            SELECT
                -- Exit Velocity (90th percentile)
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                    FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                -- Hard Hit Rate
                COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                -- Contact Rate
                COUNT(*) FILTER (WHERE contact = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                -- Whiff Rate
                COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                -- Chase Rate
                COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                    NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                -- Sample size
                COUNT(*) as pitches_seen,
                COUNT(*) FILTER (WHERE swing = TRUE) as swings,
                COUNT(*) FILTER (WHERE launch_speed IS NOT NULL) as balls_in_play,

                -- Track levels included
                array_agg(DISTINCT level ORDER BY level) as levels_included

            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s
                AND level = ANY(%s)
                AND season = 2025
        )
        SELECT * FROM player_stats
        WHERE pitches_seen >= 50
    """, (mlb_player_id, levels_played))

    result = cursor.fetchone()

    if result:
        cols = [desc[0] for desc in cursor.description]
        print("\n   Metrics calculated successfully!")
        for col, val in zip(cols, result):
            if val is not None:
                print(f"   {col}: {val}")
    else:
        print("\n   NO METRICS CALCULATED (possibly < 50 pitches)")

    # 3. Check if it's the level matching that's failing
    print(f"\n3. Checking game logs for comparison:")
    cursor.execute("""
        SELECT
            gl.level as game_log_level,
            COUNT(DISTINCT gl.game_pk) as games,
            COUNT(DISTINCT bp.game_pk) as pitch_games
        FROM milb_game_logs gl
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND bp.mlb_batter_id = %s
        WHERE gl.mlb_player_id = %s
            AND gl.season = 2025
        GROUP BY gl.level
        ORDER BY games DESC
    """, (mlb_player_id, mlb_player_id))

    results = cursor.fetchall()
    print("\n   Level comparison (game logs vs pitch data):")
    for level, games, pitch_games in results:
        print(f"   - {level}: {games} game logs, {pitch_games or 0} with pitch data")

    # 4. Check a few more prospects
    print("\n" + "="*80)
    print("CHECKING OTHER TOP PROSPECTS")
    print("="*80)

    test_prospects = [
        (804606, 'Konnor Griffin'),
        (701350, 'Roman Anthony'),
        (692225, 'Kristian Campbell')
    ]

    for mlb_id, name in test_prospects:
        cursor.execute("""
            SELECT COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = 2025
        """, (mlb_id,))

        count = cursor.fetchone()[0]
        print(f"  {name} ({mlb_id}): {count} pitches")

    conn.close()
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)

if __name__ == "__main__":
    test_pitch_queries()