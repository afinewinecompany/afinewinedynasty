"""Check the actual schema of our pitch tables"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("MILB_BATTER_PITCHES TABLE SCHEMA")
print("="*80)

cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'milb_batter_pitches'
    ORDER BY ordinal_position
""")

columns = cursor.fetchall()
for col, dtype in columns:
    print(f"  {col:30s} {dtype}")

print("\n" + "="*80)
print("MILB_PITCHER_PITCHES TABLE SCHEMA")
print("="*80)

cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'milb_pitcher_pitches'
    ORDER BY ordinal_position
""")

columns = cursor.fetchall()
for col, dtype in columns:
    print(f"  {col:30s} {dtype}")

# Check sample data
print("\n" + "="*80)
print("SAMPLE BATTER PITCH DATA")
print("="*80)

cursor.execute("""
    SELECT *
    FROM milb_batter_pitches
    WHERE mlb_batter_id = 805811  -- Bryce Eldridge
    LIMIT 2
""")

cols = [desc[0] for desc in cursor.description]
print("\nColumns:", cols)
rows = cursor.fetchall()
for row in rows:
    print("\nSample row:")
    for col, val in zip(cols, row):
        if val is not None:
            print(f"  {col}: {val}")

conn.close()