"""
Check pitch data availability for Jesus Made and test enhanced metrics
"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

# Check Jesus Made's data
cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        COUNT(DISTINCT bp.game_pk) as games_with_pitches,
        COUNT(*) as total_pitches,
        MIN(bp.game_date) as first_date,
        MAX(bp.game_date) as last_date,
        array_agg(DISTINCT bp.level) as levels
    FROM prospects p
    LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
        AND bp.season = 2025
    WHERE p.name ILIKE '%made%' OR p.name ILIKE '%jesus%'
    GROUP BY p.name, p.mlb_player_id
    ORDER BY p.name
""")

print("=" * 80)
print("PITCH DATA FOR JESUS MADE AND SIMILAR NAMES")
print("=" * 80)

results = cursor.fetchall()
for name, mlb_id, games, pitches, first_date, last_date, levels in results:
    print(f"\n{name} (ID: {mlb_id}):")
    if pitches and pitches > 0:
        print(f"  Games: {games}")
        print(f"  Pitches: {pitches}")
        print(f"  Date Range: {first_date} to {last_date}")
        print(f"  Levels: {levels}")
    else:
        print("  No pitch data for 2025")

# Check other key prospects
print("\n" + "=" * 80)
print("OTHER KEY PROSPECTS WITH PITCH DATA")
print("=" * 80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        COUNT(*) as total_pitches,
        array_agg(DISTINCT bp.level) as levels
    FROM prospects p
    INNER JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
    WHERE bp.season = 2025
        AND p.name IN ('Bryce Eldridge', 'Konnor Griffin', 'Roman Anthony', 'Kristian Campbell')
    GROUP BY p.name, p.mlb_player_id
    ORDER BY COUNT(*) DESC
""")

results = cursor.fetchall()
for name, mlb_id, pitches, levels in results:
    print(f"\n{name} (ID: {mlb_id}):")
    print(f"  Pitches: {pitches}")
    print(f"  Levels: {levels}")

# Find prospects with most pitch data to test with
print("\n" + "=" * 80)
print("TOP PROSPECTS WITH MOST PITCH DATA (FOR TESTING)")
print("=" * 80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        COUNT(*) as total_pitches,
        array_agg(DISTINCT bp.level ORDER BY bp.level) as levels,
        COUNT(DISTINCT bp.game_pk) as games
    FROM prospects p
    INNER JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
    WHERE bp.season = 2025
    GROUP BY p.name, p.mlb_player_id, p.position
    HAVING COUNT(*) >= 1000
    ORDER BY COUNT(*) DESC
    LIMIT 10
""")

results = cursor.fetchall()
for name, mlb_id, position, pitches, levels, games in results:
    print(f"\n{name} ({position}) - ID: {mlb_id}:")
    print(f"  Pitches: {pitches:,}")
    print(f"  Games: {games}")
    print(f"  Levels: {', '.join(levels) if levels else 'N/A'}")

conn.close()