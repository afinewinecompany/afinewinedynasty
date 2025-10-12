"""
Check 2021 MiLB data status
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

# Get database connection
db_url = os.getenv('SQLALCHEMY_DATABASE_URI')
if 'postgresql+asyncpg://' in db_url:
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')

engine = create_engine(db_url)

print("="*70)
print("2021 MiLB DATA CHECK")
print("="*70)
print()

with engine.connect() as conn:
    # Check game logs for 2021
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_logs,
            COUNT(DISTINCT mlb_player_id) as players
        FROM milb_game_logs
        WHERE season = 2021
    """))
    row = result.fetchone()
    print(f"2021 Game Logs: {row[0]:,} records for {row[1]} players")

    # Check plate appearances for 2021
    result = conn.execute(text("""
        SELECT
            COUNT(*) as total_pa,
            COUNT(DISTINCT mlb_player_id) as players
        FROM milb_plate_appearances
        WHERE season = 2021
    """))
    row = result.fetchone()
    print(f"2021 Plate Appearances: {row[0]:,} records for {row[1]} players")

    # Find top players with game logs but no PBP data
    print()
    print("Top players with 2021 game logs but NO plate appearance data:")
    print("-"*70)

    result = conn.execute(text("""
        WITH player_stats AS (
            SELECT
                g.mlb_player_id,
                COUNT(*) as games,
                MAX(p.name) as name,
                MAX(p.organization) as org,
                ROUND(AVG(g.batting_avg), 3) as avg,
                SUM(g.hits) as hits,
                SUM(g.home_runs) as hr
            FROM milb_game_logs g
            LEFT JOIN prospects p ON g.mlb_player_id::text = p.mlb_player_id
            WHERE g.season = 2021
            GROUP BY g.mlb_player_id
        )
        SELECT
            ps.name,
            ps.org,
            ps.games,
            ps.avg,
            ps.hits,
            ps.hr,
            ps.mlb_player_id
        FROM player_stats ps
        WHERE NOT EXISTS (
            SELECT 1
            FROM milb_plate_appearances pa
            WHERE pa.mlb_player_id = ps.mlb_player_id
            AND pa.season = 2021
        )
        AND ps.games > 50  -- Only players with significant games
        ORDER BY ps.games DESC
        LIMIT 20
    """))

    rows = list(result)
    if rows:
        print(f"{'Player':<30} {'Org':<5} {'Games':<8} {'AVG':<7} {'Hits':<6} {'HR':<5} {'ID':<8}")
        print("-"*70)
        for row in rows:
            name = row[0] or f"Player {row[6]}"
            org = row[1] or "???"
            avg_str = f"{row[3]:.3f}" if row[3] is not None else "N/A"
            print(f"{name[:30]:<30} {org:<5} {row[2]:<8} {avg_str:<7} {row[4] or 0:<6} {row[5] or 0:<5} {row[6]:<8}")
    else:
        print("No players found")

    # Check what seasons need collection
    print()
    print("Plate Appearances Coverage by Season:")
    print("-"*70)

    result = conn.execute(text("""
        SELECT
            s.season,
            COALESCE(g.game_log_count, 0) as game_logs,
            COALESCE(g.player_count, 0) as gl_players,
            COALESCE(p.pa_count, 0) as plate_apps,
            COALESCE(p.pa_players, 0) as pa_players,
            CASE
                WHEN COALESCE(g.player_count, 0) > 0
                THEN ROUND(100.0 * COALESCE(p.pa_players, 0) / g.player_count, 1)
                ELSE 0
            END as coverage_pct
        FROM (
            SELECT generate_series(2021, 2025) as season
        ) s
        LEFT JOIN (
            SELECT season,
                   COUNT(*) as game_log_count,
                   COUNT(DISTINCT mlb_player_id) as player_count
            FROM milb_game_logs
            GROUP BY season
        ) g ON s.season = g.season
        LEFT JOIN (
            SELECT season,
                   COUNT(*) as pa_count,
                   COUNT(DISTINCT mlb_player_id) as pa_players
            FROM milb_plate_appearances
            GROUP BY season
        ) p ON s.season = p.season
        ORDER BY s.season DESC
    """))

    print(f"{'Season':<8} {'Game Logs':<12} {'GL Players':<12} {'Plate Apps':<12} {'PA Players':<12} {'Coverage %':<10}")
    print("-"*70)
    for row in result:
        print(f"{row[0]:<8} {row[1]:<12,} {row[2]:<12} {row[3]:<12,} {row[4]:<12} {row[5]:<10.1f}%")