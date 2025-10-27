#!/usr/bin/env python3
"""
Quick audit report for pitch data completeness
"""

import psycopg2
from datetime import datetime
import json

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def run_quick_audit():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("PITCH DATA COMPLETENESS AUDIT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Overall 2025 statistics
    print("\nOVERALL 2025 SEASON STATISTICS:")
    print("-" * 50)

    cur.execute("""
        SELECT
            COUNT(DISTINCT p.id) as total_prospects,
            COUNT(DISTINCT CASE WHEN gl.season = 2025 THEN p.id END) as prospects_with_2025_games,
            COUNT(DISTINCT gl.game_pk) as total_games,
            COUNT(DISTINCT bp.game_pk) as games_with_pitches,
            COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
            ROUND((COUNT(DISTINCT bp.game_pk)::numeric / COUNT(DISTINCT gl.game_pk)) * 100, 1) as coverage_pct,
            COUNT(bp.*) as total_pitches
        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id::text = gl.mlb_player_id::text
            AND gl.season = 2025
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND p.mlb_player_id::integer = bp.mlb_batter_id
        WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
            AND p.mlb_player_id IS NOT NULL
    """)

    result = cur.fetchone()
    print(f"  Total hitting prospects: {result[0]}")
    print(f"  Prospects with 2025 games: {result[1]}")
    print(f"  Total games played: {result[2]:,}")
    print(f"  Games with pitch data: {result[3]:,}")
    print(f"  Games missing pitch data: {result[4]:,}")
    print(f"  Overall coverage: {result[5]}%")
    print(f"  Total pitches collected: {result[6]:,}")

    # Coverage breakdown
    print("\nCOVERAGE BREAKDOWN:")
    print("-" * 50)

    cur.execute("""
        WITH player_coverage AS (
            SELECT
                p.name,
                COUNT(DISTINCT gl.game_pk) as total_games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                CASE
                    WHEN COUNT(DISTINCT gl.game_pk) = 0 THEN 'No Games'
                    WHEN COUNT(DISTINCT bp.game_pk) = 0 THEN 'No Pitch Data'
                    WHEN COUNT(DISTINCT gl.game_pk) = COUNT(DISTINCT bp.game_pk) THEN 'Complete'
                    WHEN COUNT(DISTINCT bp.game_pk)::numeric / COUNT(DISTINCT gl.game_pk) >= 0.8 THEN 'Good (80%+)'
                    WHEN COUNT(DISTINCT bp.game_pk)::numeric / COUNT(DISTINCT gl.game_pk) >= 0.5 THEN 'Partial (50-80%)'
                    ELSE 'Poor (<50%)'
                END as coverage_status
            FROM prospects p
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id::text = gl.mlb_player_id::text
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp
                ON gl.game_pk = bp.game_pk
                AND p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
                AND p.mlb_player_id IS NOT NULL
            GROUP BY p.name
        )
        SELECT
            coverage_status,
            COUNT(*) as prospect_count
        FROM player_coverage
        GROUP BY coverage_status
        ORDER BY
            CASE coverage_status
                WHEN 'Complete' THEN 1
                WHEN 'Good (80%+)' THEN 2
                WHEN 'Partial (50-80%)' THEN 3
                WHEN 'Poor (<50%)' THEN 4
                WHEN 'No Pitch Data' THEN 5
                WHEN 'No Games' THEN 6
            END
    """)

    results = cur.fetchall()
    for status, count in results:
        icon = "[OK]" if status == "Complete" else "[G]" if "Good" in status else "[P]" if "Partial" in status else "[!]" if "Poor" in status else "[X]" if "No Pitch" in status else "[-]"
        print(f"  {icon} {status:<20}: {count} prospects")

    # Top players needing collection
    print("\n** TOP PRIORITY - PLAYERS NEEDING COLLECTION:")
    print("-" * 50)

    cur.execute("""
        SELECT
            p.name,
            p.position,
            p.organization,
            COUNT(DISTINCT gl.game_pk) as total_games,
            COUNT(DISTINCT bp.game_pk) as games_with_pitches,
            COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games,
            ROUND((COUNT(DISTINCT bp.game_pk)::numeric / NULLIF(COUNT(DISTINCT gl.game_pk), 0)) * 100, 1) as coverage_pct
        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id::text = gl.mlb_player_id::text
            AND gl.season = 2025
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND p.mlb_player_id::integer = bp.mlb_batter_id
        WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
            AND p.mlb_player_id IS NOT NULL
        GROUP BY p.name, p.position, p.organization
        HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
            AND COUNT(DISTINCT gl.game_pk) > 0
        ORDER BY COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) DESC
        LIMIT 15
    """)

    results = cur.fetchall()
    print(f"{'Name':<25} {'Pos':<5} {'Team':<5} {'Games':<7} {'w/Pitch':<8} {'Missing':<8} {'Coverage'}")
    print("-" * 75)

    for row in results:
        coverage = row[6] if row[6] is not None else 0.0
        status = "[!]" if coverage < 20 else "[W]" if coverage < 50 else "[G]"
        print(f"{row[0]:<25} {row[1]:<5} {row[2]:<5} {row[3]:<7} {row[4]:<8} {row[5]:<8} {coverage:>6.1f}% {status}")

    # Check specific players
    print("\n> KEY PLAYERS STATUS CHECK:")
    print("-" * 50)

    cur.execute("""
        SELECT
            p.name,
            COUNT(DISTINCT gl.game_pk) as total_games,
            COUNT(DISTINCT bp.game_pk) as games_with_pitches,
            COUNT(bp.*) as total_pitches
        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id::text = gl.mlb_player_id::text
            AND gl.season = 2025
        LEFT JOIN milb_batter_pitches bp
            ON p.mlb_player_id::integer = bp.mlb_batter_id
            AND bp.season = 2025
        WHERE p.name IN ('Leo De Vries', 'Bryce Eldridge', 'Jackson Holliday', 'Junior Caminero')
        GROUP BY p.name
        ORDER BY p.name
    """)

    results = cur.fetchall()
    for name, total_games, games_with_pitches, pitches in results:
        coverage = (games_with_pitches / total_games * 100) if total_games > 0 else 0
        status = "[OK]" if coverage == 100 else "[G]" if coverage > 80 else "[W]" if coverage > 50 else "[!]"
        print(f"  {name:<20}: {games_with_pitches}/{total_games} games ({coverage:.1f}%), {pitches:,} pitches {status}")

    # Recent collection activity
    print("\n~ RECENT COLLECTION ACTIVITY (Last 24 hours):")
    print("-" * 50)

    cur.execute("""
        SELECT
            COUNT(*) as new_pitches,
            COUNT(DISTINCT mlb_batter_id) as players_updated,
            COUNT(DISTINCT game_pk) as games_updated,
            MIN(created_at) as first_update,
            MAX(created_at) as last_update
        FROM milb_batter_pitches
        WHERE created_at > NOW() - INTERVAL '24 hours'
    """)

    result = cur.fetchone()
    if result[0] > 0:
        print(f"  New pitches added: {result[0]:,}")
        print(f"  Players updated: {result[1]}")
        print(f"  Games updated: {result[2]}")
        print(f"  Activity window: {result[3].strftime('%H:%M')} to {result[4].strftime('%H:%M')}")
    else:
        print("  No collection activity in the last 24 hours")

    # Monthly coverage pattern
    print("\n# MONTHLY COVERAGE PATTERN (2025):")
    print("-" * 50)

    cur.execute("""
        SELECT
            TO_CHAR(gl.game_date, 'Mon') as month,
            COUNT(DISTINCT gl.game_pk) as total_games,
            COUNT(DISTINCT bp.game_pk) as games_with_pitches,
            ROUND((COUNT(DISTINCT bp.game_pk)::numeric / COUNT(DISTINCT gl.game_pk)) * 100, 1) as coverage_pct
        FROM milb_game_logs gl
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND gl.mlb_player_id::integer = bp.mlb_batter_id
        WHERE gl.season = 2025
        GROUP BY TO_CHAR(gl.game_date, 'Mon'), EXTRACT(MONTH FROM gl.game_date)
        ORDER BY EXTRACT(MONTH FROM gl.game_date)
    """)

    results = cur.fetchall()
    for month, total, with_pitches, coverage in results:
        bar_length = int(coverage / 5) if coverage else 0
        bar = "=" * bar_length + "-" * (20 - bar_length)
        print(f"  {month}: {bar} {coverage}% ({with_pitches}/{total} games)")

    print("\n" + "=" * 80)
    print("RECOMMENDATIONS:")
    print("-" * 80)

    # Generate recommendations based on findings
    cur.execute("""
        SELECT
            COUNT(*) as prospects_no_data
        FROM prospects p
        INNER JOIN milb_game_logs gl
            ON p.mlb_player_id::text = gl.mlb_player_id::text
            AND gl.season = 2025
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND p.mlb_player_id::integer = bp.mlb_batter_id
        WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH', 'IF', 'UT')
            AND p.mlb_player_id IS NOT NULL
        GROUP BY p.id
        HAVING COUNT(DISTINCT gl.game_pk) > 0
            AND COUNT(DISTINCT bp.game_pk) = 0
    """)

    no_data_count = cur.fetchone()
    if no_data_count and no_data_count[0] > 0:
        print(f"  [!] CRITICAL: {no_data_count[0]} prospects have games but NO pitch data at all")
        print(f"     -> Run comprehensive collection for these players immediately")

    if result[5] < 80:  # If overall coverage < 80%
        print(f"  [W] HIGH: Overall coverage is only {result[5]}% - below recommended 80% threshold")
        print(f"     -> Schedule regular collection runs to fill {result[4]:,} missing games")

    print("\n" + "=" * 80)

    # Save summary to JSON
    summary = {
        'timestamp': datetime.now().isoformat(),
        'overall_coverage_pct': float(result[5]) if result[5] else 0,
        'total_games': result[2],
        'games_with_pitches': result[3],
        'missing_games': result[4],
        'total_pitches': result[6]
    }

    filename = f"audit_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n[OK] Audit complete! Summary saved to: {filename}")

    conn.close()

if __name__ == "__main__":
    run_quick_audit()