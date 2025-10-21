import psycopg2

conn = psycopg2.connect(
    host="nozomi.proxy.rlwy.net",
    port=39235,
    database="railway",
    user="postgres",
    password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp"
)

cur = conn.cursor()

print("\n" + "="*80)
print("ANALYZING THE 547 'MISSING' BATTERS")
print("="*80)

# Check position breakdown of "missing" batters
cur.execute("""
    SELECT p.position, COUNT(*) as count
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position != 'P'
    AND NOT EXISTS (
        SELECT 1 FROM milb_plate_appearances mpa
        WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
    )
    GROUP BY p.position
    ORDER BY count DESC
""")

print("\nPOSITION BREAKDOWN:")
positions = cur.fetchall()
for position, count in positions:
    print(f"  {position}: {count}")

# Check if these are actually pitchers
cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position != 'P'
    AND p.position IN ('SP', 'RP', 'RHP', 'LHP', 'PITCHER')
    AND NOT EXISTS (
        SELECT 1 FROM milb_plate_appearances mpa
        WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
    )
""")
pitcher_positions = cur.fetchone()[0]
print(f"\n*** PITCHERS in 'missing batters': {pitcher_positions}")

# Get actual non-pitcher positions
cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
    AND NOT EXISTS (
        SELECT 1 FROM milb_plate_appearances mpa
        WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
    )
""")
true_batters = cur.fetchone()[0]
print(f"TRUE BATTERS missing data: {true_batters}")

# Check how many prospects total
cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
""")
total_batters = cur.fetchone()[0]
print(f"TOTAL NON-PITCHER PROSPECTS: {total_batters}")

# Check how many have data
cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_plate_appearances
    WHERE season = 2025
""")
batters_with_data = cur.fetchone()[0]
print(f"BATTERS WITH 2025 DATA: {batters_with_data}")

print(f"\nCOVERAGE: {batters_with_data}/{total_batters} = {100*batters_with_data/total_batters:.1f}%")

# Sample some true batters
print("\n" + "="*80)
print("SAMPLE OF 20 TRUE BATTERS WITH NO DATA:")
print("="*80)
cur.execute("""
    SELECT p.mlb_player_id, p.name, p.position, p.organization
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
    AND NOT EXISTS (
        SELECT 1 FROM milb_plate_appearances mpa
        WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
    )
    ORDER BY p.name
    LIMIT 20
""")

for player_id, name, position, org in cur.fetchall():
    print(f"  {name} ({position}, {org}) - ID: {player_id}")

cur.close()
conn.close()
