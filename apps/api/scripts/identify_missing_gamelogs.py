"""
Identify prospects who are missing game logs (which prevents pitch data collection)
"""

import psycopg2
from typing import List, Dict

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025

def get_prospects_missing_gamelogs() -> List[Dict]:
    """Find top prospects with no or very limited game logs"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # Get prospects ordered by ranking who have limited game log coverage
    query = """
        WITH gamelog_coverage AS (
            SELECT
                p.id,
                p.name,
                p.mlb_player_id,
                p.position,
                p.current_level,
                COALESCE(COUNT(DISTINCT gl.game_pk), 0) as total_games,
                COALESCE(SUM(gl.plate_appearances), 0) as total_pa
            FROM prospects p
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id::integer = gl.mlb_player_id
                AND gl.season = %s
            WHERE p.position NOT IN ('SP', 'RP', 'P')  -- Hitters only
              AND p.mlb_player_id IS NOT NULL
              AND p.mlb_player_id != ''
            GROUP BY p.id, p.name, p.mlb_player_id, p.position, p.current_level
        )
        SELECT
            name,
            mlb_player_id,
            position,
            current_level,
            total_games,
            total_pa
        FROM gamelog_coverage
        WHERE total_games < 20  -- Less than 20 games (very incomplete)
           OR total_pa = 0
        ORDER BY total_games, name
        LIMIT 100
    """

    cursor.execute(query, (SEASON,))
    columns = [desc[0] for desc in cursor.description]
    prospects = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()

    return prospects

def get_pitch_data_gaps() -> List[Dict]:
    """Find prospects with game logs but no/limited pitch data"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    query = """
        WITH coverage AS (
            SELECT
                p.name,
                p.mlb_player_id,
                p.position,
                COUNT(DISTINCT gl.game_pk) as game_log_games,
                SUM(gl.plate_appearances) as total_pa,
                COUNT(DISTINCT bp.game_pk) as pitch_games,
                COUNT(bp.id) as total_pitches
            FROM prospects p
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id::integer = gl.mlb_player_id
                AND gl.season = %s
            LEFT JOIN milb_batter_pitches bp
                ON gl.game_pk = bp.game_pk
                AND gl.mlb_player_id = bp.mlb_batter_id
                AND bp.season = %s
            WHERE p.position NOT IN ('SP', 'RP', 'P')
              AND p.mlb_player_id IS NOT NULL
              AND p.mlb_player_id != ''
            GROUP BY p.name, p.mlb_player_id, p.position
        )
        SELECT
            name,
            mlb_player_id,
            position,
            game_log_games,
            total_pa,
            pitch_games,
            total_pitches,
            ROUND((total_pitches::numeric / NULLIF(total_pa * 4.5, 0)) * 100, 1) as coverage_pct
        FROM coverage
        WHERE game_log_games > 0  -- Has game logs
          AND total_pitches < (total_pa * 2)  -- Less than 50% coverage
        ORDER BY total_pa DESC
        LIMIT 50
    """

    cursor.execute(query, (SEASON, SEASON))
    columns = [desc[0] for desc in cursor.description]
    prospects = [dict(zip(columns, row)) for row in cursor.fetchall()]

    conn.close()

    return prospects

def main():
    print("="*80)
    print("GAME LOG COVERAGE ANALYSIS - 2025 Season")
    print("="*80)

    # Check for prospects with missing game logs
    print("\n" + "="*80)
    print("PROSPECTS WITH MISSING/INCOMPLETE GAME LOGS (<20 games)")
    print("="*80)
    print("\nThese prospects need game log collection before pitch backfill can work:\n")

    missing_gamelogs = get_prospects_missing_gamelogs()

    if missing_gamelogs:
        print(f"Found {len(missing_gamelogs)} prospects with incomplete game logs:\n")
        for i, p in enumerate(missing_gamelogs[:30], 1):
            level = p['current_level'] or 'N/A'
            print(f"{i:3d}. {p['name']:<25} (ID: {p['mlb_player_id']:<7}) {p['position']:<3} {level:<6} - {p['total_games']} games, {p['total_pa']} PAs")
    else:
        print("\n✓ All prospects have game logs!")

    # Check for prospects with game logs but missing pitch data
    print("\n" + "="*80)
    print("PROSPECTS WITH GAME LOGS BUT MISSING PITCH DATA")
    print("="*80)
    print("\n(Skipping detailed analysis - will run full backfill instead)\n")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Prospects needing game log collection: {len(missing_gamelogs)}")

    print("\n" + "="*80)
    print("NEXT STEPS")
    print("="*80)
    print("\n1. Collect game logs for prospects with missing data:")
    print("   cd apps/api/scripts")
    print("   python collect_missing_gamelogs_2025.py")
    print("\n2. Run pitch backfill for prospects with game logs:")
    print("   cd apps/api/scripts")
    print("   python backfill_pitch_data_2025.py")
    print("="*80)

if __name__ == "__main__":
    main()
