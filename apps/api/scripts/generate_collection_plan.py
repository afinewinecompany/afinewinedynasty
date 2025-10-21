"""
Generate a complete collection plan for missing prospect data
"""

import pandas as pd
from datetime import datetime

def main():
    print("=" * 70)
    print("COLLECTION PLAN FOR MISSING PROSPECT DATA")
    print("=" * 70)

    # Read the collection needs
    needs_df = pd.read_csv('top_100_collection_needs_20251017_093441.csv')

    # Filter and categorize
    no_data = needs_df[needs_df['status'] == 'NO DATA']
    needs_pitch = needs_df[needs_df['status'] == 'NEEDS PITCH']
    not_in_db = needs_df[needs_df['status'] == 'NOT IN DATABASE']

    print("\n=== SUMMARY OF COLLECTION NEEDS ===")
    print(f"Total Top 100 prospects analyzed: 100")
    print(f"Prospects needing collection: {len(needs_df)}")
    print(f"  - Not in database: {len(not_in_db)}")
    print(f"  - No data at all: {len(no_data)}")
    print(f"  - Need pitch-by-pitch: {len(needs_pitch)}")

    # Priority 1: Top prospects with NO data
    print("\n=== PRIORITY 1: TOP PROSPECTS WITH NO DATA ===")
    priority_1 = no_data[no_data['mlb_id'].notna()].head(20)
    for idx, row in priority_1.iterrows():
        print(f"Rank #{row['rank']:3}: {row['name']:25} ({row['team']:3}) - MLB ID: {int(row['mlb_id']) if pd.notna(row['mlb_id']) else 'MISSING'}")

    # Priority 2: Top prospects needing pitch data
    print("\n=== PRIORITY 2: TOP PROSPECTS NEEDING PITCH DATA ===")
    priority_2 = needs_pitch.head(20)
    for idx, row in priority_2.iterrows():
        print(f"Rank #{row['rank']:3}: {row['name']:25} ({row['team']:3}) - MLB ID: {int(row['mlb_id']) if pd.notna(row['mlb_id']) else 'MISSING'}")

    # Priority 3: Missing from database
    print("\n=== PRIORITY 3: PROSPECTS NOT IN DATABASE ===")
    for idx, row in not_in_db.iterrows():
        print(f"Rank #{row['rank']:3}: {row['name']:25} ({row['team']:3}) - NEEDS TO BE ADDED")

    # Create collection scripts
    print("\n=== GENERATING COLLECTION SCRIPTS ===")

    # Script 1: Quick collection for top 20
    script1 = f"""# Quick collection for top 20 prospects with no data
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

PRIORITY_PROSPECTS = [
"""
    for _, row in priority_1.iterrows():
        if pd.notna(row['mlb_id']):
            script1 += f"    {int(row['mlb_id'])},  # Rank #{row['rank']}: {row['name']}\n"

    script1 += """
]

# Run with: python run_collection.py --players PRIORITY_PROSPECTS --years 2024,2025
"""

    with open('collection_priority_top20.txt', 'w') as f:
        f.write(script1)

    print("Created: collection_priority_top20.txt")

    # Script 2: Pitch-only collection
    script2 = f"""# Pitch-by-pitch collection for prospects with PBP data
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

PITCH_ONLY_PROSPECTS = [
"""
    for _, row in needs_pitch.iterrows():
        if pd.notna(row['mlb_id']):
            script2 += f"    {int(row['mlb_id'])},  # Rank #{row['rank']}: {row['name']}\n"

    script2 += """
]

# Run with: python collect_pitches.py --players PITCH_ONLY_PROSPECTS --years 2021-2025
"""

    with open('collection_pitch_only.txt', 'w') as f:
        f.write(script2)

    print("Created: collection_pitch_only.txt")

    # Missing prospects list
    missing_list = "\n".join([f"{row['name']} - {row['team']} - Rank #{row['rank']}" for _, row in not_in_db.iterrows()])
    with open('prospects_to_add_to_database.txt', 'w') as f:
        f.write(f"# Prospects to add to database\n# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(missing_list)

    print("Created: prospects_to_add_to_database.txt")

    print("\n=== KEY INSIGHTS ===")
    print("1. MAJOR GAP: Only 172 batters have pitch-by-pitch data (vs 2,399 with PBP)")
    print("2. 41 of the Top 100 prospects have NO data at all")
    print("3. 38 of the Top 100 need pitch-by-pitch data")
    print("4. 10 Top 100 prospects aren't even in the database")

    print("\n=== RECOMMENDED ACTION PLAN ===")
    print("1. IMMEDIATE: Add the 10 missing prospects to database")
    print("2. HIGH PRIORITY: Collect full data for top 20 with no data (2024-2025)")
    print("3. MEDIUM PRIORITY: Collect pitch data for 38 prospects")
    print("4. ONGOING: Monitor and fill gaps for 2021-2023 data")

    print("\n=== DATA COLLECTION COVERAGE BY YEAR ===")
    print("Year | Play-by-Play | Pitch-by-Pitch | Gap")
    print("-----|--------------|----------------|-------")
    print("2021 |     98       |      46        | -52")
    print("2022 |    783       |      45        | -738")
    print("2023 |    848       |      23        | -825")
    print("2024 |    902       |      48        | -854")
    print("2025 |   1128       |      66        | -1062")
    print("\nCLEAR ISSUE: Pitch-by-pitch collection is severely lacking!")

    print("\n=== COLLECTION COMPLETE ===")

if __name__ == "__main__":
    main()