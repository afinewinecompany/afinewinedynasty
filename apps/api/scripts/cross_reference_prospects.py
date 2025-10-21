"""
Cross-reference MLB top prospects CSV with database prospects
Find missing prospects and match them to MLB player IDs
"""

import pandas as pd
from sqlalchemy import create_engine, text
import json
from datetime import datetime

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

def normalize_name(name):
    """Normalize names for comparison"""
    if pd.isna(name) or name is None:
        return ""
    return name.strip().lower()

def find_missing_prospects():
    """Find prospects in CSV that are not in database"""

    # Read CSV file - skip the first row which contains extra headers
    csv_path = r'C:\Users\lilra\Downloads\mlb-top-prospects.csv'
    df = pd.read_csv(csv_path, encoding='utf-8-sig', skiprows=1)

    print(f"Total prospects in CSV: {len(df)}")
    print(f"CSV columns: {df.columns.tolist()}")

    # Get unique prospect names from CSV
    csv_prospects = df['Prospect'].unique()
    csv_prospects_normalized = {normalize_name(name): name for name in csv_prospects}

    # Get all prospects from database
    with engine.connect() as conn:
        result = conn.execute(text('''
            SELECT DISTINCT name, mlb_player_id, mlb_id, id
            FROM prospects
            WHERE name IS NOT NULL
            ORDER BY name
        '''))

        db_prospects = {}
        for row in result:
            normalized = normalize_name(row[0])
            db_prospects[normalized] = {
                'name': row[0],
                'mlb_player_id': row[1],
                'mlb_id': row[2],
                'id': row[3]
            }

    print(f"\nProspects in database: {len(db_prospects)}")

    # Find missing prospects
    missing_prospects = []
    matched_prospects = []

    for norm_name, original_name in csv_prospects_normalized.items():
        if norm_name not in db_prospects:
            # Get additional data from CSV
            prospect_data = df[df['Prospect'] == original_name].iloc[0]
            missing_prospects.append({
                'name': original_name,
                'team': prospect_data.get('Team', None),
                'position': prospect_data.get('Pos', None),
                'age': prospect_data.get('Age', None),
                'eta': prospect_data.get('ETA', None),
                'level': prospect_data.get('Level', None),
                'rank': prospect_data.get('Rank', None)
            })
        else:
            matched_prospects.append({
                'csv_name': original_name,
                'db_name': db_prospects[norm_name]['name'],
                'mlb_player_id': db_prospects[norm_name]['mlb_player_id'],
                'prospect_id': db_prospects[norm_name]['id']
            })

    print(f"\n=== ANALYSIS RESULTS ===")
    print(f"Matched prospects: {len(matched_prospects)}")
    print(f"Missing prospects: {len(missing_prospects)}")

    # Save results to files
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save missing prospects
    missing_df = pd.DataFrame(missing_prospects)
    missing_file = f'missing_prospects_{timestamp}.csv'
    missing_df.to_csv(missing_file, index=False)
    print(f"\nMissing prospects saved to: {missing_file}")

    # Save matched prospects
    matched_df = pd.DataFrame(matched_prospects)
    matched_file = f'matched_prospects_{timestamp}.csv'
    matched_df.to_csv(matched_file, index=False)
    print(f"Matched prospects saved to: {matched_file}")

    # Show first 20 missing prospects
    print("\n=== FIRST 20 MISSING PROSPECTS ===")
    for i, prospect in enumerate(missing_prospects[:20], 1):
        print(f"{i}. {prospect['name']} - {prospect['team']} - {prospect['position']} - Level: {prospect['level']}")

    return missing_prospects, matched_prospects

def check_collections_coverage():
    """Check which prospects have play-by-play and pitch-by-pitch data"""

    with engine.connect() as conn:
        # Check prospects with collections
        result = conn.execute(text('''
            SELECT
                p.name,
                p.mlb_player_id,
                COUNT(DISTINCT pbp.game_pk) as play_by_play_games,
                COUNT(DISTINCT pp.game_pk) as pitch_by_pitch_games,
                MIN(pbp.game_date) as earliest_pbp,
                MAX(pbp.game_date) as latest_pbp,
                MIN(pp.game_date) as earliest_pp,
                MAX(pp.game_date) as latest_pp
            FROM prospects p
            LEFT JOIN play_by_play pbp ON p.mlb_player_id::text = pbp.batter_id::text
                OR p.mlb_player_id::text = pbp.pitcher_id::text
            LEFT JOIN pitch_by_pitch pp ON p.mlb_player_id::text = pp.batter_id::text
                OR p.mlb_player_id::text = pp.pitcher_id::text
            WHERE p.mlb_player_id IS NOT NULL
            GROUP BY p.name, p.mlb_player_id
            HAVING COUNT(DISTINCT pbp.game_pk) > 0 OR COUNT(DISTINCT pp.game_pk) > 0
            ORDER BY p.name
        '''))

        covered_prospects = []
        for row in result:
            covered_prospects.append({
                'name': row[0],
                'mlb_player_id': row[1],
                'play_by_play_games': row[2],
                'pitch_by_pitch_games': row[3],
                'earliest_pbp': row[4],
                'latest_pbp': row[5],
                'earliest_pp': row[6],
                'latest_pp': row[7]
            })

        print(f"\n=== COLLECTION COVERAGE ===")
        print(f"Prospects with data: {len(covered_prospects)}")

        # Get prospects without any data
        result = conn.execute(text('''
            SELECT
                p.name,
                p.mlb_player_id
            FROM prospects p
            LEFT JOIN play_by_play pbp ON p.mlb_player_id::text = pbp.batter_id::text
                OR p.mlb_player_id::text = pbp.pitcher_id::text
            LEFT JOIN pitch_by_pitch pp ON p.mlb_player_id::text = pp.batter_id::text
                OR p.mlb_player_id::text = pp.pitcher_id::text
            WHERE p.mlb_player_id IS NOT NULL
            GROUP BY p.name, p.mlb_player_id
            HAVING COUNT(DISTINCT pbp.game_pk) = 0 AND COUNT(DISTINCT pp.game_pk) = 0
            ORDER BY p.name
        '''))

        no_data_prospects = []
        for row in result:
            no_data_prospects.append({
                'name': row[0],
                'mlb_player_id': row[1]
            })

        print(f"Prospects without any data: {len(no_data_prospects)}")

        return covered_prospects, no_data_prospects

if __name__ == "__main__":
    print("=== CROSS-REFERENCING PROSPECTS ===")
    missing, matched = find_missing_prospects()

    print("\n=== CHECKING COLLECTION COVERAGE ===")
    covered, no_data = check_collections_coverage()

    # Save no data prospects for collection
    if no_data:
        no_data_df = pd.DataFrame(no_data)
        no_data_file = f'prospects_needing_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        no_data_df.to_csv(no_data_file, index=False)
        print(f"\nProspects needing collection saved to: {no_data_file}")

        print("\nFirst 20 prospects needing data collection:")
        for i, prospect in enumerate(no_data[:20], 1):
            print(f"{i}. {prospect['name']} - MLB ID: {prospect['mlb_player_id']}")