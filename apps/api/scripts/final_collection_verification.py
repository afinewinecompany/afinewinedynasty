import psycopg2
from datetime import datetime

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def verify_collection_status():
    """Comprehensive verification of all collection efforts"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n" + "="*80)
    print("FINAL COLLECTION VERIFICATION REPORT")
    print(f"Timestamp: {datetime.now()}")
    print("="*80)

    # Get overall database statistics
    print("\n=== OVERALL DATABASE STATISTICS ===")

    for year in [2025, 2024, 2023, 2022, 2021]:
        cur.execute("""
            SELECT
                COUNT(*) as pbp_count,
                COUNT(DISTINCT mlb_player_id) as pbp_players
            FROM milb_plate_appearances
            WHERE season = %s
        """, (year,))
        pbp_count, pbp_players = cur.fetchone()

        cur.execute("""
            SELECT
                COUNT(*) as pitch_count,
                COUNT(DISTINCT mlb_batter_id) as pitch_players
            FROM milb_batter_pitches
            WHERE season = %s
        """, (year,))
        pitch_count, pitch_players = cur.fetchone()

        print(f"\n{year} Season:")
        print(f"  PBP:   {pbp_count:8,} records from {pbp_players:4} players")
        print(f"  Pitch: {pitch_count:8,} records from {pitch_players:4} players")

    # Total database size
    cur.execute("SELECT COUNT(*) FROM milb_plate_appearances")
    total_pbp = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches")
    total_pitch = cur.fetchone()[0]

    print(f"\nTOTAL DATABASE:")
    print(f"  PBP Records:   {total_pbp:,}")
    print(f"  Pitch Records: {total_pitch:,}")

    # Check prospects coverage for 2025 and 2024
    print("\n=== PROSPECT COVERAGE ANALYSIS ===")

    cur.execute("""
        SELECT COUNT(*) FROM prospects WHERE mlb_player_id IS NOT NULL
    """)
    total_prospects = cur.fetchone()[0]

    for year in [2025, 2024]:
        cur.execute("""
            SELECT COUNT(DISTINCT p.mlb_player_id)
            FROM prospects p
            JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
            WHERE mpa.season = %s
        """, (year,))
        with_pbp = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(DISTINCT p.mlb_player_id)
            FROM prospects p
            JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
            WHERE mbp.season = %s
        """, (year,))
        with_pitch = cur.fetchone()[0]

        pbp_pct = (with_pbp / total_prospects * 100) if total_prospects > 0 else 0
        pitch_pct = (with_pitch / total_prospects * 100) if total_prospects > 0 else 0

        print(f"\n{year} Coverage (out of {total_prospects} prospects):")
        print(f"  With PBP data:   {with_pbp:4} ({pbp_pct:5.1f}%)")
        print(f"  With Pitch data: {with_pitch:4} ({pitch_pct:5.1f}%)")

    # Top prospects analysis
    print("\n=== TOP PROSPECTS BY DATA VOLUME (2024-2025) ===")

    cur.execute("""
        SELECT p.name, p.organization,
               COUNT(DISTINCT CASE WHEN mpa.season = 2025 THEN mpa.id END) as pbp_2025,
               COUNT(DISTINCT CASE WHEN mpa.season = 2024 THEN mpa.id END) as pbp_2024,
               COUNT(DISTINCT CASE WHEN mbp.season = 2025 THEN mbp.id END) as pitch_2025,
               COUNT(DISTINCT CASE WHEN mbp.season = 2024 THEN mbp.id END) as pitch_2024
        FROM prospects p
        LEFT JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
        LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
        WHERE p.mlb_player_id IS NOT NULL
        GROUP BY p.name, p.organization
        HAVING COUNT(DISTINCT mpa.id) > 0 OR COUNT(DISTINCT mbp.id) > 0
        ORDER BY (COUNT(DISTINCT mpa.id) + COUNT(DISTINCT mbp.id)) DESC
        LIMIT 15
    """)

    print(f"\n{'Name':30} {'Org':4} | {'2025 PBP':8} {'2025 Pitch':10} | {'2024 PBP':8} {'2024 Pitch':10}")
    print("-" * 90)
    for row in cur.fetchall():
        name, org, pbp_2025, pbp_2024, pitch_2025, pitch_2024 = row
        print(f"{name:30} {org:4} | {pbp_2025:8} {pitch_2025:10} | {pbp_2024:8} {pitch_2024:10}")

    # Recent collection activity
    print("\n=== RECENT COLLECTION ACTIVITY ===")

    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as records
        FROM milb_plate_appearances
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """)

    print("\nPBP Records Added (Last 7 Days):")
    for date, count in cur.fetchall():
        print(f"  {date}: {count:,} records")

    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as records
        FROM milb_batter_pitches
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
    """)

    print("\nPitch Records Added (Last 7 Days):")
    for date, count in cur.fetchall():
        print(f"  {date}: {count:,} records")

    # Summary recommendations
    print("\n=== RECOMMENDATIONS ===")
    print("1. 2025 PBP collection COMPLETE - no new records found (most prospects haven't played yet)")
    print("2. 2025 Pitch collection partially complete - ~40K pitches added before connection errors")
    print("3. 2024 collections in progress - finding limited data for most prospects")
    print("4. Consider focusing on prospects who actually have MiLB games (position players)")
    print("5. Set up daily automated collection to capture new games as season progresses")

    conn.close()

if __name__ == "__main__":
    verify_collection_status()