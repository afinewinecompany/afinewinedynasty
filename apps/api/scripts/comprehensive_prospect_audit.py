import psycopg2
from datetime import datetime

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def comprehensive_prospect_audit():
    """Comprehensive audit of all prospects and their data coverage across all seasons"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n" + "="*80)
    print("COMPREHENSIVE PROSPECT DATA AUDIT")
    print(f"Timestamp: {datetime.now()}")
    print("="*80)

    # Get total prospects count
    cur.execute("SELECT COUNT(*) FROM prospects WHERE mlb_player_id IS NOT NULL")
    total_prospects = cur.fetchone()[0]

    print(f"\nTotal prospects with MLB Player ID: {total_prospects:,}")

    # Check coverage across all seasons
    seasons = [2023, 2024, 2025]

    print("\n" + "="*80)
    print("OVERALL COVERAGE SUMMARY")
    print("="*80)

    for season in seasons:
        print(f"\n=== {season} SEASON ===")

        # PBP coverage
        cur.execute(f"""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM milb_plate_appearances
            WHERE season = {season}
        """)
        pbp_count = cur.fetchone()[0]

        # Pitch coverage
        cur.execute(f"""
            SELECT COUNT(DISTINCT mlb_batter_id)
            FROM milb_batter_pitches
            WHERE season = {season}
        """)
        pitch_count = cur.fetchone()[0]

        # Prospects with data
        cur.execute(f"""
            SELECT COUNT(DISTINCT p.mlb_player_id)
            FROM prospects p
            LEFT JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id AND mpa.season = {season}
            WHERE p.mlb_player_id IS NOT NULL AND mpa.mlb_player_id IS NOT NULL
        """)
        prospects_pbp = cur.fetchone()[0]

        cur.execute(f"""
            SELECT COUNT(DISTINCT p.mlb_player_id)
            FROM prospects p
            LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id AND mbp.season = {season}
            WHERE p.mlb_player_id IS NOT NULL AND mbp.mlb_batter_id IS NOT NULL
        """)
        prospects_pitch = cur.fetchone()[0]

        pbp_pct = (prospects_pbp / total_prospects * 100) if total_prospects > 0 else 0
        pitch_pct = (prospects_pitch / total_prospects * 100) if total_prospects > 0 else 0

        print(f"Prospects with PBP data:   {prospects_pbp:4}/{total_prospects} ({pbp_pct:5.1f}%)")
        print(f"Prospects with Pitch data: {prospects_pitch:4}/{total_prospects} ({pitch_pct:5.1f}%)")

    # Find prospects with NO data at all
    print("\n" + "="*80)
    print("PROSPECTS WITH NO DATA (ANY SEASON)")
    print("="*80)

    cur.execute("""
        SELECT p.name, p.organization, p.mlb_player_id
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER
        )
        ORDER BY p.organization, p.name
    """)

    no_data = cur.fetchall()
    print(f"\nTotal prospects with NO data: {len(no_data)}")

    if no_data:
        print(f"\n{'Name':<30} {'Org':<5} {'MLB ID':<10}")
        print("-" * 50)
        for name, org, mlb_id in no_data[:50]:  # Show first 50
            print(f"{name:<30} {org:<5} {mlb_id:<10}")
        if len(no_data) > 50:
            print(f"\n... and {len(no_data) - 50} more")

    # Find prospects missing 2025 data specifically
    print("\n" + "="*80)
    print("PROSPECTS MISSING 2025 DATA")
    print("="*80)

    cur.execute("""
        SELECT p.name, p.organization, p.mlb_player_id,
               EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                      WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_pbp,
               EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                      WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025) as has_pitch
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND (
            NOT EXISTS (
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
            )
            OR NOT EXISTS (
                SELECT 1 FROM milb_batter_pitches mbp
                WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025
            )
        )
        ORDER BY p.organization, p.name
    """)

    missing_2025 = cur.fetchall()

    missing_pbp_only = [p for p in missing_2025 if not p[3]]
    missing_pitch_only = [p for p in missing_2025 if not p[4]]
    missing_both = [p for p in missing_2025 if not p[3] and not p[4]]

    print(f"\nProspects missing 2025 PBP data:   {len(missing_pbp_only)}")
    print(f"Prospects missing 2025 Pitch data: {len(missing_pitch_only)}")
    print(f"Prospects missing BOTH:            {len(missing_both)}")

    # Detailed breakdown by what's missing
    print("\n" + "="*80)
    print("MISSING 2025 DATA BREAKDOWN")
    print("="*80)

    print("\n--- Missing PBP Only (has Pitch data) ---")
    missing_pbp_has_pitch = [p for p in missing_2025 if not p[3] and p[4]]
    print(f"Count: {len(missing_pbp_has_pitch)}")
    if missing_pbp_has_pitch:
        for name, org, mlb_id, has_pbp, has_pitch in missing_pbp_has_pitch[:20]:
            print(f"  {name:<30} ({org}) - ID: {mlb_id}")
        if len(missing_pbp_has_pitch) > 20:
            print(f"  ... and {len(missing_pbp_has_pitch) - 20} more")

    print("\n--- Missing Pitch Only (has PBP data) ---")
    missing_pitch_has_pbp = [p for p in missing_2025 if p[3] and not p[4]]
    print(f"Count: {len(missing_pitch_has_pbp)}")
    if missing_pitch_has_pbp:
        for name, org, mlb_id, has_pbp, has_pitch in missing_pitch_has_pbp[:20]:
            print(f"  {name:<30} ({org}) - ID: {mlb_id}")
        if len(missing_pitch_has_pbp) > 20:
            print(f"  ... and {len(missing_pitch_has_pbp) - 20} more")

    print("\n--- Missing BOTH PBP and Pitch for 2025 ---")
    print(f"Count: {len(missing_both)}")
    if missing_both:
        for name, org, mlb_id, has_pbp, has_pitch in missing_both[:30]:
            print(f"  {name:<30} ({org}) - ID: {mlb_id}")
        if len(missing_both) > 30:
            print(f"  ... and {len(missing_both) - 30} more")

    # Organization breakdown
    print("\n" + "="*80)
    print("MISSING DATA BY ORGANIZATION (2025)")
    print("="*80)

    cur.execute("""
        SELECT p.organization,
               COUNT(DISTINCT p.mlb_player_id) as total,
               COUNT(DISTINCT CASE WHEN mpa.mlb_player_id IS NULL THEN p.mlb_player_id END) as missing_pbp,
               COUNT(DISTINCT CASE WHEN mbp.mlb_batter_id IS NULL THEN p.mlb_player_id END) as missing_pitch
        FROM prospects p
        LEFT JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id AND mpa.season = 2025
        LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id AND mbp.season = 2025
        WHERE p.mlb_player_id IS NOT NULL
        GROUP BY p.organization
        ORDER BY missing_pbp DESC, missing_pitch DESC
    """)

    print(f"\n{'Org':<5} | {'Total':<6} | {'Miss PBP':<9} | {'Miss Pitch':<11} | {'%MissPBP':<10} | {'%MissPitch':<10}")
    print("-" * 75)
    for org, total, miss_pbp, miss_pitch in cur.fetchall():
        pbp_pct = (miss_pbp / total * 100) if total > 0 else 0
        pitch_pct = (miss_pitch / total * 100) if total > 0 else 0
        print(f"{org:<5} | {total:<6} | {miss_pbp:<9} | {miss_pitch:<11} | {pbp_pct:<9.1f}% | {pitch_pct:<9.1f}%")

    conn.close()

    print("\n" + "="*80)
    print("AUDIT COMPLETE")
    print("="*80)

if __name__ == "__main__":
    comprehensive_prospect_audit()
