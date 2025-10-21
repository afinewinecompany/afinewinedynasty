"""
Aggressive collection run for maximum coverage
Targets remaining prospects with focus on both PBP and Pitch data
"""

import requests
import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(f'aggressive_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Extended list of prospects needing pitch data
PITCH_TARGETS = [
    {'rank': 5, 'name': 'Carson Williams', 'mlb_id': 805804},
    {'rank': 16, 'name': 'Rainiel Rodriguez', 'mlb_id': 823787},
    {'rank': 17, 'name': 'Jett Williams', 'mlb_id': 805802},
    {'rank': 19, 'name': 'Edward Florentino', 'mlb_id': 821273},
    {'rank': 24, 'name': 'Joshua Baez', 'mlb_id': 695491},
    {'rank': 28, 'name': 'Travis Bazzana', 'mlb_id': 683953},
    # Expand to more
    {'rank': 31, 'name': 'Carson Benge', 'mlb_id': 701807},
    {'rank': 32, 'name': 'Josue De Paula', 'mlb_id': 800543},
    {'rank': 33, 'name': 'Zyhir Hope', 'mlb_id': 807737},
    {'rank': 35, 'name': 'Cooper Pratt', 'mlb_id': 806198},
    {'rank': 36, 'name': 'Kaelen Culpepper', 'mlb_id': 701785},
    {'rank': 39, 'name': 'Braden Montgomery', 'mlb_id': 695731},
    {'rank': 40, 'name': 'Ralphy Velazquez', 'mlb_id': 806252},
]

def collect_pbp_and_pitch(player_id, name, rank):
    """Collect both PBP and pitch data for a player"""

    logger.info(f"Collecting Rank #{rank}: {name}")

    with engine.begin() as conn:
        pbp_count = 0
        pitch_count = 0

        # Get games from 2024 and 2025
        for year in [2025, 2024]:
            url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
            params = {
                'stats': 'gameLog',
                'season': year,
                'group': 'hitting,pitching',
                'sportIds': '11,12,13,14,15,16'
            }

            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code != 200:
                    continue

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

                if not games:
                    continue

                logger.info(f"  {year}: {len(games)} games")

                # Process games (10 per year max for speed)
                for game in games[:10]:
                    pbp_url = f"https://statsapi.mlb.com/api/v1.1/game/{game['pk']}/feed/live"
                    pbp_response = requests.get(pbp_url, timeout=10)

                    if pbp_response.status_code != 200:
                        continue

                    pbp_data = pbp_response.json()
                    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                    # Collect PBP and pitch data simultaneously
                    for idx, play in enumerate(plays):
                        matchup = play.get('matchup', {})
                        batter_id = matchup.get('batter', {}).get('id')
                        pitcher_id = matchup.get('pitcher', {}).get('id')

                        if batter_id == player_id:
                            # Save PBP
                            result = play.get('result', {})
                            try:
                                conn.execute(text("""
                                    INSERT INTO milb_plate_appearances (
                                        mlb_player_id, game_pk, game_date, season,
                                        level, at_bat_index, event_type, description,
                                        created_at
                                    ) VALUES (
                                        :pid, :gpk, :gdate, :season,
                                        'AA', :idx, :evt, :desc, NOW()
                                    )
                                    ON CONFLICT (mlb_player_id, game_pk, at_bat_index) DO NOTHING
                                """), {
                                    'pid': player_id,
                                    'gpk': game['pk'],
                                    'gdate': game['date'],
                                    'season': year,
                                    'idx': idx,
                                    'evt': result.get('event', '')[:50],
                                    'desc': result.get('description', '')[:200]
                                })
                                pbp_count += 1
                            except:
                                pass

                            # Save pitches
                            at_bat_index = play.get('atBatIndex', 0)
                            about = play.get('about', {})

                            for pitch_idx, event in enumerate(play.get('playEvents', [])):
                                if not event.get('isPitch', False):
                                    continue

                                details = event.get('details', {})
                                pitch_data = event.get('pitchData', {})

                                try:
                                    conn.execute(text("""
                                        INSERT INTO milb_batter_pitches (
                                            mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                                            level, at_bat_index, pitch_number, inning,
                                            pitch_type, start_speed, spin_rate, zone,
                                            pitch_call, pitch_result, is_strike,
                                            balls, strikes, created_at
                                        ) VALUES (
                                            :bid, :pid, :gpk, :gdate, :season,
                                            'AA', :abi, :pn, :inn,
                                            :pt, :ss, :sr, :z,
                                            :pc, :pr, :is,
                                            :b, :s, NOW()
                                        )
                                        ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_number)
                                        DO NOTHING
                                    """), {
                                        'bid': batter_id,
                                        'pid': pitcher_id,
                                        'gpk': game['pk'],
                                        'gdate': game['date'],
                                        'season': year,
                                        'abi': at_bat_index,
                                        'pn': pitch_idx + 1,
                                        'inn': about.get('inning', 0),
                                        'pt': details.get('type', {}).get('code', '')[:10],
                                        'ss': pitch_data.get('startSpeed'),
                                        'sr': pitch_data.get('breaks', {}).get('spinRate'),
                                        'z': pitch_data.get('zone'),
                                        'pc': details.get('call', {}).get('code', '')[:10],
                                        'pr': details.get('call', {}).get('description', '')[:100],
                                        'is': details.get('isStrike', False),
                                        'b': details.get('count', {}).get('balls', 0),
                                        's': details.get('count', {}).get('strikes', 0)
                                    })
                                    pitch_count += 1
                                except:
                                    pass

                    time.sleep(0.15)  # Fast rate limiting

            except Exception as e:
                logger.error(f"  Error {year}: {e}")

    logger.info(f"  Result: {pbp_count} PAs, {pitch_count} pitches")
    return pbp_count, pitch_count

def main():
    print("=" * 70)
    print("AGGRESSIVE COLLECTION RUN - MAXIMUM COVERAGE")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    start_time = time.time()
    stats = {'pbp': 0, 'pitch': 0, 'players': 0}

    for prospect in PITCH_TARGETS:
        try:
            pbp, pitch = collect_pbp_and_pitch(
                prospect['mlb_id'],
                prospect['name'],
                prospect['rank']
            )

            stats['pbp'] += pbp
            stats['pitch'] += pitch
            stats['players'] += 1

            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed {prospect['name']}: {e}")

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("AGGRESSIVE RUN COMPLETE")
    print("=" * 70)
    print(f"Players processed: {stats['players']}")
    print(f"PBP records: {stats['pbp']}")
    print(f"Pitch records: {stats['pitch']}")
    print(f"Time: {elapsed/60:.1f} minutes")
    print(f"Rate: {(stats['pbp'] + stats['pitch'])/elapsed:.1f} records/sec")

if __name__ == "__main__":
    main()