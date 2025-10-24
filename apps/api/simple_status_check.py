"""Simple status check without unicode"""
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cursor = conn.cursor()

print("="*80)
print("2025 PITCH DATA STATUS")
print("="*80)

# Totals
cursor.execute("SELECT COUNT(*), COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season = 2025")
bp, bb = cursor.fetchone()

cursor.execute("SELECT COUNT(*), COUNT(DISTINCT mlb_pitcher_id) FROM milb_pitcher_pitches WHERE season = 2025")
pp, pb = cursor.fetchone()

print(f"\nBatter Pitches: {bp:,} from {bb:,} batters")
print(f"Pitcher Pitches: {pp:,} from {pb:,} pitchers")
print(f"TOTAL PITCHES: {bp+pp:,}")

# Missing batters
cursor.execute("""
    SELECT COUNT(*)
    FROM prospects p
    INNER JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id AND gl.season = 2025
    LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id AND bp.season = 2025
    WHERE p.position NOT IN ('SP', 'RP') AND bp.mlb_batter_id IS NULL
""")
missing_batters = cursor.fetchone()[0]

# Missing pitchers
cursor.execute("""
    SELECT COUNT(*)
    FROM prospects p
    INNER JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id AND gl.season = 2025
    LEFT JOIN milb_pitcher_pitches pp ON p.mlb_player_id::integer = pp.mlb_pitcher_id AND pp.season = 2025
    WHERE p.position IN ('SP', 'RP') AND pp.mlb_pitcher_id IS NULL
""")
missing_pitchers = cursor.fetchone()[0]

print(f"\nMissing Data:")
print(f"  Batters: {missing_batters}")
print(f"  Pitchers: {missing_pitchers}")

if missing_batters == 0 and missing_pitchers == 0:
    print("\n[COMPLETE] All prospects with game logs have pitch data")
    print("[READY] Can proceed with updating rankings")
else:
    print(f"\n[IN PROGRESS] Collection still running")
    print(f"[WAIT] Let collection complete before updating rankings")

conn.close()
