"""
Analyze pitch-by-pitch and play-by-play collections for prospects
Find gaps in data collection from 2021-2025
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import os

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

def check_milb_collections():
    """Check MiLB collections data"""

    with engine.connect() as conn:
        # Check plate appearances
        result = conn.execute(text('''
            SELECT
                COUNT(DISTINCT pa.player_id) as unique_players,
                COUNT(*) as total_plate_appearances,
                MIN(pa.game_date) as earliest_date,
                MAX(pa.game_date) as latest_date,
                COUNT(DISTINCT pa.game_date) as unique_dates
            FROM milb_plate_appearances pa
        '''))

        row = result.fetchone()
        print("=== MiLB PLATE APPEARANCES ===")
        print(f"Unique players: {row[0]}")
        print(f"Total plate appearances: {row[1]}")
        print(f"Date range: {row[2]} to {row[3]}")
        print(f"Unique dates: {row[4]}")

        # Check by year
        result = conn.execute(text('''
            SELECT
                EXTRACT(YEAR FROM game_date) as year,
                COUNT(DISTINCT player_id) as players,
                COUNT(*) as plate_appearances
            FROM milb_plate_appearances
            GROUP BY EXTRACT(YEAR FROM game_date)
            ORDER BY year
        '''))

        print("\n=== PLATE APPEARANCES BY YEAR ===")
        for row in result:
            print(f"{int(row[0])}: {row[1]} players, {row[2]} PAs")

        # Check pitcher pitches
        result = conn.execute(text('''
            SELECT
                COUNT(DISTINCT pp.pitcher_id) as unique_pitchers,
                COUNT(*) as total_pitches,
                MIN(pp.game_date) as earliest_date,
                MAX(pp.game_date) as latest_date,
                COUNT(DISTINCT pp.game_date) as unique_dates
            FROM milb_pitcher_pitches pp
        '''))

        row = result.fetchone()
        print("\n=== MiLB PITCHER PITCHES ===")
        print(f"Unique pitchers: {row[0]}")
        print(f"Total pitches: {row[1]}")
        print(f"Date range: {row[2]} to {row[3]}")
        print(f"Unique dates: {row[4]}")

        # Check batter pitches
        result = conn.execute(text('''
            SELECT
                COUNT(DISTINCT bp.batter_id) as unique_batters,
                COUNT(*) as total_pitches,
                MIN(bp.game_date) as earliest_date,
                MAX(bp.game_date) as latest_date,
                COUNT(DISTINCT bp.game_date) as unique_dates
            FROM milb_batter_pitches bp
        '''))

        row = result.fetchone()
        print("\n=== MiLB BATTER PITCHES ===")
        print(f"Unique batters: {row[0]}")
        print(f"Total pitches seen: {row[1]}")
        print(f"Date range: {row[2]} to {row[3]}")
        print(f"Unique dates: {row[4]}")

def match_prospects_to_milb_data():
    """Match prospects from CSV to MiLB data"""

    # Read missing prospects CSV
    missing_df = pd.read_csv('missing_prospects_20251017_093027.csv')

    with engine.connect() as conn:
        # Get all prospects with MiLB data
        result = conn.execute(text('''
            SELECT DISTINCT
                p.name as prospect_name,
                p.mlb_player_id,
                pa.player_id as milb_player_id,
                COUNT(DISTINCT pa.game_date) as games_with_data
            FROM prospects p
            LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.player_id::text
            WHERE pa.player_id IS NOT NULL
            GROUP BY p.name, p.mlb_player_id, pa.player_id
            ORDER BY games_with_data DESC
        '''))

        prospects_with_data = []
        for row in result:
            prospects_with_data.append({
                'name': row[0],
                'mlb_player_id': row[1],
                'milb_player_id': row[2],
                'games_with_data': row[3]
            })

        print(f"\n=== PROSPECTS WITH MiLB DATA ===")
        print(f"Total prospects with data: {len(prospects_with_data)}")

        # Show top 20
        print("\nTop 20 prospects by games with data:")
        for i, prospect in enumerate(prospects_with_data[:20], 1):
            print(f"{i}. {prospect['name']} - MLB ID: {prospect['mlb_player_id']} - Games: {prospect['games_with_data']}")

        # Check prospects without data
        result = conn.execute(text('''
            SELECT
                p.name,
                p.mlb_player_id,
                p.current_level,
                p.eta_year
            FROM prospects p
            LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.player_id::text
            WHERE p.mlb_player_id IS NOT NULL
                AND pa.player_id IS NULL
            ORDER BY p.name
        '''))

        prospects_without_data = []
        for row in result:
            prospects_without_data.append({
                'name': row[0],
                'mlb_player_id': row[1],
                'level': row[2],
                'eta': row[3]
            })

        print(f"\n=== PROSPECTS WITHOUT MiLB DATA ===")
        print(f"Total prospects without data: {len(prospects_without_data)}")

        # Save to CSV
        if prospects_without_data:
            df = pd.DataFrame(prospects_without_data)
            filename = f'prospects_needing_milb_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            df.to_csv(filename, index=False)
            print(f"\nSaved to: {filename}")

            print("\nFirst 20 prospects needing collection:")
            for i, prospect in enumerate(prospects_without_data[:20], 1):
                print(f"{i}. {prospect['name']} - MLB ID: {prospect['mlb_player_id']} - Level: {prospect['level']}")

def check_collection_gaps():
    """Find gaps in collection by date range"""

    with engine.connect() as conn:
        # Check date coverage for 2021-2025
        result = conn.execute(text('''
            WITH date_coverage AS (
                SELECT
                    EXTRACT(YEAR FROM game_date) as year,
                    EXTRACT(MONTH FROM game_date) as month,
                    COUNT(DISTINCT game_date) as days_with_data,
                    COUNT(DISTINCT player_id) as unique_players,
                    COUNT(*) as total_records
                FROM milb_plate_appearances
                WHERE EXTRACT(YEAR FROM game_date) BETWEEN 2021 AND 2025
                GROUP BY EXTRACT(YEAR FROM game_date), EXTRACT(MONTH FROM game_date)
            )
            SELECT * FROM date_coverage
            ORDER BY year, month
        '''))

        print("\n=== DATA COVERAGE BY MONTH (2021-2025) ===")
        print("Year-Month | Days | Players | Records")
        print("-" * 40)

        current_year = None
        for row in result:
            year = int(row[0])
            month = int(row[1])
            if current_year != year:
                print(f"\n--- {year} ---")
                current_year = year
            print(f"{year}-{month:02d}: {row[2]:3} days, {row[3]:4} players, {row[4]:6} records")

def find_mlb_ids_for_missing_prospects():
    """Try to find MLB IDs for missing prospects"""

    # Read missing prospects
    missing_df = pd.read_csv('missing_prospects_20251017_093027.csv')

    print("\n=== SEARCHING FOR MLB IDs ===")
    print(f"Missing prospects to search: {len(missing_df)}")

    # Create a script to search for these players
    with open('search_missing_prospects.py', 'w') as f:
        f.write('''"""
