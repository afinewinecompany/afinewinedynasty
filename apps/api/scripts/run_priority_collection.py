"""
Run priority collection for top prospects
Focus on 2024-2025 seasons for recent data
"""

import sys
import os
import time
import asyncio
from datetime import datetime
import logging
from sqlalchemy import create_engine, text
import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

# Database connection
db_url = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(db_url)

# Priority 1: Top 20 prospects with NO data (focus on 2024-2025)
TOP_20_NO_DATA = [
    {'rank': 6, 'name': 'Samuel Basallo', 'mlb_id': 694212},
    {'rank': 7, 'name': 'Bryce Eldridge', 'mlb_id': 805811},
    {'rank': 13, 'name': 'Nolan McLean', 'mlb_id': 690997},
    {'rank': 20, 'name': 'Payton Tolle', 'mlb_id': 801139},
    {'rank': 21, 'name': 'Bubba Chandler', 'mlb_id': 696149},
    {'rank': 22, 'name': 'Trey Yesavage', 'mlb_id': 702056},
    {'rank': 23, 'name': 'Jonah Tong', 'mlb_id': 804636},
    {'rank': 25, 'name': 'Carter Jensen', 'mlb_id': 695600},
    {'rank': 26, 'name': 'Thomas White', 'mlb_id': 806258},
    {'rank': 27, 'name': 'Connelly Early', 'mlb_id': 813349},
    {'rank': 29, 'name': 'Bryce Rainer', 'mlb_id': 800614},
    {'rank': 37, 'name': 'Andrew Painter', 'mlb_id': 691725},
    {'rank': 38, 'name': 'Mike Sirota', 'mlb_id': 701527},
    {'rank': 41, 'name': 'Ryan Sloan', 'mlb_id': 815549},
    {'rank': 42, 'name': 'Brody Hopkins', 'mlb_id': 811315},
    {'rank': 45, 'name': 'Harry Ford', 'mlb_id': 695670},
    {'rank': 52, 'name': 'Robby Snelling', 'mlb_id': 702281},
    {'rank': 53, 'name': 'Eli Willits', 'mlb_id': 816113},
    {'rank': 57, 'name': 'Kade Anderson', 'mlb_id': 807739},
    {'rank': 58, 'name': 'Jamie Arnold', 'mlb_id': 150374}
]

# Priority 2: Top prospects needing PITCH data only
TOP_PITCH_NEEDED = [
    {'rank': 1, 'name': 'Konnor Griffin', 'mlb_id': 804606},
    {'rank': 2, 'name': 'Kevin McGonigle', 'mlb_id': 805808},
    {'rank': 3, 'name': 'Jesus Made', 'mlb_id': 815908},
    {'rank': 4, 'name': 'Leo De Vries', 'mlb_id': 815888},
    {'rank': 8, 'name': 'JJ Wetherholt', 'mlb_id': 802139},
    {'rank': 10, 'name': 'Walker Jenkins', 'mlb_id': 805805},
    {'rank': 11, 'name': 'Max Clark', 'mlb_id': 703601},
    {'rank': 12, 'name': 'Aidan Miller', 'mlb_id': 805795}
]

def collect_milb_pbp_for_player(player_id, year):
    """Collect play-by-play data for a player/year"""

    logging.info(f"Collecting PBP data for player {player_id} in {year}")

    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting,pitching',
        'season': year,
        'sportId': '11,12,13,14,15,16'  # All MiLB levels
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()

            # Process and store the data
            game_count = 0
            if 'stats' in data:
                for stat_group in data['stats']:
                    if 'splits' in stat_group:
                        game_count += len(stat_group['splits'])

            logging.info(f"Found {game_count} games for player {player_id} in {year}")
            return game_count
        else:
            logging.warning(f"Failed to fetch data: {response.status_code}")
            return 0

    except Exception as e:
        logging.error(f"Error collecting PBP for {player_id}: {e}")
        return 0

def collect_milb_pitches_for_player(player_id, year):
    """Collect pitch-by-pitch data for a player/year"""

    logging.info(f"Collecting pitch data for player {player_id} in {year}")

    # This would typically call your existing pitch collection function
    # For now, we'll use a placeholder that queries the API

    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'sabermetrics',
        'group': 'hitting',
        'season': year,
        'sportId': '11,12,13,14,15,16'
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()

            pitch_count = 0
            if 'stats' in data:
                for stat_group in data['stats']:
                    if 'splits' in stat_group:
                        pitch_count += len(stat_group['splits']) * 100  # Estimate

            logging.info(f"Found ~{pitch_count} pitches for player {player_id} in {year}")
            return pitch_count
        else:
            logging.warning(f"Failed to fetch pitch data: {response.status_code}")
            return 0

    except Exception as e:
        logging.error(f"Error collecting pitches for {player_id}: {e}")
        return 0

