import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("\n" + "="*70)
print("COLLECTION STATUS REPORT")
print(f"Generated: {datetime.now()}")
print("="*70)

# Overall stats
cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2025")
total_2025 = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2024")
total_2024 = cur.fetchone()[0]

cur.execute("SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season IN (2024, 2025)")
unique_batters = cur.fetchone()[0]

print(f"\nOVERALL PITCH DATA:")
print(f"  2025 pitches: {total_2025:,}")
print(f"  2024 pitches: {total_2024:,}")
print(f"  Unique batters: {unique_batters:,}")

# Most recent inserts
cur.execute("""
    SELECT MAX(created_at), COUNT(*)
    FROM milb_batter_pitches
    WHERE created_at > NOW() - INTERVAL '24 hours'
""")
row = cur.fetchone()
print(f"\nRECENT ACTIVITY:")
print(f"  Last insert: {row[0]}")
print(f"  Records in last 24h: {row[1]:,}")

# Prospects needing 2025 data
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
    LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
        AND mbp.season = 2025
    WHERE mpa.season = 2025
        AND p.mlb_player_id IS NOT NULL
        AND mbp.id IS NULL
""")
need_2025 = cur.fetchone()[0]

# Prospects needing 2024 data
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
    LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
        AND mbp.season = 2024
    WHERE mpa.season = 2024
        AND p.mlb_player_id IS NOT NULL
        AND mbp.id IS NULL
""")
need_2024 = cur.fetchone()[0]

print(f"\nPROSPECTS NEEDING DATA:")
print(f"  Need 2025 pitch data: {need_2025:,}")
print(f"  Need 2024 pitch data: {need_2024:,}")

# Top prospects needing 2025 data
cur.execute("""
    SELECT p.mlb_player_id, p.name, p.organization,
           COUNT(DISTINCT mpa.id) as pa_count
    FROM prospects p
    JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
    LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
        AND mbp.season = 2025
    WHERE mpa.season = 2025
        AND p.mlb_player_id IS NOT NULL
        AND mbp.id IS NULL
    GROUP BY p.mlb_player_id, p.name, p.organization
    HAVING COUNT(DISTINCT mpa.id) > 0
    ORDER BY COUNT(DISTINCT mpa.id) DESC
    LIMIT 15
""")

print(f"\nTOP 15 PROSPECTS NEEDING 2025 PITCH DATA:")
for i, row in enumerate(cur.fetchall(), 1):
    print(f"  {i:2d}. {row[1]:30s} ({row[2]:15s}) - {row[3]:3d} PAs - ID: {row[0]}")

# Prospects with data
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
    WHERE mbp.season = 2025
""")
have_2025 = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
    WHERE mbp.season = 2024
""")
have_2024 = cur.fetchone()[0]

print(f"\nPROSPECTS WITH DATA:")
print(f"  Have 2025 pitch data: {have_2025:,}")
print(f"  Have 2024 pitch data: {have_2024:,}")

print("\n" + "="*70)

cur.close()
conn.close()
