import psycopg2
from datetime import datetime

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def verify_collection_status():
    """Verify the current status of 2025 data collection"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n" + "="*70)
    print("2025 COLLECTION STATUS VERIFICATION")
    print(f"Timestamp: {datetime.now()}")
    print("="*70)

    # Get current counts
    cur.execute("SELECT COUNT(*) FROM milb_plate_appearances WHERE season = 2025")
    total_pbp = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2025")
    total_pitch = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_player_id) FROM milb_plate_appearances WHERE season = 2025")
    unique_pbp = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season = 2025")
    unique_pitch = cur.fetchone()[0]

    print(f"\n=== CURRENT DATABASE TOTALS (2025) ===")
    print(f"PBP Records:        {total_pbp:,}")
    print(f"Pitch Records:      {total_pitch:,}")
    print(f"Players with PBP:   {unique_pbp:,}")
    print(f"Players with Pitch: {unique_pitch:,}")

    # Check prospects with most recent data
    cur.execute("""
        SELECT p.name, p.organization, COUNT(*) as pa_count
        FROM milb_plate_appearances mpa
        JOIN prospects p ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
        WHERE mpa.season = 2025
        GROUP BY p.name, p.organization
        ORDER BY pa_count DESC
        LIMIT 10
    """)

    print(f"\n=== TOP 10 PROSPECTS BY 2025 PAs ===")
    for name, org, count in cur.fetchall():
        print(f"{name:30} ({org:3}) - {count:4} PAs")

    # Check prospects with pitch data
    cur.execute("""
        SELECT p.name, p.organization, COUNT(*) as pitch_count
        FROM milb_batter_pitches mbp
        JOIN prospects p ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
        WHERE mbp.season = 2025
        GROUP BY p.name, p.organization
        ORDER BY pitch_count DESC
        LIMIT 10
    """)

    print(f"\n=== TOP 10 PROSPECTS BY 2025 PITCHES ===")
    for name, org, count in cur.fetchall():
        print(f"{name:30} ({org:3}) - {count:4} pitches")

    # Check most recent game dates
    cur.execute("""
        SELECT MAX(game_date) as latest, MIN(game_date) as earliest
        FROM milb_plate_appearances
        WHERE season = 2025
    """)
    latest, earliest = cur.fetchone()

    print(f"\n=== 2025 GAME DATE RANGE ===")
    print(f"Earliest game: {earliest}")
    print(f"Latest game:   {latest}")

    # Check coverage by organization
    cur.execute("""
        SELECT p.organization, COUNT(DISTINCT p.mlb_player_id) as total,
               COUNT(DISTINCT mpa.mlb_player_id) as with_pbp,
               COUNT(DISTINCT mbp.mlb_batter_id) as with_pitch
        FROM prospects p
        LEFT JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id AND mpa.season = 2025
        LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id AND mbp.season = 2025
        WHERE p.mlb_player_id IS NOT NULL
        GROUP BY p.organization
        ORDER BY p.organization
    """)

    print(f"\n=== COVERAGE BY ORGANIZATION (2025) ===")
    print(f"{'Team':4} | {'Total':5} | {'w/PBP':5} | {'w/Pitch':7} | {'%PBP':5} | {'%Pitch':6}")
    print("-" * 45)
    for org, total, with_pbp, with_pitch in cur.fetchall():
        pbp_pct = (with_pbp or 0) / total * 100 if total > 0 else 0
        pitch_pct = (with_pitch or 0) / total * 100 if total > 0 else 0
        print(f"{org:4} | {total:5} | {with_pbp or 0:5} | {with_pitch or 0:7} | {pbp_pct:5.1f} | {pitch_pct:6.1f}")

    conn.close()

if __name__ == "__main__":
    verify_collection_status()