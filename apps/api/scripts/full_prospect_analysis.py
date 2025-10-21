"""
Complete analysis of prospects, collections, and gaps
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import json

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

def analyze_milb_collections():
    """Analyze MiLB pitch-by-pitch and play-by-play data"""

    with engine.connect() as conn:
        # 1. Plate Appearances Analysis
        result = conn.execute(text('''
            SELECT
                COUNT(DISTINCT mlb_player_id) as unique_players,
                COUNT(*) as total_plate_appearances,
                MIN(game_date) as earliest_date,
                MAX(game_date) as latest_date,
                COUNT(DISTINCT game_date) as unique_dates,
                COUNT(DISTINCT game_pk) as unique_games
            FROM milb_plate_appearances
        '''))

        row = result.fetchone()
        print("=== MiLB PLATE APPEARANCES (Play-by-Play) ===")
        print(f"Unique players: {row[0]}")
        print(f"Total plate appearances: {row[1]}")
        print(f"Unique games: {row[5]}")
        print(f"Date range: {row[2]} to {row[3]}")

        # By year breakdown
        result = conn.execute(text('''
            SELECT
                season,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as plate_appearances,
                COUNT(DISTINCT game_pk) as games
            FROM milb_plate_appearances
            WHERE season BETWEEN 2021 AND 2025
            GROUP BY season
            ORDER BY season
        '''))

        print("\n=== PLAY-BY-PLAY BY YEAR ===")
        pbp_years = {}
        for row in result:
            pbp_years[row[0]] = row[1]
            print(f"{row[0]}: {row[1]} players, {row[2]} PAs, {row[3]} games")

        # 2. Pitcher Pitches Analysis
        result = conn.execute(text('''
            SELECT
                COUNT(DISTINCT mlb_pitcher_id) as unique_pitchers,
                COUNT(*) as total_pitches,
                MIN(game_date) as earliest_date,
                MAX(game_date) as latest_date,
                COUNT(DISTINCT game_pk) as unique_games
            FROM milb_pitcher_pitches
        '''))

        row = result.fetchone()
        print("\n=== MiLB PITCHER PITCHES (Pitch-by-Pitch) ===")
        print(f"Unique pitchers: {row[0]}")
        print(f"Total pitches thrown: {row[1]}")
        print(f"Unique games: {row[4]}")
        print(f"Date range: {row[2]} to {row[3]}")

        # 3. Batter Pitches Analysis
        result = conn.execute(text('''
            SELECT
                COUNT(DISTINCT mlb_batter_id) as unique_batters,
                COUNT(*) as total_pitches,
                MIN(game_date) as earliest_date,
                MAX(game_date) as latest_date,
                COUNT(DISTINCT game_pk) as unique_games
            FROM milb_batter_pitches
        '''))

        row = result.fetchone()
        print("\n=== MiLB BATTER PITCHES (Pitch-by-Pitch) ===")
        print(f"Unique batters: {row[0]}")
        print(f"Total pitches seen: {row[1]}")
        print(f"Unique games: {row[4]}")
        print(f"Date range: {row[2]} to {row[3]}")

        # By year breakdown for pitches
        result = conn.execute(text('''
            SELECT
                season,
                COUNT(DISTINCT mlb_batter_id) as batters,
                COUNT(DISTINCT mlb_pitcher_id) as pitchers,
                COUNT(*) as pitches,
                COUNT(DISTINCT game_pk) as games
            FROM milb_batter_pitches
            WHERE season BETWEEN 2021 AND 2025
            GROUP BY season
            ORDER BY season
        '''))

        print("\n=== PITCH-BY-PITCH BY YEAR ===")
        pitch_years = {}
        for row in result:
            pitch_years[row[0]] = {'batters': row[1], 'pitchers': row[2]}
            print(f"{row[0]}: {row[1]} batters, {row[2]} pitchers, {row[3]} pitches, {row[4]} games")

        return pbp_years, pitch_years


def match_prospects_to_collections():
    """Match prospects to their collection data"""

    with engine.connect() as conn:
        # Match prospects to play-by-play data
        result = conn.execute(text('''
            WITH prospect_pbp AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    p.current_level,
                    COUNT(DISTINCT pa.game_pk) as pbp_games,
                    MIN(pa.game_date) as first_pbp,
                    MAX(pa.game_date) as last_pbp,
                    SUM(CASE WHEN pa.season = 2021 THEN 1 ELSE 0 END) as pbp_2021,
                    SUM(CASE WHEN pa.season = 2022 THEN 1 ELSE 0 END) as pbp_2022,
                    SUM(CASE WHEN pa.season = 2023 THEN 1 ELSE 0 END) as pbp_2023,
                    SUM(CASE WHEN pa.season = 2024 THEN 1 ELSE 0 END) as pbp_2024,
                    SUM(CASE WHEN pa.season = 2025 THEN 1 ELSE 0 END) as pbp_2025
                FROM prospects p
                LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.mlb_player_id::text
                WHERE p.mlb_player_id IS NOT NULL
                GROUP BY p.name, p.mlb_player_id, p.current_level
            )
            SELECT * FROM prospect_pbp
            ORDER BY pbp_games DESC NULLS LAST
        '''))

        prospects_data = []
        for row in result:
            prospects_data.append({
                'name': row[0],
                'mlb_player_id': row[1],
                'level': row[2],
                'pbp_games': row[3] or 0,
                'first_pbp': row[4],
                'last_pbp': row[5],
                'pbp_2021': row[6] or 0,
                'pbp_2022': row[7] or 0,
                'pbp_2023': row[8] or 0,
                'pbp_2024': row[9] or 0,
                'pbp_2025': row[10] or 0
            })

        # Add pitch-by-pitch data
        result = conn.execute(text('''
            SELECT
                p.mlb_player_id,
                COUNT(DISTINCT bp.game_pk) as pitch_games,
                MIN(bp.game_date) as first_pitch,
                MAX(bp.game_date) as last_pitch
            FROM prospects p
            LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id::text
            WHERE p.mlb_player_id IS NOT NULL AND bp.game_pk IS NOT NULL
            GROUP BY p.mlb_player_id
        '''))

        pitch_data = {}
        for row in result:
            pitch_data[row[0]] = {
                'pitch_games': row[1],
                'first_pitch': row[2],
                'last_pitch': row[3]
            }

        # Combine data
        for prospect in prospects_data:
            mlb_id = prospect['mlb_player_id']
            if mlb_id in pitch_data:
                prospect['pitch_games'] = pitch_data[mlb_id]['pitch_games']
                prospect['first_pitch'] = pitch_data[mlb_id]['first_pitch']
                prospect['last_pitch'] = pitch_data[mlb_id]['last_pitch']
            else:
                prospect['pitch_games'] = 0
                prospect['first_pitch'] = None
                prospect['last_pitch'] = None

        # Categorize prospects
        has_both = [p for p in prospects_data if p['pbp_games'] > 0 and p['pitch_games'] > 0]
        pbp_only = [p for p in prospects_data if p['pbp_games'] > 0 and p['pitch_games'] == 0]
        pitch_only = [p for p in prospects_data if p['pbp_games'] == 0 and p['pitch_games'] > 0]
        no_data = [p for p in prospects_data if p['pbp_games'] == 0 and p['pitch_games'] == 0]

        print("\n=== PROSPECT DATA COVERAGE ===")
        print(f"Prospects with both PBP and Pitch data: {len(has_both)}")
        print(f"Prospects with PBP only: {len(pbp_only)}")
        print(f"Prospects with Pitch only: {len(pitch_only)}")
        print(f"Prospects with NO data: {len(no_data)}")

        return prospects_data, has_both, pbp_only, pitch_only, no_data


def analyze_csv_prospects():
    """Analyze prospects from CSV and find who needs collection"""

    # Read CSV prospects
    csv_path = r'C:\Users\lilra\Downloads\mlb-top-prospects.csv'
    df = pd.read_csv(csv_path, encoding='utf-8-sig', skiprows=1)

    # Read missing prospects we already found
    missing_df = pd.read_csv('missing_prospects_20251017_093027.csv')

    print("\n=== CSV PROSPECT ANALYSIS ===")
    print(f"Total prospects in CSV: {len(df)}")
    print(f"Already identified as missing from DB: {len(missing_df)}")

    # Get top 100 prospects from CSV
    top_100 = df.head(100)

    with engine.connect() as conn:
        collection_needs = []

        for idx, row in top_100.iterrows():
            prospect_name = row['Prospect']
            rank = row['Rank']
            level = row['Level']

            # Check if this prospect has data
            result = conn.execute(text('''
                SELECT
                    p.mlb_player_id,
                    COUNT(DISTINCT pa.game_pk) as pbp_games,
                    COUNT(DISTINCT bp.game_pk) as pitch_games
                FROM prospects p
                LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.mlb_player_id::text
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id::text
                WHERE LOWER(p.name) = LOWER(:name)
                GROUP BY p.mlb_player_id
            '''), {'name': prospect_name})

            data = result.fetchone()

            if not data or not data[0]:
                # Not in database
                collection_needs.append({
                    'rank': rank,
                    'name': prospect_name,
                    'level': level,
                    'team': row['Team'],
                    'status': 'NOT IN DATABASE',
                    'mlb_id': None,
                    'pbp_games': 0,
                    'pitch_games': 0
                })
            else:
                pbp_games = data[1] or 0
                pitch_games = data[2] or 0

                if pbp_games == 0 and pitch_games == 0:
                    collection_needs.append({
                        'rank': rank,
                        'name': prospect_name,
                        'level': level,
                        'team': row['Team'],
                        'status': 'NO DATA',
                        'mlb_id': data[0],
                        'pbp_games': 0,
                        'pitch_games': 0
                    })
                elif pbp_games == 0:
                    collection_needs.append({
                        'rank': rank,
                        'name': prospect_name,
                        'level': level,
                        'team': row['Team'],
                        'status': 'NEEDS PBP',
                        'mlb_id': data[0],
                        'pbp_games': 0,
                        'pitch_games': pitch_games
                    })
                elif pitch_games == 0:
                    collection_needs.append({
                        'rank': rank,
                        'name': prospect_name,
                        'level': level,
                        'team': row['Team'],
                        'status': 'NEEDS PITCH',
                        'mlb_id': data[0],
                        'pbp_games': pbp_games,
                        'pitch_games': 0
                    })

        print(f"\nTop 100 prospects needing data collection: {len(collection_needs)}")

        if collection_needs:
            # Save to CSV
            needs_df = pd.DataFrame(collection_needs)
            filename = f'top_100_collection_needs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            needs_df.to_csv(filename, index=False)
            print(f"Saved to: {filename}")

            # Show summary
            print("\n=== COLLECTION NEEDS SUMMARY ===")
            for status in ['NOT IN DATABASE', 'NO DATA', 'NEEDS PBP', 'NEEDS PITCH']:
                count = len([n for n in collection_needs if n['status'] == status])
                if count > 0:
                    print(f"{status}: {count} prospects")

            # Show first 20
            print("\n=== FIRST 20 PROSPECTS NEEDING COLLECTION ===")
            for i, need in enumerate(collection_needs[:20], 1):
                print(f"{i}. Rank #{need['rank']}: {need['name']} ({need['team']}) - {need['status']}")

        return collection_needs


def generate_collection_script():
    """Generate a script to collect missing data"""

    print("\n=== GENERATING COLLECTION SCRIPT ===")

    script_content = '''"""
