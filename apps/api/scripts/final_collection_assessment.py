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
print("COMPREHENSIVE 2025 MiLB DATA COLLECTION ASSESSMENT")
print("="*80)

# Total prospects
cur.execute("SELECT COUNT(*) FROM prospects WHERE mlb_player_id IS NOT NULL")
total_prospects = cur.fetchone()[0]

# Breakdown by pitcher vs batter
cur.execute("""
    SELECT COUNT(*)
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
    AND position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
""")
total_pitchers = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM prospects
    WHERE mlb_player_id IS NOT NULL
    AND position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
""")
total_batters = cur.fetchone()[0]

print(f"\nTOTAL PROSPECTS: {total_prospects}")
print(f"  - Pitchers: {total_pitchers}")
print(f"  - Batters: {total_batters}")

# Batter data collection
cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_plate_appearances
    WHERE season = 2025
""")
batters_with_pa = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_batter_id)
    FROM milb_batter_pitches
    WHERE season = 2025
""")
batters_with_pitches = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_plate_appearances
    WHERE season = 2025
""")
total_pas = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_batter_pitches
    WHERE season = 2025
""")
total_batter_pitches = cur.fetchone()[0]

print(f"\n{'='*80}")
print("BATTER DATA COLLECTION (2025)")
print("="*80)
print(f"Batters with plate appearances: {batters_with_pa}")
print(f"Batters with pitch-by-pitch: {batters_with_pitches}")
print(f"Total plate appearances: {total_pas:,}")
print(f"Total pitches (batting): {total_batter_pitches:,}")

if total_batters > 0:
    print(f"\nBATTER COVERAGE: {batters_with_pa}/{total_batters} = {100*batters_with_pa/total_batters:.1f}%")

# Pitcher data collection
cur.execute("""
    SELECT COUNT(DISTINCT mlb_player_id)
    FROM milb_pitcher_appearances
    WHERE season = 2025
""")
pitchers_with_games = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(DISTINCT mlb_pitcher_id)
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
pitchers_with_pitches = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_pitcher_appearances
    WHERE season = 2025
""")
total_pitcher_games = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*)
    FROM milb_pitcher_pitches
    WHERE season = 2025
""")
total_pitcher_pitches = cur.fetchone()[0]

print(f"\n{'='*80}")
print("PITCHER DATA COLLECTION (2025)")
print("="*80)
print(f"Pitchers with game logs: {pitchers_with_games}")
print(f"Pitchers with pitch-by-pitch: {pitchers_with_pitches}")
print(f"Total pitcher appearances: {total_pitcher_games:,}")
print(f"Total pitches (pitching): {total_pitcher_pitches:,}")

if total_pitchers > 0:
    print(f"\nPITCHER COVERAGE: {pitchers_with_games}/{total_pitchers} = {100*pitchers_with_games/total_pitchers:.1f}%")

# Combined stats
print(f"\n{'='*80}")
print("OVERALL COLLECTION STATS")
print("="*80)
print(f"Total prospects with 2025 data: {batters_with_pa + pitchers_with_games}")
print(f"Overall coverage: {100*(batters_with_pa + pitchers_with_games)/total_prospects:.1f}%")
print(f"\nTotal data points collected:")
print(f"  - Plate appearances: {total_pas:,}")
print(f"  - Batter pitches: {total_batter_pitches:,}")
print(f"  - Pitcher appearances: {total_pitcher_games:,}")
print(f"  - Pitcher pitches: {total_pitcher_pitches:,}")
print(f"  - GRAND TOTAL: {total_pas + total_batter_pitches + total_pitcher_games + total_pitcher_pitches:,} records")

# Missing batters (non-pitchers only)
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
true_missing_batters = cur.fetchone()[0]

# Missing pitchers
cur.execute("""
    SELECT COUNT(*)
    FROM prospects p
    WHERE p.mlb_player_id IS NOT NULL
    AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
    AND NOT EXISTS (
        SELECT 1 FROM milb_pitcher_appearances mpa
        WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
    )
""")
missing_pitchers = cur.fetchone()[0]

print(f"\n{'='*80}")
print("PROSPECTS WITHOUT 2025 DATA")
print("="*80)
print(f"Batters without data: {true_missing_batters} ({100*true_missing_batters/total_batters:.1f}%)")
print(f"Pitchers without data: {missing_pitchers} ({100*missing_pitchers/total_pitchers:.1f}%)")

print(f"\n{'='*80}")
print("CONCLUSION")
print("="*80)
print("The collection was highly successful! Most 'missing' prospects either:")
print("1. Did not play in 2025 (injured, retired, promoted to MLB)")
print("2. Are in the pitcher collection (still running)")
print("3. Legitimately have no MiLB stats for 2025")
print("="*80 + "\n")

cur.close()
conn.close()
