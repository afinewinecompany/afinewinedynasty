import psycopg2

DB_CONFIG = {
    'host': 'nozomi.proxy.rlwy.net',
    'port': 39235,
    'database': 'railway',
    'user': 'postgres',
    'password': 'BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp'
}

def verify_sport_id_coverage():
    """Verify we have data from all MiLB sport levels"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("\n" + "="*80)
    print("SPORT ID COVERAGE VERIFICATION")
    print("="*80)

    # Check pitcher appearances by level
    print("\n### PITCHER APPEARANCES BY LEVEL ###\n")
    for season in [2023, 2024, 2025]:
        print(f"Season {season}:")
        cur.execute("""
            SELECT level, COUNT(*) as games, COUNT(DISTINCT mlb_player_id) as pitchers
            FROM milb_pitcher_appearances
            WHERE season = %s
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'High-A' THEN 3
                    WHEN 'Single-A' THEN 4
                    ELSE 5
                END
        """, (season,))

        results = cur.fetchall()
        if results:
            total_games = 0
            total_pitchers = set()
            for level, games, pitchers in results:
                print(f"  {level:12s}: {games:5,} games, {pitchers:3} pitchers")
                total_games += games
            print(f"  {'TOTAL':12s}: {total_games:5,} games")
        else:
            print(f"  No data for {season}")
        print()

    # Check batter plate appearances - check if we have level info
    print("\n### BATTER DATA BY SEASON ###\n")
    for season in [2023, 2024, 2025]:
        cur.execute("""
            SELECT COUNT(*) as pas, COUNT(DISTINCT mlb_player_id) as batters
            FROM milb_plate_appearances
            WHERE season = %s
        """, (season,))

        pas, batters = cur.fetchone()
        print(f"Season {season}: {pas:6,} PAs, {batters:3} batters")

    # Check for multi-level players
    print("\n### MULTI-LEVEL PLAYERS (2023-2024) ###\n")
    for season in [2023, 2024]:
        print(f"Season {season}:")

        # Pitchers at multiple levels
        cur.execute("""
            SELECT mlb_player_id, COUNT(DISTINCT level) as level_count,
                   STRING_AGG(DISTINCT level, ', ' ORDER BY level) as levels
            FROM milb_pitcher_appearances
            WHERE season = %s
            GROUP BY mlb_player_id
            HAVING COUNT(DISTINCT level) > 1
            ORDER BY level_count DESC, mlb_player_id
            LIMIT 10
        """, (season,))

        multi_level = cur.fetchall()
        if multi_level:
            print(f"  Pitchers at multiple levels: {len(multi_level)}")
            print(f"  Top 10 examples:")
            for player_id, level_count, levels in multi_level[:5]:
                # Get player name
                cur.execute("SELECT name FROM prospects WHERE mlb_player_id = %s", (str(player_id),))
                result = cur.fetchone()
                name = result[0] if result else "Unknown"
                print(f"    {name:30s} (ID: {player_id}): {level_count} levels ({levels})")
        else:
            print(f"  No multi-level pitchers found")
        print()

    # Verify the 4 sport IDs are represented
    print("\n### LEVEL COVERAGE CHECK ###\n")
    expected_levels = ['AAA', 'AA', 'High-A', 'Single-A']

    for season in [2023, 2024, 2025]:
        cur.execute("""
            SELECT DISTINCT level
            FROM milb_pitcher_appearances
            WHERE season = %s
        """, (season,))

        levels_found = {row[0] for row in cur.fetchall()}
        missing = set(expected_levels) - levels_found

        print(f"Season {season}:")
        print(f"  Levels found: {', '.join(sorted(levels_found))}")
        if missing:
            print(f"  Missing levels: {', '.join(sorted(missing))} ⚠️")
        else:
            print(f"  ✓ All 4 standard MiLB levels present")
        print()

    conn.close()

    print("="*80)
    print("VERIFICATION COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    verify_sport_id_coverage()
