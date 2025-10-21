import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("\n" + "="*70)
print("PITCHER COLLECTION NEEDS ANALYSIS")
print(f"Generated: {datetime.now()}")
print("="*70)

# Get pitcher prospects
cur.execute("""
    SELECT COUNT(*)
    FROM prospects
    WHERE position = 'P' AND mlb_player_id IS NOT NULL
""")
total_pitcher_prospects = cur.fetchone()[0]

print(f"\nTOTAL PITCHER PROSPECTS: {total_pitcher_prospects:,}")

# Pitchers with 2025 pitch data
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
    WHERE p.position = 'P' AND mpp.season = 2025
""")
have_2025 = cur.fetchone()[0]

# Pitchers with 2024 pitch data
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
    WHERE p.position = 'P' AND mpp.season = 2024
""")
have_2024 = cur.fetchone()[0]

print(f"\nPITCHERS WITH PITCH DATA:")
print(f"  Have 2025 data: {have_2025:,}")
print(f"  Have 2024 data: {have_2024:,}")

# Pitchers needing 2025 data (who have plate appearances as pitchers)
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    LEFT JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
        AND mpp.season = 2025
    WHERE p.position = 'P'
        AND p.mlb_player_id IS NOT NULL
        AND mpp.id IS NULL
""")
need_2025 = cur.fetchone()[0]

# Pitchers needing 2024 data
cur.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    LEFT JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
        AND mpp.season = 2024
    WHERE p.position = 'P'
        AND p.mlb_player_id IS NOT NULL
        AND mpp.id IS NULL
""")
need_2024 = cur.fetchone()[0]

print(f"\nPITCHERS NEEDING PITCH DATA:")
print(f"  Need 2025 data: {need_2025:,}")
print(f"  Need 2024 data: {need_2024:,}")

# Top pitchers needing 2025 data
cur.execute("""
    SELECT p.mlb_player_id, p.name, p.organization
    FROM prospects p
    LEFT JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
        AND mpp.season = 2025
    WHERE p.position = 'P'
        AND p.mlb_player_id IS NOT NULL
        AND mpp.id IS NULL
    ORDER BY p.name
    LIMIT 20
""")

print(f"\nTOP 20 PITCHERS NEEDING 2025 PITCH DATA:")
for i, row in enumerate(cur.fetchall(), 1):
    print(f"  {i:2d}. {row[1]:30s} ({row[2]:15s}) - ID: {row[0]}")

# Check if there's a dedicated pitcher pitch collection table or if it's combined
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_name LIKE '%pitcher%pitch%'
       OR table_name LIKE '%pitch%pitcher%'
""")
pitch_tables = cur.fetchall()

print(f"\nPITCH-RELATED TABLES:")
for table in pitch_tables:
    print(f"  - {table[0]}")

print("\n" + "="*70)

cur.close()
conn.close()
