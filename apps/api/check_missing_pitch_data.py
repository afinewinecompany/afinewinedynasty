"""Check which prospects are still missing pitch data"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("PITCH DATA COLLECTION STATUS")
print("="*80)

# Current totals
cursor.execute("""
    SELECT
        COUNT(*) as total_pitches,
        COUNT(DISTINCT mlb_batter_id) as unique_batters
    FROM milb_batter_pitches
    WHERE season = 2025
""")
batter_pitches, unique_batters = cursor.fetchone()

cursor.execute("""
    SELECT
        COUNT(*) as total_pitches,
        COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
pitcher_pitches, unique_pitchers = cursor.fetchone()

print(f"\nCurrent Database Totals:")
print(f"  Batter Pitches: {batter_pitches:,} from {unique_batters:,} batters")
print(f"  Pitcher Pitches: {pitcher_pitches:,} from {unique_pitchers:,} pitchers")
print(f"  TOTAL: {batter_pitches + pitcher_pitches:,}")

# Prospects with game logs
cursor.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_game_logs
    WHERE season = 2025
""")
prospects_with_logs = cursor.fetchone()[0]
print(f"\nProspects with 2025 game logs: {prospects_with_logs:,}")

# Check key prospects
print("\n" + "="*80)
print("KEY PROSPECTS STATUS")
print("="*80)

key_prospects = [
    'Bryce Eldridge',
    'Konnor Griffin',
    'Trey Lipscomb',
    'Roman Anthony',
    'Kristian Campbell',
    'Christian Moore',
    'Jakob Marsee',
    'Jac Caglianone'
]

for name in key_prospects:
    cursor.execute("""
        SELECT
            p.name,
            p.mlb_player_id,
            p.position,
            (SELECT COUNT(DISTINCT game_pk)
             FROM milb_game_logs gl
             WHERE gl.mlb_player_id = p.mlb_player_id::integer
             AND gl.season = 2025) as game_logs,
            (SELECT COUNT(*)
             FROM milb_batter_pitches bp
             WHERE bp.mlb_batter_id = p.mlb_player_id::integer
             AND bp.season = 2025) as batter_pitches,
            (SELECT COUNT(*)
             FROM milb_pitcher_pitches pp
             WHERE pp.mlb_pitcher_id = p.mlb_player_id::integer
             AND pp.season = 2025) as pitcher_pitches
        FROM prospects p
        WHERE p.name = %s
    """, (name,))

    row = cursor.fetchone()
    if row:
        name, mlb_id, position, games, b_pitches, p_pitches = row
        pitches = b_pitches if position not in ('SP', 'RP') else p_pitches
        status = "✓" if pitches > 0 else "✗ MISSING"
        print(f"  {name:25s} | {position:3s} | {games:3d} games | {pitches:6d} pitches {status}")

# Missing batter pitch data (top 30)
print("\n" + "="*80)
print("TOP 30 BATTERS MISSING PITCH DATA (with game logs)")
print("="*80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        COUNT(DISTINCT gl.game_pk) as game_logs
    FROM prospects p
    INNER JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    LEFT JOIN milb_batter_pitches bp
        ON p.mlb_player_id::integer = bp.mlb_batter_id
        AND bp.season = 2025
    WHERE p.position NOT IN ('SP', 'RP')
        AND bp.mlb_batter_id IS NULL
    GROUP BY p.name, p.mlb_player_id, p.position
    ORDER BY game_logs DESC
    LIMIT 30
""")

missing = cursor.fetchall()
if missing:
    print(f"\n{len(missing)} batters still need pitch data collection:\n")
    for name, mlb_id, position, games in missing:
        print(f"  {name:30s} ({mlb_id}) - {position:3s}: {games:3d} games")
    print(f"\n⚠️  Collection still in progress...")
else:
    print("\n✓ All batters with game logs have pitch data!")

# Missing pitcher pitch data
print("\n" + "="*80)
print("PITCHERS MISSING PITCH DATA (with game logs)")
print("="*80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        COUNT(DISTINCT gl.game_pk) as game_logs
    FROM prospects p
    INNER JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    LEFT JOIN milb_pitcher_pitches pp
        ON p.mlb_player_id::integer = pp.mlb_pitcher_id
        AND pp.season = 2025
    WHERE p.position IN ('SP', 'RP')
        AND pp.mlb_pitcher_id IS NULL
    GROUP BY p.name, p.mlb_player_id, p.position
    ORDER BY game_logs DESC
    LIMIT 30
""")

missing_pitchers = cursor.fetchall()
if missing_pitchers:
    print(f"\n{len(missing_pitchers)} pitchers still need pitch data collection:\n")
    for name, mlb_id, position, games in missing_pitchers:
        print(f"  {name:30s} ({mlb_id}) - {position:3s}: {games:3d} games")
else:
    print("\n✓ All pitchers with game logs have pitch data!")

# Summary
print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if not missing and not missing_pitchers:
    print("\n✓ DATA COLLECTION COMPLETE!")
    print("✓ All prospects with game logs have pitch data")
    print("✓ READY TO UPDATE RANKINGS\n")
else:
    print(f"\n⚠️  Collection still in progress")
    print(f"   - {len(missing)} batters remaining")
    print(f"   - {len(missing_pitchers)} pitchers remaining")
    print(f"\n   Wait for collection to complete before updating rankings\n")

conn.close()
