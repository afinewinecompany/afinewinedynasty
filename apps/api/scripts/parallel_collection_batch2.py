"""
Parallel collection for additional prospects (ranks 31-50)
Run this while other collection is happening
"""

import requests
import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(f'parallel_batch2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Ranks 31-50 prospects (you would need to add the actual MLB IDs)
BATCH_2_PROSPECTS = [
    {'rank': 31, 'name': 'Carson Benge', 'mlb_id': 701807},
    {'rank': 32, 'name': 'Josue De Paula', 'mlb_id': 800543},
    {'rank': 33, 'name': 'Zyhir Hope', 'mlb_id': 807737},
    {'rank': 34, 'name': 'Ryan Waldschmidt', 'mlb_id': 801830},
    {'rank': 35, 'name': 'Cooper Pratt', 'mlb_id': 806198},
    {'rank': 36, 'name': 'Kaelen Culpepper', 'mlb_id': 701785},
    {'rank': 37, 'name': 'Andrew Painter', 'mlb_id': 691725},
    {'rank': 38, 'name': 'Mike Sirota', 'mlb_id': 701527},
    {'rank': 39, 'name': 'Braden Montgomery', 'mlb_id': 695731},
    {'rank': 40, 'name': 'Ralphy Velazquez', 'mlb_id': 806252},
]

def quick_collect(player_id, name, rank):
    """Quick collection of recent games"""

    logger.info(f"Quick collect for Rank #{rank}: {name}")

    with engine.begin() as conn:
        total_pas = 0

        # Just get 2025 games for speed
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'gameLog',
            'season': 2025,
            'group': 'hitting,pitching',
            'sportIds': '11,12,13,14,15,16'
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()

                games = []
                for stat_group in data.get('stats', []):
                    for split in stat_group.get('splits', []):
                        game = split.get('game', {})
                        if game.get('gamePk'):
                            games.append({
                                'pk': game['gamePk'],
                                'date': split.get('date')
                            })

                logger.info(f"  Found {len(games)} games in 2025")

                # Process first 5 games quickly
                for game in games[:5]:
                    # Get PBP
                    pbp_url = f"https://statsapi.mlb.com/api/v1.1/game/{game['pk']}/feed/live"
                    pbp_response = requests.get(pbp_url, timeout=10)

                    if pbp_response.status_code == 200:
                        pbp_data = pbp_response.json()
                        plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                        for idx, play in enumerate(plays):
                            matchup = play.get('matchup', {})
                            if matchup.get('batter', {}).get('id') == player_id:
                                result = play.get('result', {})

                                conn.execute(text("""
                                    INSERT INTO milb_plate_appearances (
                                        mlb_player_id, game_pk, game_date, season,
                                        level, at_bat_index, event_type, description,
                                        created_at
                                    ) VALUES (
                                        :pid, :gpk, :gdate, 2025,
                                        'AA', :idx, :evt, :desc, NOW()
                                    )
                                    ON CONFLICT DO NOTHING
                                """), {
                                    'pid': player_id,
                                    'gpk': game['pk'],
                                    'gdate': game['date'],
                                    'idx': idx,
                                    'evt': result.get('event', '')[:50],
                                    'desc': result.get('description', '')[:200]
                                })
                                total_pas += 1

                    time.sleep(0.2)

        except Exception as e:
            logger.error(f"  Error: {e}")

    logger.info(f"  Collected {total_pas} PAs")
    return total_pas

def main():
    print("=" * 70)
    print("PARALLEL COLLECTION BATCH 2 (RANKS 31-50)")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    start_time = time.time()
    total_collected = 0

    for prospect in BATCH_2_PROSPECTS:
        try:
            pas = quick_collect(
                prospect['mlb_id'],
                prospect['name'],
                prospect['rank']
            )
            total_collected += pas
            time.sleep(1)

        except Exception as e:
            logger.error(f"Failed {prospect['name']}: {e}")

    elapsed = time.time() - start_time

    print(f"\n=== BATCH 2 COMPLETE ===")
    print(f"Total PAs collected: {total_collected}")
    print(f"Time: {elapsed/60:.1f} minutes")

if __name__ == "__main__":
    main()