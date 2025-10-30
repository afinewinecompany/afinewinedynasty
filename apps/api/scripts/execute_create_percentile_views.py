"""Execute SQL to create percentile materialized views"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("Creating percentile materialized views...")

# Read SQL file
with open('create_percentile_views.sql', 'r') as f:
    sql_commands = f.read()

# Execute the SQL
try:
    cursor.execute(sql_commands)
    conn.commit()
    print("Materialized views created successfully!")

    # Check the data
    cursor.execute("""
        SELECT level, season, num_hitters,
               contact_percentiles[3] as median_contact,
               whiff_percentiles[3] as median_whiff,
               chase_percentiles[3] as median_chase
        FROM mv_hitter_percentiles_by_level
        ORDER BY level
    """)

    print("\nHitter Percentile Data:")
    print("Level | Hitters | Median Contact | Median Whiff | Median Chase")
    print("-" * 65)
    for row in cursor.fetchall():
        level, season, num, contact, whiff, chase = row
        print(f"{level:8s} | {num:7d} | {contact or 0:13.1f} | {whiff or 0:11.1f} | {chase or 0:11.1f}")

    # Check pitcher data
    cursor.execute("""
        SELECT level, season, num_pitchers,
               whiff_percentiles[3] as median_whiff,
               zone_percentiles[3] as median_zone
        FROM mv_pitcher_percentiles_by_level
        ORDER BY level
    """)

    print("\nPitcher Percentile Data:")
    print("Level | Pitchers | Median Whiff | Median Zone")
    print("-" * 50)
    for row in cursor.fetchall():
        level, season, num, whiff, zone = row
        print(f"{level:8s} | {num:8d} | {whiff or 0:11.1f} | {zone or 0:10.1f}")

except Exception as e:
    print(f"Error: {e}")
    conn.rollback()

conn.close()