Search for MLB player IDs for missing prospects
"""
import statsapi
import pandas as pd
from datetime import datetime

def search_player_id(name, team=None):
    """Search for player ID using MLB Stats API"""
    try:
        # Try exact search first
        results = statsapi.lookup_player(name)
        if results:
            return results[0]['id'], results[0]['fullName']

        # Try last name only
        parts = name.split()
        if len(parts) > 1:
            results = statsapi.lookup_player(parts[-1])
            for player in results:
                if player['fullName'].lower() == name.lower():
                    return player['id'], player['fullName']

        return None, None
    except Exception as e:
        print(f"Error searching {name}: {e}")
        return None, None

# Read missing prospects
df = pd.read_csv('missing_prospects_20251017_093027.csv')

results = []
for idx, row in df.iterrows():
    name = row['name']
    team = row.get('team', None)

    mlb_id, found_name = search_player_id(name, team)

    results.append({
        'original_name': name,
        'team': team,
        'mlb_id': mlb_id,
        'found_name': found_name,
        'position': row.get('position', ''),
        'age': row.get('age', ''),
        'level': row.get('level', '')
    })

    print(f"Searched {idx+1}/{len(df)}: {name} -> {mlb_id if mlb_id else 'NOT FOUND'}")

# Save results
results_df = pd.DataFrame(results)
output_file = f'missing_prospects_with_ids_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
results_df.to_csv(output_file, index=False)
print(f"\\nResults saved to: {output_file}")

# Summary
found = results_df[results_df['mlb_id'].notna()]
not_found = results_df[results_df['mlb_id'].isna()]
print(f"\\nFound MLB IDs for: {len(found)} prospects")
print(f"Could not find: {len(not_found)} prospects")
''')

    print("Created search_missing_prospects.py")

if __name__ == "__main__":
    print("=== ANALYZING MiLB COLLECTIONS ===\n")

    # Check overall collections
    check_milb_collections()

    # Match prospects to data
    match_prospects_to_milb_data()

    # Check gaps in collection
    check_collection_gaps()

    # Create script to find MLB IDs
    find_mlb_ids_for_missing_prospects()

    print("\n=== ANALYSIS COMPLETE ===")