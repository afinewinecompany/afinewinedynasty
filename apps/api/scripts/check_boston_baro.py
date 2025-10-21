import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Check if Boston Baro exists
cur.execute("SELECT mlb_player_id, name, organization FROM prospects WHERE name = 'Boston Baro'")
result = cur.fetchone()

if result:
    print(f"Boston Baro found in prospects table:")
    print(f"  MLB ID: {result[0]}")
    print(f"  Name: {result[1]}")
    print(f"  Org: {result[2]}")

    mlb_id = result[0]

    # Check for PAs
    cur.execute("""
        SELECT COUNT(*) FROM milb_plate_appearances
        WHERE mlb_player_id = %s::INTEGER AND season = 2025
    """, (mlb_id,))
    pa_count = cur.fetchone()[0]
    print(f"  2025 PAs in database: {pa_count}")

    # Check for pitches
    cur.execute("""
        SELECT COUNT(*) FROM milb_batter_pitches
        WHERE mlb_batter_id = %s::INTEGER AND season = 2025
    """, (mlb_id,))
    pitch_count = cur.fetchone()[0]
    print(f"  2025 Pitches in database: {pitch_count}")

    # Check what the recent collection script would have queried
    cur.execute("""
        SELECT mlb_player_id, name,
               EXISTS(SELECT 1 FROM milb_plate_appearances mpa WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_pbp,
               EXISTS(SELECT 1 FROM milb_batter_pitches mbp WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025) as has_pitch
        FROM prospects p
        WHERE p.name = 'Boston Baro'
        AND p.mlb_player_id IS NOT NULL
    """)

    result2 = cur.fetchone()
    print(f"\n  Would be included in 'missing data' collection? {not result2[2] or not result2[3]}")
    print(f"    Has PBP: {result2[2]}")
    print(f"    Has Pitch: {result2[3]}")
else:
    print("Boston Baro NOT found in prospects table!")

conn.close()
