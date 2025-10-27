"""Check if we have complete data coverage for all prospects with game logs"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("DATA COVERAGE ANALYSIS - 2025 SEASON")
print("="*80)

# Overall stats
cursor.execute("""
    SELECT
        COUNT(*) as total_pitches,
        COUNT(DISTINCT mlb_batter_id) as unique_batters,
        COUNT(DISTINCT game_pk) as unique_games
    FROM milb_batter_pitches
    WHERE season = 2025
""")
total_pitches, unique_batters, unique_games = cursor.fetchone()
print(f"\nBatter Pitch Data:")
print(f"  Total Pitches: {total_pitches:,}")
print(f"  Unique Batters: {unique_batters:,}")
print(f"  Unique Games: {unique_games:,}")

cursor.execute("""
    SELECT
        COUNT(*) as total_pitches,
        COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers,
        COUNT(DISTINCT game_pk) as unique_games
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
total_pitches, unique_pitchers, unique_games = cursor.fetchone()
print(f"\nPitcher Pitch Data:")
print(f"  Total Pitches: {total_pitches:,}")
print(f"  Unique Pitchers: {unique_pitchers:,}")
print(f"  Unique Games: {unique_games:,}")

# Prospects with game logs but NO batter pitch data
print("\n" + "="*80)
print("BATTERS: Prospects with Game Logs but Missing Pitch Data")
print("="*80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        COUNT(DISTINCT gl.game_pk) as game_logs,
        COALESCE((SELECT COUNT(DISTINCT bp.game_pk)
                  FROM milb_batter_pitches bp
                  WHERE bp.mlb_batter_id = p.mlb_player_id::integer
                  AND bp.season = 2025), 0) as pitch_games
    FROM prospects p
    INNER JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    LEFT JOIN milb_batter_pitches bp
        ON p.mlb_player_id::integer = bp.mlb_batter_id
        AND bp.season = 2025
    WHERE p.position NOT IN ('SP', 'RP')
    GROUP BY p.name, p.mlb_player_id, p.position
    HAVING COUNT(DISTINCT gl.game_pk) > 0
        AND COALESCE((SELECT COUNT(DISTINCT bp.game_pk)
                      FROM milb_batter_pitches bp
                      WHERE bp.mlb_batter_id = p.mlb_player_id::integer
                      AND bp.season = 2025), 0) = 0
    ORDER BY game_logs DESC
    LIMIT 20
""")

missing_batters = cursor.fetchall()
if missing_batters:
    print(f"\nFound {len(missing_batters)} batters with game logs but no pitch data:")
    for name, mlb_id, position, game_logs, pitch_games in missing_batters:
        print(f"  {name} ({mlb_id}) - {position}: {game_logs} games, {pitch_games} with pitch data")
else:
    print("\n✓ All batters with game logs have pitch data!")

# Pitchers with game logs but NO pitcher pitch data
print("\n" + "="*80)
print("PITCHERS: Prospects with Game Logs but Missing Pitch Data")
print("="*80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        COUNT(DISTINCT gl.game_pk) as game_logs,
        COALESCE((SELECT COUNT(DISTINCT pp.game_pk)
                  FROM milb_pitcher_pitches pp
                  WHERE pp.mlb_pitcher_id = p.mlb_player_id::integer
                  AND pp.season = 2025), 0) as pitch_games
    FROM prospects p
    INNER JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    LEFT JOIN milb_pitcher_pitches pp
        ON p.mlb_player_id::integer = pp.mlb_pitcher_id
        AND pp.season = 2025
    WHERE p.position IN ('SP', 'RP')
    GROUP BY p.name, p.mlb_player_id, p.position
    HAVING COUNT(DISTINCT gl.game_pk) > 0
        AND COALESCE((SELECT COUNT(DISTINCT pp.game_pk)
                      FROM milb_pitcher_pitches pp
                      WHERE pp.mlb_pitcher_id = p.mlb_player_id::integer
                      AND pp.season = 2025), 0) = 0
    ORDER BY game_logs DESC
    LIMIT 20
""")

missing_pitchers = cursor.fetchall()
if missing_pitchers:
    print(f"\nFound {len(missing_pitchers)} pitchers with game logs but no pitch data:")
    for name, mlb_id, position, game_logs, pitch_games in missing_pitchers:
        print(f"  {name} ({mlb_id}) - {position}: {game_logs} games, {pitch_games} with pitch data")
else:
    print("\n✓ All pitchers with game logs have pitch data!")

# Top prospects coverage check
print("\n" + "="*80)
print("TOP 20 PROSPECTS DATA COVERAGE")
print("="*80)

cursor.execute("""
    SELECT
        p.name,
        p.mlb_player_id,
        p.position,
        p.fg_rank_2025,
        COUNT(DISTINCT gl.game_pk) as game_logs,
        COALESCE((SELECT COUNT(*)
                  FROM milb_batter_pitches bp
                  WHERE bp.mlb_batter_id = p.mlb_player_id::integer
                  AND bp.season = 2025), 0) as batter_pitches,
        COALESCE((SELECT COUNT(*)
                  FROM milb_pitcher_pitches pp
                  WHERE pp.mlb_pitcher_id = p.mlb_player_id::integer
                  AND pp.season = 2025), 0) as pitcher_pitches
    FROM prospects p
    LEFT JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
    WHERE p.fg_rank_2025 IS NOT NULL
        AND p.fg_rank_2025 <= 20
    GROUP BY p.name, p.mlb_player_id, p.position, p.fg_rank_2025
    ORDER BY p.fg_rank_2025
""")

print("\nRank | Name | Position | Game Logs | Pitches")
print("-" * 80)
for name, mlb_id, position, rank, game_logs, batter_pitches, pitcher_pitches in cursor.fetchall():
    pitches = batter_pitches if position not in ('SP', 'RP') else pitcher_pitches
    status = "✓" if pitches > 0 else "✗"
    print(f"{rank:4d} | {name:25s} | {position:8s} | {game_logs:9d} | {pitches:7d} {status}")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)

cursor.execute("""
    SELECT COUNT(*) FROM prospects
    WHERE mlb_player_id IS NOT NULL
""")
total_prospects = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    INNER JOIN milb_game_logs gl
        ON p.mlb_player_id::integer = gl.mlb_player_id
        AND gl.season = 2025
""")
prospects_with_gamelogs = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(DISTINCT mlb_batter_id)
    FROM milb_batter_pitches
    WHERE season = 2025
""")
batters_with_pitches = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(DISTINCT mlb_pitcher_id)
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
pitchers_with_pitches = cursor.fetchone()[0]

print(f"\nTotal Prospects: {total_prospects:,}")
print(f"Prospects with 2025 Game Logs: {prospects_with_gamelogs:,}")
print(f"Batters with Pitch Data: {batters_with_pitches:,}")
print(f"Pitchers with Pitch Data: {pitchers_with_pitches:,}")
print(f"Total with Pitch Data: {batters_with_pitches + pitchers_with_pitches:,}")

if missing_batters or missing_pitchers:
    print(f"\n⚠️  ACTION NEEDED: {len(missing_batters)} batters and {len(missing_pitchers)} pitchers missing pitch data")
else:
    print(f"\n✓ DATA COMPLETE: All prospects with game logs have pitch data!")
    print(f"✓ READY TO UPDATE RANKINGS")

conn.close()
