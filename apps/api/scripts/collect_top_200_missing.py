import psycopg2
from datetime import datetime
import time

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def get_top_200_missing():
    """Get all top 200 ranked prospects missing 2025 data"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    print("\n" + "="*80)
    print("IDENTIFYING TOP 200 PROSPECTS MISSING 2025 DATA")
    print(f"Timestamp: {datetime.now()}")
    print("="*80)

    # Get top 200 prospects missing data
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.organization,
            p.position,
            pr.v7_rank as prospect_rank,
            EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                   WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_2025_pbp,
            EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                   WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025) as has_2025_pitch
        FROM prospects p
        INNER JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id AND pr.report_year = 2025
        WHERE p.mlb_player_id IS NOT NULL
        AND pr.v7_rank <= 200
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
        ORDER BY pr.v7_rank ASC
    """)

    missing_prospects = cur.fetchall()
    conn.close()

    print(f"\nTop 200 prospects missing 2025 data: {len(missing_prospects)}")

    if missing_prospects:
        print(f"\n{'Rank':<6} {'Name':<30} {'Org':<5} {'Pos':<5} {'MLB ID':<10} {'Missing':<20}")
        print("-" * 80)
        for mlb_id, name, org, pos, rank, has_pbp, has_pitch in missing_prospects:
            missing = []
            if not has_pbp:
                missing.append("PBP")
            if not has_pitch:
                missing.append("Pitch")
            missing_str = ", ".join(missing)
            print(f"{rank:<6} {name:<30} {org:<5} {pos or 'N/A':<5} {mlb_id:<10} {missing_str:<20}")

    return missing_prospects


def collect_prospect_data(mlb_player_id, name, rank):
    """Collect both PBP and Pitch data for a single prospect"""
    print(f"\n{'='*60}")
    print(f"Collecting data for #{rank} {name} (ID: {mlb_player_id})")
    print(f"{'='*60}")

    try:
        # Import the collection modules
        import sys
        sys.path.insert(0, 'C:/Users/lilra/myprojects/afinewinedynasty/apps/api')
        from app.services.stats_bomber import StatsBomber

        bomber = StatsBomber()

        # Collect PBP data for 2025
        print(f"\n[1/2] Collecting Play-by-Play data for 2025...")
        try:
            pbp_result = bomber.collect_player_milb_pbp(int(mlb_player_id), 2025)
            if pbp_result and 'plate_appearances' in pbp_result:
                pa_count = len(pbp_result['plate_appearances'])
                print(f"  ✓ Successfully collected {pa_count} plate appearances")
            else:
                print(f"  ⚠ No PBP data available for 2025")
        except Exception as e:
            print(f"  ✗ Error collecting PBP: {str(e)}")

        time.sleep(2)  # Rate limiting

        # Collect Pitch data for 2025
        print(f"\n[2/2] Collecting Pitch-by-Pitch data for 2025...")
        try:
            pitch_result = bomber.collect_batter_pitches(int(mlb_player_id), 2025)
            if pitch_result and 'pitches' in pitch_result:
                pitch_count = len(pitch_result['pitches'])
                print(f"  ✓ Successfully collected {pitch_count} pitches")
            else:
                print(f"  ⚠ No Pitch data available for 2025")
        except Exception as e:
            print(f"  ✗ Error collecting Pitch data: {str(e)}")

        time.sleep(2)  # Rate limiting

        print(f"\n✓ Completed collection for {name}")
        return True

    except Exception as e:
        print(f"\n✗ Failed to collect data for {name}: {str(e)}")
        return False


def main():
    """Main collection process"""
    print("\n" + "="*80)
    print("TOP 200 PROSPECTS - DATA COLLECTION")
    print("="*80)

    # Get list of missing prospects
    missing_prospects = get_top_200_missing()

    if not missing_prospects:
        print("\n✓ All top 200 prospects have complete 2025 data!")
        return

    print(f"\n{'='*80}")
    print(f"STARTING COLLECTION FOR {len(missing_prospects)} PROSPECTS")
    print(f"{'='*80}")

    successful = 0
    failed = 0

    for i, (mlb_id, name, org, pos, rank, has_pbp, has_pitch) in enumerate(missing_prospects, 1):
        print(f"\n\n[{i}/{len(missing_prospects)}] Processing prospect...")

        try:
            result = collect_prospect_data(mlb_id, name, rank)
            if result:
                successful += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Unexpected error: {str(e)}")
            failed += 1

        # Progress update every 5 prospects
        if i % 5 == 0:
            print(f"\n{'='*60}")
            print(f"PROGRESS: {i}/{len(missing_prospects)} prospects processed")
            print(f"Success: {successful} | Failed: {failed}")
            print(f"{'='*60}")

    # Final summary
    print("\n" + "="*80)
    print("COLLECTION COMPLETE")
    print("="*80)
    print(f"\nTotal prospects processed: {len(missing_prospects)}")
    print(f"Successful collections:    {successful}")
    print(f"Failed collections:        {failed}")
    print(f"Success rate:              {(successful/len(missing_prospects)*100):.1f}%")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()
