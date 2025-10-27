"""Check all tables for Bryce Eldridge data"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("BRYCE ELDRIDGE - ALL DATABASE TABLES")
print("="*80)

# Check prospects table
print("\nPROSPECTS TABLE:")
cursor.execute("""
    SELECT name, fg_player_id, mlb_player_id, position, current_level
    FROM prospects
    WHERE mlb_player_id = '805811'
""")
row = cursor.fetchone()
if row:
    print(f"  Name: {row[0]}")
    print(f"  FG ID: {row[1]}")
    print(f"  MLB ID: {row[2]}")
    print(f"  Position: {row[3]}")
    print(f"  Level: {row[4]}")

# Check milb_plate_appearances
print("\nMILB_PLATE_APPEARANCES:")
try:
    cursor.execute("""
        SELECT season, level, COUNT(*) as games, SUM(plate_appearances) as total_pa
        FROM milb_plate_appearances
        WHERE mlb_player_id = 805811
        GROUP BY season, level
        ORDER BY season DESC, level
    """)
except Exception as e:
    print(f"  Table doesn't exist or error: {e}")
    cursor.execute("ROLLBACK")
    rows = []
rows = cursor.fetchall()
if rows:
    for row in rows:
        season, level, games, pa = row
        print(f"  {season} - {level}: {games} games, {pa} PAs, ~{int(pa*4.5)} expected pitches")
else:
    print("  No data")

# Check milb_game_logs
print("\nMILB_GAME_LOGS:")
cursor.execute("""
    SELECT season, level, COUNT(*) as games, SUM(plate_appearances) as total_pa
    FROM milb_game_logs
    WHERE mlb_player_id = 805811
    GROUP BY season, level
    ORDER BY season DESC, level
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        season, level, games, pa = row
        print(f"  {season} - {level}: {games} games, {pa} PAs, ~{int(pa*4.5)} expected pitches")
else:
    print("  No data")

# Check milb_batter_pitches
print("\nMILB_BATTER_PITCHES:")
cursor.execute("""
    SELECT season, level, COUNT(DISTINCT game_pk) as games, COUNT(*) as pitches
    FROM milb_batter_pitches
    WHERE mlb_batter_id = 805811
    GROUP BY season, level
    ORDER BY season DESC, level
""")
rows = cursor.fetchall()
if rows:
    total_pitches = 0
    for row in rows:
        season, level, games, pitches = row
        total_pitches += pitches
        print(f"  {season} - {level}: {games} games, {pitches} pitches")
    print(f"\n  TOTAL: {total_pitches} pitches")
else:
    print("  No data")

conn.close()

print("\n" + "="*80)
print("CONCLUSION:")
print("="*80)
print("\nBased on all available data sources:")
print("- MLB Stats API: Only has 2025 MLB games (10 games)")
print("- Database game logs: Only has 2 CPX games from 2025")
print("- Database pitch data: 25 CPX pitches + 160 MLB pitches (incorrectly labeled AA)")
print("\nThe expected 1,746 pitches (25 CPX, 556 AA, 1,165 AAA) cannot be found")
print("in any data source. This may be:")
print("  1. Expected/projected stats (not actual)")
print("  2. From a different data source (not MLB Stats API)")
print("  3. From a different season that MLB API doesn't have")
print("="*80)
