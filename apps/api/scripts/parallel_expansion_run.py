"""
Parallel expansion - collect for prospects 41-60
Run simultaneously with aggressive collection
"""

import requests
import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Prospects ranks 41-60 (add actual MLB IDs as you have them)
BATCH_41_60 = [
    {'rank': 41, 'name': 'Ryan Sloan', 'mlb_id': 815549},
    {'rank': 42, 'name': 'Brody Hopkins', 'mlb_id': 811315},
    {'rank': 43, 'name': 'Michael Arroyo', 'mlb_id': 807747},
    {'rank': 44, 'name': 'Dylan Beavers', 'mlb_id': 694213},
    {'rank': 45, 'name': 'Harry Ford', 'mlb_id': 695670},
    {'rank': 46, 'name': 'Ryan Clifford', 'mlb_id': 805809},
    {'rank': 47, 'name': 'Arjun Nimmala', 'mlb_id': 805796},
    {'rank': 48, 'name': 'Josue Briceno', 'mlb_id': 800522},
    {'rank': 49, 'name': 'Termarr Johnson', 'mlb_id': 807741},
    {'rank': 50, 'name': 'Brennen Davis', 'mlb_id': 702137},
]

def quick_full_collect(player_id, name, rank):
    """Quick collection of both PBP and pitch"""

    logger.info(f"Rank #{rank}: {name}")

    with engine.begin() as conn:
        total = 0

        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {'stats': 'gameLog', 'season': 2025, 'group': 'hitting', 'sportIds': '11,12,13,14,15,16'}

        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                games = []

                for stat_group in data.get('stats', []):
                    for split in stat_group.get('splits', []):
                        game = split.get('game', {})
                        if game.get('gamePk'):
                            games.append({'pk': game['gamePk'], 'date': split.get('date')})

                logger.info(f"  {len(games)} games found")

                for game in games[:5]:  # Quick 5 games
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
                                        level, at_bat_index, event_type, description, created_at
                                    ) VALUES (
                                        :pid, :gpk, :gdate, 2025, 'AA', :idx, :evt, :desc, NOW()
                                    )
                                    ON CONFLICT DO NOTHING
                                """), {
                                    'pid': player_id, 'gpk': game['pk'], 'gdate': game['date'],
                                    'idx': idx, 'evt': result.get('event', '')[:50],
                                    'desc': result.get('description', '')[:200]
                                })
                                total += 1

                    time.sleep(0.15)

        except Exception as e:
            logger.error(f"  Error: {e}")

    logger.info(f"  Collected {total} records")
    return total

def main():
    print("PARALLEL EXPANSION - RANKS 41-60")
    print(f"Started: {datetime.now()}")

    start = time.time()
    total = 0

    for prospect in BATCH_41_60:
        total += quick_full_collect(prospect['mlb_id'], prospect['name'], prospect['rank'])
        time.sleep(0.5)

    print(f"\nCOMPLETE: {total} records in {(time.time()-start)/60:.1f} min")

if __name__ == "__main__":
    main()