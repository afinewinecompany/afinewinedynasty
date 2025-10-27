"""Check current level values in milb_game_logs"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("CURRENT LEVEL VALUES IN milb_game_logs (2025 season)")
print("="*80)

cursor.execute("""
    SELECT level, COUNT(*) as count
    FROM milb_game_logs
    WHERE season = 2025
    GROUP BY level
    ORDER BY count DESC
""")

total = 0
for row in cursor.fetchall():
    level = row[0] if row[0] else 'NULL'
    count = row[1]
    total += count
    print(f"{level:20} {count:10,} games")

print(f"{'TOTAL':20} {total:10,} games")

# Check Bryce Eldridge specifically
print("\n" + "="*80)
print("BRYCE ELDRIDGE (805811) GAME LOGS")
print("="*80)

cursor.execute("""
    SELECT season, level, COUNT(*) as games,
           MIN(game_date) as first_date,
           MAX(game_date) as last_date
    FROM milb_game_logs
    WHERE mlb_player_id = 805811
    GROUP BY season, level
    ORDER BY season, level
""")

results = cursor.fetchall()
if results:
    for row in results:
        season, level, games, first, last = row
        print(f"{season} {level}: {games} games ({first} to {last})")
else:
    print("No game logs found")

conn.close()
