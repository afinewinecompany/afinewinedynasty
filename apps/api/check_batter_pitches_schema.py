import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Get column information
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'milb_batter_pitches'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()

print("milb_batter_pitches table schema:")
print("-" * 50)
for col in columns:
    print(f"{col[0]:<25} {col[1]:<20} {col[2]}")

# Check for unique constraints
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'milb_batter_pitches'::regclass
    AND contype IN ('u', 'p')
""")

constraints = cur.fetchall()
print("\nConstraints:")
for c in constraints:
    print(f"  {c[0]}: {c[1]}")

conn.close()