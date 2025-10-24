"""Investigate why missing count is so high"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("Investigating missing pitch data counts...")
print()

# How many total players have game logs?
cursor.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_game_logs
    WHERE season = 2025
""")
total_with_logs = cursor.fetchone()[0]
print(f"Total players with 2025 game logs: {total_with_logs:,}")

# How many are in prospects table?
cursor.execute("""
    SELECT COUNT(DISTINCT gl.mlb_player_id)
    FROM milb_game_logs gl
    INNER JOIN prospects p ON gl.mlb_player_id = p.mlb_player_id::integer
    WHERE gl.season = 2025
""")
prospects_with_logs = cursor.fetchone()[0]
print(f"Players in prospects table with game logs: {prospects_with_logs:,}")

# How many prospects are batters (not pitchers)?
cursor.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    INNER JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id
    WHERE gl.season = 2025
        AND p.position NOT IN ('SP', 'RP')
""")
batter_prospects_with_logs = cursor.fetchone()[0]
print(f"Batter prospects with game logs: {batter_prospects_with_logs:,}")

# How many of those batters have pitch data?
cursor.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    INNER JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id
    INNER JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
    WHERE gl.season = 2025
        AND bp.season = 2025
        AND p.position NOT IN ('SP', 'RP')
""")
batters_with_pitch_data = cursor.fetchone()[0]
print(f"Batter prospects WITH pitch data: {batters_with_pitch_data:,}")
print(f"Batter prospects MISSING pitch data: {batter_prospects_with_logs - batters_with_pitch_data:,}")

# The issue: we're collecting from game_logs table, but some game logs might be for MLB players
# Let's check if we're only collecting prospects
cursor.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_game_logs
    WHERE season = 2025
        AND mlb_player_id NOT IN (SELECT mlb_player_id::integer FROM prospects WHERE mlb_player_id IS NOT NULL)
""")
non_prospect_gamelogs = cursor.fetchone()[0]
print(f"\nNon-prospect players in game logs: {non_prospect_gamelogs:,}")

# Check the collection script - is it querying all game logs or just prospects?
print("\n" + "="*80)
print("KEY FINDING")
print("="*80)
print(f"\nThe collection script is querying ALL players with game logs ({total_with_logs:,}),")
print(f"not just the prospects in our prospects table ({prospects_with_logs:,}).")
print(f"\nThis means it's trying to collect {total_with_logs - prospects_with_logs:,} non-prospect players.")
print(f"\nFor OUR PURPOSES (updating rankings), we only care about the {prospects_with_logs:,} prospects.")

# What's the actual status for JUST our prospects?
print("\n" + "="*80)
print("PROSPECTS-ONLY STATUS")
print("="*80)

cursor.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    INNER JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id AND gl.season = 2025
    LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id AND bp.season = 2025
    WHERE p.position NOT IN ('SP', 'RP')
        AND bp.mlb_batter_id IS NULL
""")
missing_prospect_batters = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(DISTINCT p.mlb_player_id)
    FROM prospects p
    INNER JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id AND gl.season = 2025
    LEFT JOIN milb_pitcher_pitches pp ON p.mlb_player_id::integer = pp.mlb_pitcher_id AND pp.season = 2025
    WHERE p.position IN ('SP', 'RP')
        AND pp.mlb_pitcher_id IS NULL
""")
missing_prospect_pitchers = cursor.fetchone()[0]

print(f"\nProspect batters missing pitch data: {missing_prospect_batters}")
print(f"Prospect pitchers missing pitch data: {missing_prospect_pitchers}")

if missing_prospect_batters == 0 and missing_prospect_pitchers == 0:
    print("\n[COMPLETE] All PROSPECTS have pitch data!")
    print("[READY] Can update rankings now!")
else:
    print(f"\n[WAIT] {missing_prospect_batters + missing_prospect_pitchers} prospects still need data")

conn.close()
