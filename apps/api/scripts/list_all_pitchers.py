import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("\n" + "="*80)
print("ALL PITCHER PROSPECTS IN DATABASE")
print("="*80)

# Check all position values
cur.execute("""
    SELECT DISTINCT position, COUNT(*)
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
    GROUP BY position
    ORDER BY position
""")
print("\nAll positions in prospects table:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} prospects")

# Get all pitchers (position = 'P')
cur.execute("""
    SELECT mlb_player_id, name, organization, position
    FROM prospects
    WHERE position = 'P' AND mlb_player_id IS NOT NULL
    ORDER BY name
""")

pitchers = cur.fetchall()
print(f"\n\nTotal Pitcher Prospects (position='P'): {len(pitchers)}")
print("\n" + "="*80)

for i, p in enumerate(pitchers, 1):
    print(f"{i:3d}. {p[1]:35s} ({p[2]:15s}) - ID: {p[0]}")

# Check if any might be RHP/LHP
cur.execute("""
    SELECT mlb_player_id, name, organization, position
    FROM prospects
    WHERE (position LIKE '%P' OR position LIKE 'P%')
        AND mlb_player_id IS NOT NULL
    ORDER BY position, name
""")

all_pitcher_types = cur.fetchall()
if len(all_pitcher_types) > len(pitchers):
    print(f"\n\nFound additional pitcher prospects with different position codes:")
    print(f"Total including RHP/LHP/etc: {len(all_pitcher_types)}")
    print("\n" + "="*80)
    for i, p in enumerate(all_pitcher_types, 1):
        print(f"{i:3d}. {p[1]:35s} ({p[2]:15s}) - Pos: {p[3]:5s} - ID: {p[0]}")

print("\n" + "="*80)

cur.close()
conn.close()
