"""Check milb_game_logs schema"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

# Get table schema
cursor.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'milb_game_logs'
    ORDER BY ordinal_position
""")

print("="*80)
print("milb_game_logs TABLE SCHEMA")
print("="*80)

for row in cursor.fetchall():
    print(f"{row[0]:40} {row[1]:20} nullable={row[2]}")

# Check if level column exists
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'milb_game_logs'
      AND column_name = 'level'
""")

level_exists = cursor.fetchone()

print("\n" + "="*80)
if level_exists:
    print("✓ 'level' column EXISTS in milb_game_logs")

    # Check current level values
    cursor.execute("""
        SELECT level, COUNT(*) as count
        FROM milb_game_logs
        WHERE season = 2025
        GROUP BY level
        ORDER BY count DESC
    """)

    print("\nCurrent level values in 2025 season:")
    for row in cursor.fetchall():
        level = row[0] if row[0] else 'NULL'
        count = row[1]
        print(f"  {level}: {count:,} games")
else:
    print("✗ 'level' column DOES NOT EXIST in milb_game_logs")
    print("This explains why we can't filter/attribute games by level!")

conn.close()
