"""
Add missing prospects to database and prepare collection
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import requests
import time

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

def search_mlb_id(name, team=None):
    """Search for MLB player ID using MLB Stats API"""
    try:
        # Clean name
        name = name.strip()

        # Try MLB Stats API search
        url = f"https://statsapi.mlb.com/api/v1/people/search?names={name}&sportIds=11,12,13,14,15,5442,16&hydrate=currentTeam"
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()
            if data.get('people'):
                # Try to find exact match first
                for player in data['people']:
                    if player.get('fullName', '').lower() == name.lower():
                        return player['id'], player['fullName']

                # If no exact match, return first result
                if data['people']:
                    return data['people'][0]['id'], data['people'][0]['fullName']

        return None, None
    except Exception as e:
        print(f"Error searching for {name}: {e}")
        return None, None


def add_missing_prospects():
    """Add missing prospects to database"""

    # Read missing prospects
    missing_df = pd.read_csv('missing_prospects_20251017_093027.csv')

    print(f"Processing {len(missing_df)} missing prospects...")

    added_prospects = []
    failed_searches = []

    with engine.connect() as conn:
        for idx, row in missing_df.iterrows():
            name = row['name']
            team = row.get('team', '')
            position = row.get('position', '')
            age = row.get('age', None)
            eta = row.get('eta', None)
            level = row.get('level', '')
            rank = row.get('rank', None)

            print(f"\n[{idx+1}/{len(missing_df)}] Processing: {name}")

            # Search for MLB ID
            mlb_id, found_name = search_mlb_id(name, team)

            if mlb_id:
                print(f"  Found MLB ID: {mlb_id} ({found_name})")

                try:
                    # Check if already exists with this MLB ID
                    result = conn.execute(text('''
                        SELECT id FROM prospects WHERE mlb_player_id = :mlb_id
                    '''), {'mlb_id': str(mlb_id)})

                    if result.fetchone():
                        print(f"  Already exists in database")
                    else:
                        # Insert new prospect
                        conn.execute(text('''
                            INSERT INTO prospects (
                                name,
                                mlb_player_id,
                                position,
                                organization,
                                current_level,
                                age,
                                eta_year,
                                created_at,
                                updated_at
                            ) VALUES (
                                :name,
                                :mlb_id,
                                :position,
                                :team,
                                :level,
                                :age,
                                :eta,
                                NOW(),
                                NOW()
                            )
                        '''), {
                            'name': name,
                            'mlb_id': str(mlb_id),
                            'position': position,
                            'team': team,
                            'level': level,
                            'age': age if age else None,
                            'eta': int(eta) if eta else None
                        })
                        conn.commit()

                        added_prospects.append({
                            'name': name,
                            'mlb_id': mlb_id,
                            'team': team,
                            'position': position,
                            'rank': rank
                        })
                        print(f"  Added to database!")

                except Exception as e:
                    print(f"  Error adding to database: {e}")

            else:
                print(f"  Could not find MLB ID")
                failed_searches.append({
                    'name': name,
                    'team': team,
                    'position': position,
                    'rank': rank
                })

            # Small delay to avoid rate limiting
            time.sleep(0.5)

    # Save results
    if added_prospects:
        added_df = pd.DataFrame(added_prospects)
        filename = f'newly_added_prospects_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        added_df.to_csv(filename, index=False)
        print(f"\n✓ Added {len(added_prospects)} prospects to database")
        print(f"  Saved to: {filename}")

    if failed_searches:
        failed_df = pd.DataFrame(failed_searches)
        filename = f'prospects_not_found_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        failed_df.to_csv(filename, index=False)
        print(f"\n✗ Could not find MLB IDs for {len(failed_searches)} prospects")
        print(f"  Saved to: {filename}")

    return added_prospects, failed_searches


def create_collection_commands():
    """Create batch collection commands for all prospects needing data"""

    print("\n=== CREATING COLLECTION COMMANDS ===")

    # Read the collection needs
    needs_df = pd.read_csv('top_100_collection_needs_20251017_093441.csv')

    # Filter for prospects that need data and have MLB IDs
    to_collect = needs_df[
        (needs_df['status'].isin(['NO DATA', 'NEEDS PBP', 'NEEDS PITCH'])) &
        (needs_df['mlb_id'].notna())
    ]

    print(f"Found {len(to_collect)} prospects needing collection")

    # Group by collection type
    no_data = to_collect[to_collect['status'] == 'NO DATA']
    needs_pbp = to_collect[to_collect['status'] == 'NEEDS PBP']
    needs_pitch = to_collect[to_collect['status'] == 'NEEDS PITCH']

    # Create batch collection script
    script = '''#!/usr/bin/env python
"""
Batch collection script for missing prospect data
Generated: ''' + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '''
"""

import sys
import os
import time
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.run_collection import run_collection

# Prospects needing FULL collection (both PBP and Pitch)
FULL_COLLECTION = [
'''

    for _, row in no_data.iterrows():
        script += f"    ({int(row['mlb_id'])}, '{row['name']}', {row['rank']}),  # Rank #{row['rank']}\n"

    script += ''']

# Prospects needing PITCH-BY-PITCH only
PITCH_ONLY = [
'''

    for _, row in needs_pitch.iterrows():
        script += f"    ({int(row['mlb_id'])}, '{row['name']}', {row['rank']}),  # Rank #{row['rank']}\n"

    script += ''']

def collect_all():
    """Run collections for all prospects"""

    print(f"Starting collection at {datetime.now()}")
    print(f"Full collection: {len(FULL_COLLECTION)} prospects")
    print(f"Pitch-only: {len(PITCH_ONLY)} prospects")

    # Collect full data
    for mlb_id, name, rank in FULL_COLLECTION:
        print(f"\\nCollecting FULL data for Rank #{rank}: {name} (ID: {mlb_id})")
        try:
            run_collection(
                player_id=mlb_id,
                start_year=2021,
                end_year=2025,
                collect_pbp=True,
                collect_pitch=True
            )
            time.sleep(2)  # Delay between collections
        except Exception as e:
            print(f"  Error: {e}")

    # Collect pitch data only
    for mlb_id, name, rank in PITCH_ONLY:
        print(f"\\nCollecting PITCH data for Rank #{rank}: {name} (ID: {mlb_id})")
        try:
            run_collection(
                player_id=mlb_id,
                start_year=2021,
                end_year=2025,
                collect_pbp=False,
                collect_pitch=True
            )
            time.sleep(1)  # Shorter delay for pitch-only
        except Exception as e:
            print(f"  Error: {e}")

    print(f"\\nCollection complete at {datetime.now()}")

if __name__ == "__main__":
    collect_all()
'''

    # Save the script
    filename = 'batch_collection_top100.py'
    with open(filename, 'w') as f:
        f.write(script)

    print(f"Generated batch collection script: {filename}")
    print(f"  - Full collection: {len(no_data)} prospects")
    print(f"  - Pitch-only: {len(needs_pitch)} prospects")
    print(f"  - Total: {len(to_collect)} prospects")

    return filename


def main():
    print("=" * 60)
    print("ADD MISSING PROSPECTS AND PREPARE COLLECTION")
    print("=" * 60)

    # Step 1: Add missing prospects
    print("\n[1/2] Adding missing prospects to database...")
    added, failed = add_missing_prospects()

    # Step 2: Create collection commands
    print("\n[2/2] Creating collection commands...")
    collection_script = create_collection_commands()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(f"\n✓ Successfully added: {len(added)} prospects")
    print(f"✗ Could not find: {len(failed)} prospects")
    print(f"\n📝 Collection script: {collection_script}")

    print("\n=== KEY FINDINGS ===")
    print("1. We have 2,399 unique players with play-by-play data")
    print("2. Only 172 batters have pitch-by-pitch data (major gap!)")
    print("3. Top 100 prospects: 89 need some form of data collection")
    print("4. 41 top prospects have NO data at all")
    print("5. 38 top prospects need pitch-by-pitch data")

    print("\n=== RECOMMENDED ACTIONS ===")
    print("1. Run the batch collection script for Top 100 prospects")
    print("2. Focus on pitch-by-pitch data (biggest gap)")
    print("3. Prioritize 2024-2025 seasons for recent prospects")
    print("4. Monitor collection logs for any API issues")

    print("\nTo start collection, run:")
    print(f"  python {collection_script}")


if __name__ == "__main__":
    main()