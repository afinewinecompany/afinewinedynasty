"""Check final collection status and verify specific prospects"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("FINAL COLLECTION STATUS - 2025 SEASON")
print("="*80)

# Overall game logs
cursor.execute("""
    SELECT
        COUNT(*) as total_games,
        COUNT(DISTINCT mlb_player_id) as unique_players
    FROM milb_game_logs
    WHERE season = 2025
""")
total_games, unique_players = cursor.fetchone()
print(f"\nGame Logs: {total_games:,} games from {unique_players:,} players")

# By level
cursor.execute("""
    SELECT level, COUNT(*) as games
    FROM milb_game_logs
    WHERE season = 2025
    GROUP BY level
    ORDER BY games DESC
""")
print("\nBy Level:")
for level, count in cursor.fetchall():
    print(f"  {level}: {count:,}")

# Batter pitches
cursor.execute("""
    SELECT
        COUNT(*) as total_pitches,
        COUNT(DISTINCT mlb_batter_id) as unique_batters
    FROM milb_batter_pitches
    WHERE season = 2025
""")
total_batter_pitches, unique_batters = cursor.fetchone()
print(f"\nBatter Pitches: {total_batter_pitches:,} from {unique_batters:,} batters")

# Pitcher pitches
cursor.execute("""
    SELECT
        COUNT(*) as total_pitches,
        COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
total_pitcher_pitches, unique_pitchers = cursor.fetchone()
print(f"Pitcher Pitches: {total_pitcher_pitches:,} from {unique_pitchers:,} pitchers")

print(f"\nTOTAL PITCHES: {total_batter_pitches + total_pitcher_pitches:,}")

# Check specific prospects
print("\n" + "="*80)
print("SPECIFIC PROSPECT VERIFICATION")
print("="*80)

# Bryce Eldridge
print("\nBryce Eldridge:")
cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        COUNT(DISTINCT gl.game_pk) as game_logs,
        (SELECT COUNT(*) FROM milb_batter_pitches bp
         WHERE bp.mlb_batter_id = p.mlb_player_id::integer
         AND bp.season = 2025) as batter_pitches
    FROM prospects p
    LEFT JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    WHERE p.name = 'Bryce Eldridge'
    GROUP BY p.name, p.mlb_player_id
""")
row = cursor.fetchone()
if row:
    name, mlb_id, games, pitches = row
    print(f"  MLB ID: {mlb_id}")
    print(f"  Game Logs: {games}")
    print(f"  Batter Pitches: {pitches}")
    print(f"  Expected: ~1,746 pitches")

    # By level
    cursor.execute("""
        SELECT level, COUNT(*) as games
        FROM milb_game_logs
        WHERE mlb_player_id = %s AND season = 2025
        GROUP BY level
        ORDER BY level
    """, (mlb_id,))
    print("  By Level:")
    for level, count in cursor.fetchall():
        print(f"    {level}: {count} games")

# Konnor Griffin
print("\nKonnor Griffin:")
cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        COUNT(DISTINCT gl.game_pk) as game_logs,
        (SELECT COUNT(*) FROM milb_batter_pitches bp
         WHERE bp.mlb_batter_id = p.mlb_player_id::integer
         AND bp.season = 2025) as batter_pitches
    FROM prospects p
    LEFT JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    WHERE p.name = 'Konnor Griffin'
    GROUP BY p.name, p.mlb_player_id
""")
row = cursor.fetchone()
if row:
    name, mlb_id, games, pitches = row
    print(f"  MLB ID: {mlb_id}")
    print(f"  Game Logs: {games}")
    print(f"  Batter Pitches: {pitches}")
    print(f"  Expected: ~2,080 pitches")

    # By level
    cursor.execute("""
        SELECT level, COUNT(*) as games
        FROM milb_game_logs
        WHERE mlb_player_id = %s AND season = 2025
        GROUP BY level
        ORDER BY level
    """, (mlb_id,))
    print("  By Level:")
    for level, count in cursor.fetchall():
        print(f"    {level}: {count} games")

# Bubba Chandler (random pitcher check)
print("\nBubba Chandler (Pitcher):")
cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        COUNT(DISTINCT gl.game_pk) as game_logs,
        (SELECT COUNT(*) FROM milb_pitcher_pitches pp
         WHERE pp.mlb_pitcher_id = p.mlb_player_id::integer
         AND pp.season = 2025) as pitcher_pitches_thrown
    FROM prospects p
    LEFT JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    WHERE p.name LIKE '%Chandler%' AND p.position IN ('SP', 'RP')
    GROUP BY p.name, p.mlb_player_id, p.position
""")
row = cursor.fetchone()
if row:
    name, mlb_id, position, games, pitches = row
    print(f"  Name: {name}")
    print(f"  MLB ID: {mlb_id}")
    print(f"  Position: {position}")
    print(f"  Game Logs: {games}")
    print(f"  Pitcher Pitches Thrown: {pitches}")

    # By level
    cursor.execute("""
        SELECT level, COUNT(*) as games
        FROM milb_game_logs
        WHERE mlb_player_id = %s AND season = 2025
        GROUP BY level
        ORDER BY level
    """, (mlb_id,))
    print("  By Level:")
    for level, count in cursor.fetchall():
        print(f"    {level}: {count} games")

conn.close()