Collect MiLB data for missing prospects
Auto-generated collection script
"""

import sys
import os
import asyncio
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_milb_pbp import collect_player_season_pbp
from scripts.collect_milb_pitches import collect_player_season_pitches

async def collect_prospect_data(mlb_player_id, name, start_year=2021, end_year=2025):
    """Collect all data for a prospect"""

    print(f"\\nCollecting data for {name} (ID: {mlb_player_id})")

    for year in range(start_year, end_year + 1):
        print(f"  Year {year}...")

        try:
            # Collect play-by-play
            pbp_count = await collect_player_season_pbp(mlb_player_id, year)
            print(f"    PBP: {pbp_count} plate appearances")

            # Collect pitch-by-pitch
            pitch_count = await collect_player_season_pitches(mlb_player_id, year)
            print(f"    Pitches: {pitch_count} pitches")

            # Small delay between years
            await asyncio.sleep(1)

        except Exception as e:
            print(f"    Error: {e}")

async def main():
    # Read prospects needing collection
    needs_df = pd.read_csv('top_100_collection_needs_*.csv')

    # Filter for prospects that need data
    to_collect = needs_df[needs_df['status'].isin(['NO DATA', 'NEEDS PBP', 'NEEDS PITCH'])]
    to_collect = to_collect[to_collect['mlb_id'].notna()]

    print(f"Collecting data for {len(to_collect)} prospects...")

    for idx, row in to_collect.iterrows():
        await collect_prospect_data(
            mlb_player_id=int(row['mlb_id']),
            name=row['name']
        )

        # Delay between players
        await asyncio.sleep(2)

    print("\\nCollection complete!")

if __name__ == "__main__":
    asyncio.run(main())
'''

    with open('collect_missing_prospects.py', 'w') as f:
        f.write(script_content)

    print("Generated: collect_missing_prospects.py")


def main():
    print("=" * 60)
    print("COMPREHENSIVE PROSPECT DATA ANALYSIS")
    print("=" * 60)

    # 1. Analyze current MiLB collections
    print("\n[1/4] Analyzing MiLB Collections...")
    pbp_years, pitch_years = analyze_milb_collections()

    # 2. Match prospects to their collection data
    print("\n[2/4] Matching Prospects to Collections...")
    all_prospects, has_both, pbp_only, pitch_only, no_data = match_prospects_to_collections()

    # 3. Analyze CSV prospects
    print("\n[3/4] Analyzing Top 100 Prospects from CSV...")
    collection_needs = analyze_csv_prospects()

    # 4. Generate collection script
    print("\n[4/4] Generating Collection Script...")
    generate_collection_script()

    # Final summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # Identify gaps
    print("\n=== DATA GAPS BY YEAR ===")
    for year in range(2021, 2026):
        pbp_count = pbp_years.get(year, 0)
        pitch_count = pitch_years.get(year, {}).get('batters', 0)
        print(f"{year}: {pbp_count} players with PBP, {pitch_count} batters with pitch data")

    print("\n=== NEXT STEPS ===")
    print("1. Add missing prospects to database (79 prospects)")
    print("2. Find MLB IDs for missing prospects")
    print("3. Run collection script for prospects with IDs")
    print("4. Focus on Top 100 prospects first")
    print("5. Prioritize 2024-2025 data for recent prospects")

    # Save no-data prospects
    if no_data:
        no_data_df = pd.DataFrame(no_data)
        filename = f'prospects_with_no_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        no_data_df.to_csv(filename, index=False)
        print(f"\nProspects with no data saved to: {filename}")

    print("\n=== ANALYSIS COMPLETE ===")


if __name__ == "__main__":
    main()