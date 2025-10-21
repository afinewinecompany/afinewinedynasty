"""Test the backfill query"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

query = """
    WITH game_coverage AS (
        SELECT
            gl.mlb_player_id,
            COUNT(DISTINCT gl.game_pk) as total_games,
            SUM(gl.plate_appearances) as total_pa,
            COUNT(DISTINCT bp.game_pk) as games_with_pitches,
            COUNT(bp.pitch_id) as total_pitches
        FROM milb_game_logs gl
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND gl.mlb_player_id = bp.mlb_batter_id
            AND gl.season = bp.season
        WHERE gl.season = %s
          AND gl.plate_appearances > 0
        GROUP BY gl.mlb_player_id
    ),
    prospect_info AS (
        SELECT
            p.id,
            p.name,
            p.mlb_player_id,
            p.position,
            gc.total_games,
            gc.total_pa,
            gc.games_with_pitches,
            COALESCE(gc.total_pitches, 0) as total_pitches,
            (gc.total_pa * 4.5) as expected_pitches,
            ROUND((COALESCE(gc.total_pitches, 0)::numeric / NULLIF(gc.total_pa * 4.5, 0)) * 100, 1) as coverage_pct
        FROM prospects p
        INNER JOIN game_coverage gc ON p.mlb_player_id = gc.mlb_player_id
        WHERE p.position NOT IN ('SP', 'RP', 'P')
    )
    SELECT *
    FROM prospect_info
    WHERE coverage_pct < 50
       OR total_pitches = 0
    ORDER BY expected_pitches DESC
    LIMIT 10
"""

try:
    print(f"Executing query for season {SEASON}...")
    cursor.execute(query, (SEASON,))

    print(f"Description: {cursor.description}")

    if cursor.description:
        columns = [desc[0] for desc in cursor.description]
        print(f"\nColumns: {columns}")

        rows = cursor.fetchall()
        print(f"\nFound {len(rows)} prospects")

        for row in rows[:5]:
            prospect = dict(zip(columns, row))
            print(f"\n{prospect['name']}: {prospect['total_pitches']} pitches, {prospect['coverage_pct']}% coverage")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    conn.close()
