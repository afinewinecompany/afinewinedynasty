import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print(f"\nQuick Status Check - {datetime.now()}")
print("="*60)

# Last 5 minutes of batter pitches
cur.execute("""
    SELECT COUNT(*), MAX(created_at)
    FROM milb_batter_pitches
    WHERE created_at > NOW() - INTERVAL '5 minutes'
""")
row = cur.fetchone()
print(f"\nBatter Pitches (last 5 min): {row[0]:,}")
print(f"Most recent: {row[1]}")

# Last 5 minutes of pitcher pitches
cur.execute("""
    SELECT COUNT(*), MAX(created_at)
    FROM milb_pitcher_pitches
    WHERE created_at > NOW() - INTERVAL '5 minutes'
""")
row = cur.fetchone()
print(f"\nPitcher Pitches (last 5 min): {row[0]:,}")
print(f"Most recent: {row[1]}")

print("\n" + "="*60)

cur.close()
conn.close()
