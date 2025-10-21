import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("\n" + "="*70)
print("PITCHER PITCH DATA COLLECTION STATUS")
print(f"Generated: {datetime.now()}")
print("="*70)

# Check if table exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'milb_pitcher_pitches'
    )
""")
table_exists = cur.fetchone()[0]

if not table_exists:
    print("\nWARNING: milb_pitcher_pitches table does not exist!")
    print("Pitcher pitch collection has not been set up yet.")
else:
    # Overall stats
    cur.execute("SELECT COUNT(*) FROM milb_pitcher_pitches")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_pitcher_pitches WHERE season = 2025")
    total_2025 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_pitcher_pitches WHERE season = 2024")
    total_2024 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_pitcher_id) FROM milb_pitcher_pitches")
    unique_pitchers = cur.fetchone()[0]

    print(f"\nOVERALL PITCHER PITCH DATA:")
    print(f"  Total pitches: {total:,}")
    print(f"  2025 pitches: {total_2025:,}")
    print(f"  2024 pitches: {total_2024:,}")
    print(f"  Unique pitchers: {unique_pitchers:,}")

    # Recent activity
    cur.execute("""
        SELECT MAX(created_at), COUNT(*)
        FROM milb_pitcher_pitches
        WHERE created_at > NOW() - INTERVAL '24 hours'
    """)
    row = cur.fetchone()

    print(f"\nRECENT ACTIVITY:")
    print(f"  Last insert: {row[0]}")
    print(f"  Records in last 24h: {row[1]:,}")

    # Check recent hour
    cur.execute("""
        SELECT COUNT(*)
        FROM milb_pitcher_pitches
        WHERE created_at > NOW() - INTERVAL '1 hour'
    """)
    recent_hour = cur.fetchone()[0]
    print(f"  Records in last hour: {recent_hour:,}")

    # Most recent records
    cur.execute("""
        SELECT mlb_pitcher_id, game_date, season, COUNT(*) as pitch_count
        FROM milb_pitcher_pitches
        WHERE created_at > NOW() - INTERVAL '30 minutes'
        GROUP BY mlb_pitcher_id, game_date, season
        ORDER BY MAX(created_at) DESC
        LIMIT 5
    """)

    recent_data = cur.fetchall()
    if recent_data:
        print(f"\nMOST RECENT PITCHER DATA (last 30 min):")
        for row in recent_data:
            print(f"  Pitcher {row[0]} - {row[1]} ({row[2]}) - {row[3]} pitches")

print("\n" + "="*70)

cur.close()
conn.close()
