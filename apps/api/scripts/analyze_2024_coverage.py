import psycopg2
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def analyze_2024_coverage():
    """Analyze 2024 data coverage for all prospects"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n" + "="*70)
    print("2024 DATA COVERAGE ANALYSIS - ALL PROSPECTS")
    print(f"Timestamp: {datetime.now()}")
    print("="*70)

    # Get all prospects with mlb_player_id (needed for milb tables)
    cur.execute("""
        SELECT mlb_id, mlb_player_id, name, organization
        FROM prospects
        WHERE mlb_player_id IS NOT NULL
        ORDER BY name
    """)
    all_prospects = cur.fetchall()

    print(f"\nTotal prospects with MLB player IDs: {len(all_prospects)}")

    # Analyze coverage for each prospect
    no_pbp = []
    pbp_no_pitch = []
    complete = []

    for mlb_id, mlb_player_id, name, team in all_prospects:
        if not mlb_player_id:
            continue

        # Check PBP data for 2024
        cur.execute("""
            SELECT COUNT(*)
            FROM milb_plate_appearances
            WHERE mlb_player_id = %s AND season = 2024
        """, (mlb_player_id,))
        pbp_count = cur.fetchone()[0]

        # Check pitch data for 2024
        cur.execute("""
            SELECT COUNT(*)
            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = 2024
        """, (mlb_player_id,))
        pitch_count = cur.fetchone()[0]

        if pbp_count == 0:
            no_pbp.append((mlb_player_id, name, team))
        elif pitch_count == 0:
            pbp_no_pitch.append((mlb_player_id, name, team, pbp_count))
        else:
            complete.append((mlb_player_id, name, team, pbp_count, pitch_count))

    # Report results
    print(f"\n=== 2024 COVERAGE SUMMARY ===")
    print(f"Complete (PBP + Pitch): {len(complete)} prospects")
    print(f"PBP only (no pitch):    {len(pbp_no_pitch)} prospects")
    print(f"No data at all:         {len(no_pbp)} prospects")

    # List prospects without data
    print(f"\n=== PROSPECTS MISSING 2024 PBP DATA ===")
    print(f"Total: {len(no_pbp)} prospects")
    for mlb_id, name, team in no_pbp[:20]:
        print(f"{name:30} ({team:3}) - ID: {mlb_id}")

    # List prospects with PBP but no pitch data
    print(f"\n=== PROSPECTS WITH PBP BUT NO PITCH DATA (2024) ===")
    print(f"Total: {len(pbp_no_pitch)} prospects")
    for mlb_id, name, team, pbp_count in pbp_no_pitch[:20]:
        print(f"{name:30} ({team:3}) - {pbp_count} PAs need pitch data - ID: {mlb_id}")

    # Save lists for collection scripts
    print(f"\n=== SAVING COLLECTION LISTS ===")

    # Save prospects needing PBP
    with open('needs_2024_pbp.txt', 'w') as f:
        for mlb_id, name, team in no_pbp:
            f.write(f"{mlb_id},{name},{team}\n")
    print(f"Saved {len(no_pbp)} prospects to needs_2024_pbp.txt")

    # Save prospects needing pitch data
    with open('needs_2024_pitch.txt', 'w') as f:
        for mlb_id, name, team, pbp_count in pbp_no_pitch:
            f.write(f"{mlb_id},{name},{team},{pbp_count}\n")
    print(f"Saved {len(pbp_no_pitch)} prospects to needs_2024_pitch.txt")

    # Get total database stats
    cur.execute("SELECT COUNT(*) FROM milb_plate_appearances WHERE season = 2024")
    total_pbp_2024 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2024")
    total_pitch_2024 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_player_id) FROM milb_plate_appearances WHERE season = 2024")
    unique_pbp_2024 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season = 2024")
    unique_pitch_2024 = cur.fetchone()[0]

    print(f"\n=== DATABASE TOTALS FOR 2024 ===")
    print(f"Total PBP records:         {total_pbp_2024:,}")
    print(f"Total Pitch records:       {total_pitch_2024:,}")
    print(f"Unique players with PBP:   {unique_pbp_2024:,}")
    print(f"Unique players with Pitch: {unique_pitch_2024:,}")

    # Check date range
    cur.execute("""
        SELECT MIN(game_date) as earliest, MAX(game_date) as latest
        FROM milb_plate_appearances
        WHERE season = 2024
    """)
    result = cur.fetchone()
    if result and result[0]:
        print(f"\n=== 2024 SEASON DATE RANGE ===")
        print(f"Earliest game: {result[0]}")
        print(f"Latest game:   {result[1]}")

    conn.close()
    return no_pbp, pbp_no_pitch, complete

if __name__ == "__main__":
    no_pbp, pbp_no_pitch, complete = analyze_2024_coverage()

    print(f"\n=== COLLECTION PRIORITY ===")
    print(f"1. Collect PBP for {len(no_pbp)} prospects with no 2024 data")
    print(f"2. Add pitch data for {len(pbp_no_pitch)} prospects with PBP only")
    print(f"3. Already complete: {len(complete)} prospects")

    print("\n[ANALYSIS COMPLETE]")