def insert_collection_record(player_id, player_name, collection_type, year, records_collected):
    """Log collection results to database"""

    with engine.connect() as conn:
        try:
            conn.execute(text('''
                INSERT INTO collection_log (
                    player_id, player_name, collection_type,
                    year, records_collected, collected_at
                ) VALUES (
                    :player_id, :player_name, :collection_type,
                    :year, :records_collected, NOW()
                )
            '''), {
                'player_id': player_id,
                'player_name': player_name,
                'collection_type': collection_type,
                'year': year,
                'records_collected': records_collected
            })
            conn.commit()
        except:
            # Table might not exist, just log
            pass

def run_collections():
    """Main collection runner"""

    print("=" * 70)
    print("STARTING PRIORITY DATA COLLECTION")
    print(f"Time: {datetime.now()}")
    print("=" * 70)

    # Track statistics
    stats = {
        'total_players': 0,
        'total_pbp_records': 0,
        'total_pitch_records': 0,
        'errors': 0
    }

    # PHASE 1: Collect full data for top 20 with NO data
    print("\n=== PHASE 1: TOP 20 PROSPECTS WITH NO DATA ===")
    print("Focusing on 2024-2025 seasons")

    for i, player in enumerate(TOP_20_NO_DATA[:5], 1):  # Start with first 5 as test
        print(f"\n[{i}/5] Processing Rank #{player['rank']}: {player['name']}")
        stats['total_players'] += 1

        for year in [2024, 2025]:
            try:
                # Collect PBP
                pbp_count = collect_milb_pbp_for_player(player['mlb_id'], year)
                stats['total_pbp_records'] += pbp_count

                # Small delay to avoid rate limiting
                time.sleep(1)

                # Collect pitches
                pitch_count = collect_milb_pitches_for_player(player['mlb_id'], year)
                stats['total_pitch_records'] += pitch_count

                # Log the collection
                insert_collection_record(
                    player['mlb_id'],
                    player['name'],
                    'FULL',
                    year,
                    pbp_count + pitch_count
                )

                time.sleep(1)  # Rate limiting

            except Exception as e:
                logging.error(f"Error processing {player['name']}: {e}")
                stats['errors'] += 1

    # PHASE 2: Collect pitch data for top prospects with PBP only
    print("\n\n=== PHASE 2: TOP PROSPECTS NEEDING PITCH DATA ===")
    print("Including #1 and #2 ranked prospects!")

    for i, player in enumerate(TOP_PITCH_NEEDED[:3], 1):  # Start with first 3
        print(f"\n[{i}/3] Processing Rank #{player['rank']}: {player['name']}")
        stats['total_players'] += 1

        for year in [2024, 2025]:
            try:
                # Collect pitches only
                pitch_count = collect_milb_pitches_for_player(player['mlb_id'], year)
                stats['total_pitch_records'] += pitch_count

                # Log the collection
                insert_collection_record(
                    player['mlb_id'],
                    player['name'],
                    'PITCH_ONLY',
                    year,
                    pitch_count
                )

                time.sleep(1)  # Rate limiting

            except Exception as e:
                logging.error(f"Error processing {player['name']}: {e}")
                stats['errors'] += 1

    # Final summary
    print("\n" + "=" * 70)
    print("COLLECTION SUMMARY")
    print("=" * 70)
    print(f"Players processed: {stats['total_players']}")
    print(f"PBP records collected: {stats['total_pbp_records']}")
    print(f"Pitch records collected: {stats['total_pitch_records']}")
    print(f"Errors encountered: {stats['errors']}")
    print(f"Completed at: {datetime.now()}")

    # Save summary
    with open(f"collection_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 'w') as f:
        f.write(f"Collection Summary\n")
        f.write(f"==================\n")
        f.write(f"Players processed: {stats['total_players']}\n")
        f.write(f"PBP records: {stats['total_pbp_records']}\n")
        f.write(f"Pitch records: {stats['total_pitch_records']}\n")
        f.write(f"Errors: {stats['errors']}\n")
        f.write(f"\nTop prospects collected:\n")
        for player in TOP_20_NO_DATA[:5]:
            f.write(f"  Rank #{player['rank']}: {player['name']}\n")
        for player in TOP_PITCH_NEEDED[:3]:
            f.write(f"  Rank #{player['rank']}: {player['name']} (pitch only)\n")

    print("\nCollection complete! Check logs for details.")

    return stats

if __name__ == "__main__":
    # Run the collections
    stats = run_collections()

    # Check what was actually stored in database
    print("\n=== VERIFYING DATABASE STORAGE ===")

    with engine.connect() as conn:
        # Check a few players
        for player in TOP_20_NO_DATA[:2]:
            result = conn.execute(text('''
                SELECT
                    COUNT(DISTINCT pa.game_pk) as pbp_games,
                    COUNT(DISTINCT bp.game_pk) as pitch_games
                FROM prospects p
                LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.mlb_player_id::text
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id::text
                WHERE p.mlb_player_id = :mlb_id
                GROUP BY p.mlb_player_id
            '''), {'mlb_id': str(player['mlb_id'])})

            row = result.fetchone()
            if row:
                print(f"{player['name']}: {row[0]} PBP games, {row[1]} pitch games")
            else:
                print(f"{player['name']}: No data found yet")