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
print("2024 MiLB DATA COLLECTION STATUS")
print("="*80)

# Total prospects
cur.execute("SELECT COUNT(*) FROM prospects WHERE mlb_player_id IS NOT NULL")
total_prospects = cur.fetchone()[0]

# Batters vs Pitchers
cur.execute("""
    SELECT COUNT(*)
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
    AND position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
""")
total_batters = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
    AND position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
""")
total_pitchers = cur.fetchone()[0]

print(f"\nTOTAL PROSPECTS: {total_prospects}")
print(f"  - Batters: {total_batters}")
print(f"  - Pitchers: {total_pitchers}")

# Check 2024 batter data
cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_plate_appearances
    WHERE season = 2024
""")
batters_2024_pa = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_batter_id)
    FROM milb_batter_pitches
    WHERE season = 2024
""")
batters_2024_pitches = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM milb_plate_appearances WHERE season = 2024")
total_2024_pas = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2024")
total_2024_batter_pitches = cur.fetchone()[0]

print(f"\n{'='*80}")
print("2024 BATTER DATA (EXISTING)")
print("="*80)
print(f"Batters with PAs: {batters_2024_pa} ({100*batters_2024_pa/total_batters:.1f}%)")
print(f"Batters with pitches: {batters_2024_pitches} ({100*batters_2024_pitches/total_batters:.1f}%)")
print(f"Total PAs: {total_2024_pas:,}")
print(f"Total pitches: {total_2024_batter_pitches:,}")

# Check 2024 pitcher data
cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_pitcher_appearances
    WHERE season = 2024
""")
pitchers_2024_games = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_pitcher_id)
    FROM milb_pitcher_pitches
    WHERE season = 2024
""")
pitchers_2024_pitches = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM milb_pitcher_appearances WHERE season = 2024")
total_2024_pitcher_games = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM milb_pitcher_pitches WHERE season = 2024")
total_2024_pitcher_pitches = cur.fetchone()[0]

print(f"\n{'='*80}")
print("2024 PITCHER DATA (EXISTING)")
print("="*80)
print(f"Pitchers with games: {pitchers_2024_games} ({100*pitchers_2024_games/total_pitchers:.1f}%)")
print(f"Pitchers with pitches: {pitchers_2024_pitches} ({100*pitchers_2024_pitches/total_pitchers:.1f}%)")
print(f"Total games: {total_2024_pitcher_games:,}")
print(f"Total pitches: {total_2024_pitcher_pitches:,}")

# Find missing batters
cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
    AND (
        NOT EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2024
        )
        OR NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2024
        )
    )
""")
missing_batters = cur.fetchone()[0]

# Find missing pitchers
cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
    AND (
        NOT EXISTS (
            SELECT 1 FROM milb_pitcher_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2024
        )
        OR NOT EXISTS (
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2024
        )
    )
""")
missing_pitchers = cur.fetchone()[0]

print(f"\n{'='*80}")
print("PROSPECTS NEEDING 2024 DATA COLLECTION")
print("="*80)
print(f"Batters needing data: {missing_batters}")
print(f"Pitchers needing data: {missing_pitchers}")
print(f"TOTAL to collect: {missing_batters + missing_pitchers}")
print("="*80 + "\n")

cur.close()
conn.close()
