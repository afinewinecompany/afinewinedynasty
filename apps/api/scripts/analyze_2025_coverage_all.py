import psycopg2
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def analyze_2025_coverage():
    """Analyze 2025 data coverage for all prospects"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n" + "="*70)
    print("2025 DATA COVERAGE ANALYSIS - ALL PROSPECTS")
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
    no_mlb_id = 0

    for mlb_id, mlb_player_id, name, team in all_prospects:
        if not mlb_player_id:
            no_mlb_id += 1
            continue

        # Check PBP data for 2025
        cur.execute("""
            SELECT COUNT(*)
            FROM milb_plate_appearances
            WHERE mlb_player_id = %s AND season = 2025
        """, (mlb_player_id,))
        pbp_count = cur.fetchone()[0]

        # Check pitch data for 2025
        cur.execute("""
            SELECT COUNT(*)
            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = 2025
        """, (mlb_player_id,))
        pitch_count = cur.fetchone()[0]

        if pbp_count == 0:
            no_pbp.append((mlb_player_id, name, team))
        elif pitch_count == 0:
            pbp_no_pitch.append((mlb_player_id, name, team, pbp_count))
        else:
            complete.append((mlb_player_id, name, team, pbp_count, pitch_count))

    # Report results
    print(f"\n=== 2025 COVERAGE SUMMARY ===")
    print(f"Complete (PBP + Pitch): {len(complete)} prospects")
    print(f"PBP only (no pitch):    {len(pbp_no_pitch)} prospects")
    print(f"No data at all:         {len(no_pbp)} prospects")

    # List prospects without data
    print(f"\n=== PROSPECTS MISSING 2025 PBP DATA ===")
    print(f"Total: {len(no_pbp)} prospects")
    for mlb_id, name, team in no_pbp[:20]:
        print(f"{name:30} ({team:3}) - ID: {mlb_id}")

    # List prospects with PBP but no pitch data
    print(f"\n=== PROSPECTS WITH PBP BUT NO PITCH DATA (2025) ===")
    print(f"Total: {len(pbp_no_pitch)} prospects")
    for mlb_id, name, team, pbp_count in pbp_no_pitch[:20]:
        print(f"{name:30} ({team:3}) - {pbp_count} PAs need pitch data - ID: {mlb_id}")

    # Save lists for collection scripts
    print(f"\n=== SAVING COLLECTION LISTS ===")

    # Save prospects needing PBP
    with open('needs_2025_pbp.txt', 'w') as f:
        for mlb_id, name, team in no_pbp:
            f.write(f"{mlb_id},{name},{team}\n")
    print(f"Saved {len(no_pbp)} prospects to needs_2025_pbp.txt")

    # Save prospects needing pitch data
    with open('needs_2025_pitch.txt', 'w') as f:
        for mlb_id, name, team, pbp_count in pbp_no_pitch:
            f.write(f"{mlb_id},{name},{team},{pbp_count}\n")
    print(f"Saved {len(pbp_no_pitch)} prospects to needs_2025_pitch.txt")

    # Get total database stats
    cur.execute("SELECT COUNT(*) FROM milb_plate_appearances WHERE season = 2025")
    total_pbp_2025 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2025")
    total_pitch_2025 = cur.fetchone()[0]

    print(f"\n=== DATABASE TOTALS FOR 2025 ===")
    print(f"Total PBP records:   {total_pbp_2025:,}")
    print(f"Total Pitch records: {total_pitch_2025:,}")

    conn.close()
    return no_pbp, pbp_no_pitch, complete

if __name__ == "__main__":
    no_pbp, pbp_no_pitch, complete = analyze_2025_coverage()

    print(f"\n=== COLLECTION PRIORITY ===")
    print(f"1. Collect PBP for {len(no_pbp)} prospects with no 2025 data")
    print(f"2. Add pitch data for {len(pbp_no_pitch)} prospects with PBP only")
    print(f"3. Already complete: {len(complete)} prospects")

    print("\n[ANALYSIS COMPLETE]")