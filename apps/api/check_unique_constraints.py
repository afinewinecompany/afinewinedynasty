"""Check unique constraints on milb_game_logs"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

# Check constraints
cursor.execute("""
    SELECT conname, contype, pg_get_constraintdef(oid) as definition
    FROM pg_constraint
    WHERE conrelid = 'milb_game_logs'::regclass
""")

print("="*80)
print("CONSTRAINTS ON milb_game_logs")
print("="*80)

for row in cursor.fetchall():
    name, type_code, definition = row
    constraint_type = {'p': 'PRIMARY KEY', 'u': 'UNIQUE', 'f': 'FOREIGN KEY', 'c': 'CHECK'}.get(type_code, type_code)
    print(f"\n{name} ({constraint_type}):")
    print(f"  {definition}")

conn.close()
