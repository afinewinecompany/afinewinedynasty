import psycopg2

DB_CONFIG = {
    'host': 'nozomi.proxy.rlwy.net',
    'port': 39235,
    'database': 'railway',
    'user': 'postgres',
    'password': 'BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp'
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

print("\n" + "="*80)
print("MILB PITCH DATA COLLECTION STATUS REPORT")
print("="*80)

# Check batter pitches
print("\n### BATTER PITCHES ###")
cur.execute("SELECT COUNT(*), MIN(season), MAX(season) FROM milb_batter_pitches")
total, min_season, max_season = cur.fetchone()
print(f"Total Records: {total:,}")
print(f"Season Range: {min_season} - {max_season}")

print("\nBy Season:")
cur.execute("SELECT season, COUNT(*) FROM milb_batter_pitches GROUP BY season ORDER BY season")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} pitches")

# Check pitcher pitches
print("\n### PITCHER PITCHES ###")
cur.execute("SELECT COUNT(*), MIN(season), MAX(season) FROM milb_pitcher_pitches")
total, min_season, max_season = cur.fetchone()
print(f"Total Records: {total:,}")
print(f"Season Range: {min_season} - {max_season}")

print("\nBy Season:")
cur.execute("SELECT season, COUNT(*) FROM milb_pitcher_pitches GROUP BY season ORDER BY season")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} pitches")

# Check plate appearances for comparison
print("\n### PLATE APPEARANCES (for comparison) ###")
cur.execute("SELECT COUNT(*), MIN(season), MAX(season) FROM milb_plate_appearances")
total, min_season, max_season = cur.fetchone()
print(f"Total Records: {total:,}")
print(f"Season Range: {min_season} - {max_season}")

print("\nBy Season:")
cur.execute("SELECT season, COUNT(*) FROM milb_plate_appearances GROUP BY season ORDER BY season")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} PAs")

# Check pitcher appearances for comparison
print("\n### PITCHER APPEARANCES (for comparison) ###")
cur.execute("SELECT COUNT(*), MIN(season), MAX(season) FROM milb_pitcher_appearances")
total, min_season, max_season = cur.fetchone()
print(f"Total Records: {total:,}")
print(f"Season Range: {min_season} - {max_season}")

print("\nBy Season:")
cur.execute("SELECT season, COUNT(*) FROM milb_pitcher_appearances GROUP BY season ORDER BY season")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} appearances")

# Check unique prospects with pitch data
print("\n### UNIQUE PROSPECTS WITH DATA ###")
cur.execute("SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches")
print(f"Batters with pitch data: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(DISTINCT mlb_pitcher_id) FROM milb_pitcher_pitches")
print(f"Pitchers with pitch data: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(DISTINCT mlb_player_id) FROM milb_plate_appearances")
print(f"Batters with PA data: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(DISTINCT mlb_player_id) FROM milb_pitcher_appearances")
print(f"Pitchers with appearance data: {cur.fetchone()[0]}")

# Check for any error patterns in the conflict keys
print("\n### CONFLICT KEY ANALYSIS ###")
cur.execute("""
    SELECT season, COUNT(*) as games_with_data, COUNT(DISTINCT mlb_batter_id) as unique_batters
    FROM milb_batter_pitches
    GROUP BY season
    ORDER BY season
""")
print("\nBatter Pitches - Games vs Unique Players:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} games, {row[2]} unique batters")

cur.execute("""
    SELECT season, COUNT(*) as games_with_data, COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers
    FROM milb_pitcher_pitches
    GROUP BY season
    ORDER BY season
""")
print("\nPitcher Pitches - Games vs Unique Players:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} games, {row[2]} unique pitchers")

print("\n" + "="*80)
print("REPORT COMPLETE")
print("="*80 + "\n")

conn.close()
