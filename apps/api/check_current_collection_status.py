#!/usr/bin/env python3
"""Check current status of pitch data collections"""

import psycopg2
from datetime import datetime, timedelta

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def check_collection_status():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("=" * 80)
    print("PITCH DATA COLLECTION STATUS CHECK")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Check if any collection scripts are still running by looking at recent activity
    print("\n1. RECENT COLLECTION ACTIVITY:")
    print("-" * 50)

    # Last 5 minutes
    cur.execute("""
        SELECT
            COUNT(*) as new_pitches,
            COUNT(DISTINCT mlb_batter_id) as players_updated,
            COUNT(DISTINCT game_pk) as games_updated,
            MAX(created_at) as last_update
        FROM milb_batter_pitches
        WHERE created_at > NOW() - INTERVAL '5 minutes'
    """)

    recent_5min = cur.fetchone()
    print(f"Last 5 minutes:")
    print(f"  New pitches: {recent_5min[0]:,}")
    print(f"  Players updated: {recent_5min[1]}")
    print(f"  Games updated: {recent_5min[2]}")
    print(f"  Most recent: {recent_5min[3]}")

    # Last hour
    cur.execute("""
        SELECT
            COUNT(*) as new_pitches,
            COUNT(DISTINCT mlb_batter_id) as players_updated,
            COUNT(DISTINCT game_pk) as games_updated
        FROM milb_batter_pitches
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)

    recent_hour = cur.fetchone()
    print(f"\nLast hour:")
    print(f"  New pitches: {recent_hour[0]:,}")
    print(f"  Players updated: {recent_hour[1]}")
    print(f"  Games updated: {recent_hour[2]}")

    # Check specific players from our collection list
    print("\n2. KEY PLAYERS STATUS UPDATE:")
    print("-" * 50)

    cur.execute("""
        WITH player_status AS (
            SELECT
                p.name,
                p.position,
                COUNT(DISTINCT gl.game_pk) as total_games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                COUNT(bp.*) as total_pitches,
                MAX(bp.created_at) as last_pitch_added
            FROM prospects p
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id::text = gl.mlb_player_id::text
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp
                ON p.mlb_player_id::integer = bp.mlb_batter_id
                AND bp.season = 2025
            WHERE p.name IN (
                'Leo De Vries', 'Trey Lipscomb', 'Aidan Miller',
                'Jose Fernandez', 'Max Clark', 'JJ Wetherholt',
                'Jakob Marsee', 'Sammy Stafura'
            )
            GROUP BY p.name, p.position
            ORDER BY p.name
        )
        SELECT * FROM player_status
    """)

    results = cur.fetchall()
    print(f"{'Player':<20} {'Pos':<5} {'Games':<7} {'w/Pitch':<8} {'Coverage':<10} {'Pitches':<10} {'Last Update'}")
    print("-" * 90)

    for row in results:
        name, pos, total_games, games_with_pitches, pitches, last_update = row
        coverage = (games_with_pitches / total_games * 100) if total_games > 0 else 0
        status = "[OK]" if coverage == 100 else "[*]" if coverage > 80 else "[!]"
        last_update_str = last_update.strftime('%H:%M') if last_update else "Never"
        print(f"{name:<20} {pos:<5} {total_games:<7} {games_with_pitches:<8} "
              f"{coverage:>8.1f}% {pitches:<10} {last_update_str:<12} {status}")

    # Overall progress update
    print("\n3. OVERALL COLLECTION PROGRESS:")
    print("-" * 50)

    cur.execute("""
        WITH coverage AS (
            SELECT
                COUNT(DISTINCT p.id) as total_hitters,
                COUNT(DISTINCT CASE WHEN gl.game_pk IS NOT NULL THEN p.id END) as hitters_with_games,
                COUNT(DISTINCT CASE
                    WHEN gl.game_pk IS NOT NULL AND bp.game_pk IS NOT NULL
                    THEN p.id
                END) as hitters_with_pitch_data,
                COUNT(DISTINCT CASE
                    WHEN gl.game_pk = bp.game_pk
                    THEN p.id
                END) as hitters_complete,
                COUNT(DISTINCT gl.game_pk) as total_games,
                COUNT(DISTINCT bp.game_pk) as games_with_pitches
            FROM prospects p
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id::text = gl.mlb_player_id::text
                AND gl.season = 2025
            LEFT JOIN milb_batter_pitches bp
                ON gl.game_pk = bp.game_pk
                AND p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF', 'DH')
        )
        SELECT
            total_hitters,
            hitters_with_games,
            hitters_with_pitch_data,
            hitters_complete,
            total_games,
            games_with_pitches,
            total_games - games_with_pitches as missing_games,
            ROUND((games_with_pitches::numeric / total_games) * 100, 2) as coverage_pct
        FROM coverage
    """)

    result = cur.fetchone()
    print(f"  Total hitting prospects: {result[0]}")
    print(f"  Hitters with 2025 games: {result[1]}")
    print(f"  Hitters with some pitch data: {result[2]}")
    print(f"  Hitters with complete data: {result[3]}")
    print(f"  Total games: {result[4]:,}")
    print(f"  Games with pitch data: {result[5]:,}")
    print(f"  Missing games: {result[6]:,}")
    print(f"  Overall coverage: {result[7]:.2f}%")

    # Progress bar
    coverage = result[7]
    bar_length = int(coverage / 2)
    progress_bar = "=" * bar_length + "-" * (50 - bar_length)
    print(f"\n  Progress: [{progress_bar}] {coverage:.1f}%")

    # Check for players still needing collection
    print("\n4. PLAYERS STILL NEEDING COLLECTION:")
    print("-" * 50)

    cur.execute("""
        SELECT
            p.name,
            p.position,
            COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) as missing_games
        FROM prospects p
        JOIN milb_game_logs gl
            ON p.mlb_player_id::text = gl.mlb_player_id::text
            AND gl.season = 2025
        LEFT JOIN milb_batter_pitches bp
            ON gl.game_pk = bp.game_pk
            AND p.mlb_player_id::integer = bp.mlb_batter_id
        WHERE p.position IN ('SS', 'OF', '3B', '2B', '1B', 'C', 'CF', 'RF', 'LF')
        GROUP BY p.name, p.position
        HAVING COUNT(DISTINCT gl.game_pk) > COUNT(DISTINCT bp.game_pk)
        ORDER BY COUNT(DISTINCT gl.game_pk) - COUNT(DISTINCT bp.game_pk) DESC
        LIMIT 10
    """)

    needs_collection = cur.fetchall()

    if needs_collection:
        print(f"{'Player':<25} {'Pos':<5} {'Missing Games'}")
        print("-" * 45)
        for name, pos, missing in needs_collection:
            print(f"{name:<25} {pos:<5} {missing}")
    else:
        print("[OK] No players with missing data found!")

    # Calculate collection rate
    print("\n5. COLLECTION RATE ANALYSIS:")
    print("-" * 50)

    cur.execute("""
        SELECT
            DATE_TRUNC('hour', created_at) as hour,
            COUNT(*) as pitches_added
        FROM milb_batter_pitches
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY DATE_TRUNC('hour', created_at)
        ORDER BY hour DESC
        LIMIT 5
    """)

    hourly_rates = cur.fetchall()
    print("Recent hourly collection rates:")
    for hour, count in hourly_rates:
        print(f"  {hour.strftime('%Y-%m-%d %H:00')}: {count:,} pitches")

    # Status determination
    print("\n" + "=" * 80)
    print("STATUS SUMMARY:")
    print("-" * 80)

    if recent_5min[0] > 100:
        print("[ACTIVE] Collection is currently running")
        print(f"  Rate: ~{recent_5min[0] / 300:.1f} pitches/second")
    elif recent_hour[0] > 100:
        print("[RECENT] Collection was active in the last hour")
        print(f"  {recent_hour[0]:,} pitches added")
    else:
        print("[IDLE] No significant collection activity detected")

    if result[6] == 0:
        print("[COMPLETE] All games have pitch data!")
    elif result[6] < 50:
        print(f"[NEARLY COMPLETE] Only {result[6]} games missing data")
    else:
        print(f"[IN PROGRESS] {result[6]:,} games still need collection")

    print("\nCoverage Status: ", end="")
    if coverage >= 99.5:
        print("[EXCELLENT] 99.5%+ coverage achieved!")
    elif coverage >= 95:
        print(f"[GOOD] {coverage:.1f}% coverage")
    elif coverage >= 90:
        print(f"[FAIR] {coverage:.1f}% coverage")
    else:
        print(f"[NEEDS WORK] {coverage:.1f}% coverage")

    print("=" * 80)

    conn.close()

if __name__ == "__main__":
    check_collection_status()