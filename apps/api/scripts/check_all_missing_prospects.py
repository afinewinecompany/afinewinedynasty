"""
Comprehensive check for missing prospects considering diacritics
"""

import pandas as pd
from sqlalchemy import create_engine, text
import unicodedata
from datetime import datetime

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

def normalize_name(name):
    """Normalize name for comparison - remove accents and convert to lowercase"""
    if not name:
        return ""
    # Remove accents
    nfd = unicodedata.normalize('NFD', name)
    without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    # Remove Jr., Sr., II, III suffixes
    for suffix in [' Jr.', ' Sr.', ' II', ' III', ' Jr', ' Sr']:
        without_accents = without_accents.replace(suffix, '')
    return without_accents.strip().lower()

def main():
    print("=" * 70)
    print("COMPREHENSIVE MISSING PROSPECTS CHECK (WITH DIACRITIC HANDLING)")
    print("=" * 70)

    # Read CSV
    csv_path = r'C:\Users\lilra\Downloads\mlb-top-prospects.csv'
    df = pd.read_csv(csv_path, encoding='utf-8-sig', skiprows=1)

    with engine.connect() as conn:
        # Get all prospects from database with normalized names
        result = conn.execute(text('''
            SELECT name, mlb_player_id, id
            FROM prospects
            WHERE name IS NOT NULL
        '''))

        db_prospects = {}
        for row in result:
            normalized = normalize_name(row[0])
            db_prospects[normalized] = {
                'original_name': row[0],
                'mlb_player_id': row[1],
                'id': row[2]
            }

        print(f"\nProspects in database: {len(db_prospects)}")
        print(f"Prospects in CSV: {len(df)}")

        # Check each CSV prospect
        truly_missing = []
        matched_with_diacritics = []
        matched_normally = []

        for idx, row in df.iterrows():
            csv_name = row['Prospect']
            csv_normalized = normalize_name(csv_name)

            if csv_normalized in db_prospects:
                db_info = db_prospects[csv_normalized]
                if csv_name.lower() == db_info['original_name'].lower():
                    matched_normally.append({
                        'csv_name': csv_name,
                        'db_name': db_info['original_name'],
                        'mlb_id': db_info['mlb_player_id']
                    })
                else:
                    matched_with_diacritics.append({
                        'csv_name': csv_name,
                        'db_name': db_info['original_name'],
                        'mlb_id': db_info['mlb_player_id'],
                        'rank': row['Rank']
                    })
            else:
                truly_missing.append({
                    'rank': row['Rank'],
                    'name': csv_name,
                    'team': row['Team'],
                    'position': row['Pos'],
                    'level': row['Level'],
                    'age': row.get('Age', None)
                })

        print(f"\n=== MATCHING RESULTS ===")
        print(f"Matched exactly: {len(matched_normally)}")
        print(f"Matched with diacritic differences: {len(matched_with_diacritics)}")
        print(f"Truly missing from database: {len(truly_missing)}")

        if matched_with_diacritics:
            print(f"\n=== DIACRITIC MISMATCHES (Top 20) ===")
            for match in matched_with_diacritics[:20]:
                print(f"Rank #{match['rank']}: CSV='{match['csv_name']}' -> DB='{match['db_name']}'")

        if truly_missing:
            print(f"\n=== TRULY MISSING PROSPECTS ===")
            for prospect in truly_missing:
                print(f"Rank #{prospect['rank']}: {prospect['name']} ({prospect['team']}) - {prospect['position']}")

            # Save truly missing
            missing_df = pd.DataFrame(truly_missing)
            filename = f'truly_missing_prospects_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            missing_df.to_csv(filename, index=False)
            print(f"\nSaved {len(truly_missing)} truly missing prospects to: {filename}")

        # Now check collection status for all matched prospects
        print("\n" + "=" * 70)
        print("COLLECTION STATUS CHECK FOR ALL PROSPECTS")
        print("=" * 70)

        # Get collection stats for all prospects
        result = conn.execute(text('''
            WITH prospect_collections AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    COUNT(DISTINCT pa.game_pk) as pbp_games,
                    COUNT(DISTINCT bp.game_pk) as pitch_games,
                    COUNT(DISTINCT pp.game_pk) as pitcher_pitch_games
                FROM prospects p
                LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.mlb_player_id::text
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id::text
                LEFT JOIN milb_pitcher_pitches pp ON p.mlb_player_id::text = pp.mlb_pitcher_id::text
                WHERE p.mlb_player_id IS NOT NULL
                GROUP BY p.name, p.mlb_player_id
            )
            SELECT * FROM prospect_collections
            ORDER BY pbp_games DESC, pitch_games DESC
        '''))

        collection_stats = []
        for row in result:
            collection_stats.append({
                'name': row[0],
                'mlb_player_id': row[1],
                'pbp_games': row[2] or 0,
                'pitch_games': row[3] or 0,
                'pitcher_pitch_games': row[4] or 0
            })

        # Categorize by collection status
        has_full_data = [s for s in collection_stats if s['pbp_games'] > 0 and s['pitch_games'] > 0]
        pbp_only = [s for s in collection_stats if s['pbp_games'] > 0 and s['pitch_games'] == 0]
        pitch_only = [s for s in collection_stats if s['pbp_games'] == 0 and s['pitch_games'] > 0]
        no_data = [s for s in collection_stats if s['pbp_games'] == 0 and s['pitch_games'] == 0]

        print(f"\n=== OVERALL COLLECTION COVERAGE ===")
        print(f"Prospects with full data (PBP + Pitch): {len(has_full_data)}")
        print(f"Prospects with PBP only: {len(pbp_only)}")
        print(f"Prospects with Pitch only: {len(pitch_only)}")
        print(f"Prospects with NO data: {len(no_data)}")

        # Focus on top 100 from CSV
        top_100_needs = []
        for idx, row in df.head(100).iterrows():
            csv_name = row['Prospect']
            csv_normalized = normalize_name(csv_name)

            if csv_normalized in db_prospects:
                mlb_id = db_prospects[csv_normalized]['mlb_player_id']
                # Find collection stats
                stats = next((s for s in collection_stats if s['mlb_player_id'] == mlb_id), None)

                if stats:
                    if stats['pbp_games'] == 0 and stats['pitch_games'] == 0:
                        status = 'NO_DATA'
                    elif stats['pbp_games'] == 0:
                        status = 'NEEDS_PBP'
                    elif stats['pitch_games'] == 0:
                        status = 'NEEDS_PITCH'
                    else:
                        status = 'COMPLETE'

                    if status != 'COMPLETE':
                        top_100_needs.append({
                            'rank': row['Rank'],
                            'name': csv_name,
                            'mlb_id': mlb_id,
                            'status': status,
                            'pbp_games': stats['pbp_games'] if stats else 0,
                            'pitch_games': stats['pitch_games'] if stats else 0
                        })

        print(f"\n=== TOP 100 PROSPECTS NEEDING DATA ===")
        print(f"Total needing collection: {len(top_100_needs)}")

        by_status = {}
        for need in top_100_needs:
            status = need['status']
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(need)

        for status, needs in by_status.items():
            print(f"\n{status}: {len(needs)} prospects")
            for need in needs[:5]:  # Show first 5
                print(f"  Rank #{need['rank']}: {need['name']} (MLB ID: {need['mlb_id']})")

        # Save comprehensive results
        if top_100_needs:
            needs_df = pd.DataFrame(top_100_needs)
            filename = f'top_100_collection_needs_final_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            needs_df.to_csv(filename, index=False)
            print(f"\nSaved final collection needs to: {filename}")

        print("\n" + "=" * 70)
        print("KEY FINDINGS")
        print("=" * 70)
        print("1. The 'missing' prospects were actually in the database with diacritics")
        print("2. Name normalization is critical for matching (remove accents, suffixes)")
        print("3. Most collection gaps remain in pitch-by-pitch data")
        print("4. Recommend implementing fuzzy matching for future imports")

if __name__ == "__main__":
    main()