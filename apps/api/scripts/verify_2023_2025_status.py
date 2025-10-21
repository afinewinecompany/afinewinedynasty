import psycopg2

DB_CONFIG = {
    'host': 'nozomi.proxy.rlwy.net',
    'port': 39235,
    'database': 'railway',
    'user': 'postgres',
    'password': 'BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp'
}

def verify_pitcher_data_status():
    """Verify pitcher data collection status for 2023-2025"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    print("\n" + "="*80)
    print("PITCHER PITCH DATA STATUS: 2023-2025")
    print("="*80)

    for season in [2023, 2024, 2025]:
        print(f"\n{'='*80}")
        print(f"SEASON {season}")
        print(f"{'='*80}")

        # Total pitchers in prospects table
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
            AND position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        """)
        total_pitchers = cur.fetchone()[0]
        print(f"\nTotal pitchers in prospects: {total_pitchers}")

        # Pitchers with appearances
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM milb_pitcher_appearances
            WHERE season = %s
        """, (season,))
        pitchers_with_appearances = cur.fetchone()[0]
        print(f"Pitchers with {season} appearances: {pitchers_with_appearances}")

        # Pitchers with pitch data
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_pitcher_id)
            FROM milb_pitcher_pitches
            WHERE season = %s
        """, (season,))
        pitchers_with_pitches = cur.fetchone()[0]
        print(f"Pitchers with {season} pitch data: {pitchers_with_pitches}")

        # Gap analysis
        gap = pitchers_with_appearances - pitchers_with_pitches
        print(f"\nGAP: {gap} pitchers have appearances but NO pitch data")

        if gap > 0:
            # Get sample of missing pitchers
            cur.execute("""
                SELECT p.mlb_player_id, p.name, COUNT(mpa.game_pk) as games
                FROM prospects p
                INNER JOIN milb_pitcher_appearances mpa
                    ON mpa.mlb_player_id = p.mlb_player_id::INTEGER
                    AND mpa.season = %s
                WHERE NOT EXISTS (
                    SELECT 1 FROM milb_pitcher_pitches mpp
                    WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER
                    AND mpp.season = %s
                )
                AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
                GROUP BY p.mlb_player_id, p.name
                ORDER BY COUNT(mpa.game_pk) DESC
                LIMIT 10
            """, (season, season))

            missing = cur.fetchall()
            if missing:
                print(f"\nTop 10 pitchers missing {season} pitch data (by game count):")
                for pid, name, games in missing:
                    print(f"  {name} (ID: {pid}): {games} games")

        # Pitch data quality check
        if pitchers_with_pitches > 0:
            cur.execute("""
                SELECT
                    COUNT(*) as total_pitches,
                    COUNT(pitch_type) as pitches_with_type,
                    COUNT(start_speed) as pitches_with_speed,
                    AVG(start_speed) as avg_speed
                FROM milb_pitcher_pitches
                WHERE season = %s
            """, (season,))

            total, with_type, with_speed, avg_speed = cur.fetchone()
            print(f"\nData Quality Check for {season}:")
            print(f"  Total pitch records: {total:,}")
            print(f"  Pitches with type: {with_type:,} ({100*with_type/total:.1f}%)")
            print(f"  Pitches with speed: {with_speed:,} ({100*with_speed/total:.1f}%)")
            if avg_speed:
                print(f"  Average pitch speed: {round(avg_speed, 1)} mph")
            else:
                print(f"  Average pitch speed: N/A (all null)")

    # Summary recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    needs_collection = []
    for season in [2023, 2024, 2025]:
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM milb_pitcher_appearances
            WHERE season = %s
        """, (season,))
        with_apps = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT mlb_pitcher_id)
            FROM milb_pitcher_pitches
            WHERE season = %s
        """, (season,))
        with_pitches = cur.fetchone()[0]

        gap = with_apps - with_pitches
        if gap > 10:  # More than 10 missing
            needs_collection.append((season, gap))

    if needs_collection:
        print("\nSeasons needing pitch data collection:")
        for season, gap in needs_collection:
            print(f"  {season}: {gap} pitchers missing pitch data")
        print("\nRun the respective collect_YYYY_pitcher_data_robust.py scripts")
    else:
        print("\n✓ All seasons have good coverage!")
        print("  Small gaps are expected (pitchers may not have thrown in those games)")

    conn.close()

if __name__ == "__main__":
    verify_pitcher_data_status()
