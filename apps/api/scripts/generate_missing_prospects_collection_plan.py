import psycopg2
from datetime import datetime
import csv

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

def generate_collection_plan():
    """Generate a prioritized collection plan for all missing prospect data"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print("\n" + "="*80)
    print("GENERATING COLLECTION PLAN FOR MISSING PROSPECT DATA")
    print(f"Timestamp: {datetime.now()}")
    print("="*80)

    # Get all prospects missing 2025 data with their status
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.organization,
            p.position,
            COALESCE(pr.v7_rank, 9999) as prospect_rank,
            EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                   WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_2025_pbp,
            EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                   WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025) as has_2025_pitch,
            EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                   WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2024) as has_2024_pbp,
            EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                   WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2024) as has_2024_pitch,
            EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                   WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER) as has_any_pbp,
            EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                   WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER) as has_any_pitch
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id AND pr.report_year = 2025
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
        ORDER BY
            COALESCE(pr.v7_rank, 9999) ASC,
            p.organization,
            p.name
    """)

    missing_prospects = cur.fetchall()

    print(f"\nTotal prospects needing collection: {len(missing_prospects)}")

    # Categorize prospects
    priority_1_high_rank = []  # Top 100 prospects missing data
    priority_2_mid_rank = []   # Rank 101-300 missing data
    priority_3_low_rank = []   # Rank 300+ missing data
    priority_4_partial = []    # Has PBP but no Pitch
    priority_5_no_history = [] # Never had any data

    for prospect in missing_prospects:
        mlb_id, name, org, pos, prospect_rank, has_2025_pbp, has_2025_pitch, has_2024_pbp, has_2024_pitch, has_any_pbp, has_any_pitch = prospect

        # Categorize by priority
        if not has_2025_pbp and not has_2025_pitch:
            # Missing both 2025 data types
            if not has_any_pbp and not has_any_pitch:
                priority_5_no_history.append(prospect)
            elif prospect_rank <= 100:
                priority_1_high_rank.append(prospect)
            elif prospect_rank <= 300:
                priority_2_mid_rank.append(prospect)
            else:
                priority_3_low_rank.append(prospect)
        elif has_2025_pbp and not has_2025_pitch:
            # Has PBP but missing Pitch
            priority_4_partial.append(prospect)

    print("\n" + "="*80)
    print("COLLECTION PRIORITIES")
    print("="*80)
    print(f"\nPriority 1 - Top 100 Prospects Missing 2025 Data:     {len(priority_1_high_rank)}")
    print(f"Priority 2 - Rank 101-300 Missing 2025 Data:          {len(priority_2_mid_rank)}")
    print(f"Priority 3 - Lower Rank Missing 2025 Data:            {len(priority_3_low_rank)}")
    print(f"Priority 4 - Has PBP but Missing Pitch:               {len(priority_4_partial)}")
    print(f"Priority 5 - Never Had Any Data (Verification Needed): {len(priority_5_no_history)}")

    # Generate CSV files for each priority
    priorities = [
        (1, "top_100_missing", priority_1_high_rank),
        (2, "mid_rank_missing", priority_2_mid_rank),
        (3, "low_rank_missing", priority_3_low_rank),
        (4, "partial_data", priority_4_partial),
        (5, "no_history", priority_5_no_history)
    ]

    for priority_num, filename, prospects in priorities:
        if prospects:
            csv_filename = f"collection_priority{priority_num}_{filename}_{timestamp}.csv"
            with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['MLB_ID', 'Name', 'Organization', 'Position', 'Rank',
                               'Has_2025_PBP', 'Has_2025_Pitch', 'Has_2024_PBP', 'Has_2024_Pitch',
                               'Has_Any_PBP', 'Has_Any_Pitch'])
                for prospect in prospects:
                    writer.writerow(prospect)
            print(f"\nGenerated: {csv_filename}")

    # Generate collection lists (just IDs) for batch processing
    print("\n" + "="*80)
    print("GENERATING BATCH COLLECTION LISTS")
    print("="*80)

    for priority_num, filename, prospects in priorities:
        if prospects:
            txt_filename = f"collection_batch_{priority_num}_{filename}_{timestamp}.txt"
            with open(txt_filename, 'w') as f:
                for prospect in prospects:
                    f.write(f"{prospect[0]}\n")  # Just the MLB ID
            print(f"Generated: {txt_filename} ({len(prospects)} IDs)")

    # Summary statistics by organization
    print("\n" + "="*80)
    print("PRIORITY 1 (TOP 100) BREAKDOWN BY ORGANIZATION")
    print("="*80)

    if priority_1_high_rank:
        org_counts = {}
        for prospect in priority_1_high_rank:
            org = prospect[2]
            org_counts[org] = org_counts.get(org, 0) + 1

        print(f"\n{'Organization':<15} {'Count':<10}")
        print("-" * 30)
        for org, count in sorted(org_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"{org:<15} {count:<10}")

    # Detailed list of Priority 1 prospects
    print("\n" + "="*80)
    print("PRIORITY 1 - TOP 100 PROSPECTS NEEDING COLLECTION")
    print("="*80)

    if priority_1_high_rank:
        print(f"\n{'Rank':<6} {'Name':<30} {'Org':<5} {'Pos':<5} {'MLB ID':<10} {'2025 Status':<15}")
        print("-" * 80)
        for prospect in priority_1_high_rank[:50]:  # Show first 50
            mlb_id, name, org, pos, prospect_rank, has_2025_pbp, has_2025_pitch, _, _, _, _ = prospect
            status = []
            if not has_2025_pbp:
                status.append("No PBP")
            if not has_2025_pitch:
                status.append("No Pitch")
            status_str = ", ".join(status)
            print(f"{prospect_rank:<6} {name:<30} {org:<5} {pos or 'N/A':<5} {mlb_id:<10} {status_str:<15}")

        if len(priority_1_high_rank) > 50:
            print(f"\n... and {len(priority_1_high_rank) - 50} more")

    # Generate master collection script command
    print("\n" + "="*80)
    print("SUGGESTED COLLECTION COMMANDS")
    print("="*80)

    print("\n# Priority 1 - Top 100 Prospects")
    print(f"python collect_missing_prospects.py --priority 1 --input collection_batch_1_top_100_missing_{timestamp}.txt")

    print("\n# Priority 2 - Mid Rank")
    print(f"python collect_missing_prospects.py --priority 2 --input collection_batch_2_mid_rank_missing_{timestamp}.txt")

    print("\n# Priority 3 - Lower Rank")
    print(f"python collect_missing_prospects.py --priority 3 --input collection_batch_3_low_rank_missing_{timestamp}.txt")

    print("\n# Priority 4 - Partial Data (PBP only, need Pitch)")
    print(f"python collect_missing_pitches.py --input collection_batch_4_partial_data_{timestamp}.txt")

    conn.close()

    print("\n" + "="*80)
    print("COLLECTION PLAN GENERATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    generate_collection_plan()
