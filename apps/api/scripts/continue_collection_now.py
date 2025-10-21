"""
Continue collection immediately for all remaining prospects
Focus on filling gaps for top 100
"""

import requests
import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(f'continued_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# ALL prospects needing data (expanded list)
PROSPECTS_NO_DATA = [
    # Priority 1: Top 30 with no data
    {'rank': 13, 'name': 'Nolan McLean', 'mlb_id': 690997},
    {'rank': 20, 'name': 'Payton Tolle', 'mlb_id': 801139},
    {'rank': 21, 'name': 'Bubba Chandler', 'mlb_id': 696149},
    {'rank': 22, 'name': 'Trey Yesavage', 'mlb_id': 702056},
    {'rank': 23, 'name': 'Jonah Tong', 'mlb_id': 804636},
    {'rank': 25, 'name': 'Carter Jensen', 'mlb_id': 695600},
    {'rank': 26, 'name': 'Thomas White', 'mlb_id': 806258},
    {'rank': 27, 'name': 'Connelly Early', 'mlb_id': 813349},
    {'rank': 29, 'name': 'Bryce Rainer', 'mlb_id': 800614},
    {'rank': 30, 'name': 'Lazaro Montes', 'mlb_id': 807718},
]

PROSPECTS_NEED_PITCH = [
    # Priority 2: Need pitch data
    {'rank': 4, 'name': 'Leo De Vries', 'mlb_id': 815888},
    {'rank': 8, 'name': 'JJ Wetherholt', 'mlb_id': 802139},
    {'rank': 10, 'name': 'Walker Jenkins', 'mlb_id': 805805},
    {'rank': 14, 'name': 'Sal Stewart', 'mlb_id': 701398},
    {'rank': 15, 'name': 'Eduardo Quintero', 'mlb_id': 808234},
    {'rank': 16, 'name': 'Rainiel Rodriguez', 'mlb_id': 823787},
    {'rank': 19, 'name': 'Edward Florentino', 'mlb_id': 821273},
    {'rank': 28, 'name': 'Travis Bazzana', 'mlb_id': 683953},
]

def fetch_and_save_pbp(player_id, player_name, rank):
    """Fetch and save play-by-play data"""

    logger.info(f"[PBP] Rank #{rank}: {player_name}")

    total_pas = 0
    total_games = 0

    with engine.begin() as conn:
        for year in [2025, 2024]:
            # Get player's games
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
                                'game_pk': game['gamePk'],
                                'date': split.get('date'),
                                'team': split.get('team', {}).get('name')
                            })

                if not games:
                    logger.info(f"  No games in {year}")
                    continue

                logger.info(f"  Processing {len(games)} games from {year}")

                # Process games (limit to 10 per year for speed)
                for game_data in games[:10]:
                    game_pk = game_data['game_pk']
                    game_date = game_data['date']

                    # Get PBP data
                    pbp_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
                    pbp_response = requests.get(pbp_url, timeout=10)

                    if pbp_response.status_code != 200:
                        continue

                    pbp_data = pbp_response.json()
                    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                    game_pas = 0
                    for idx, play in enumerate(plays):
                        matchup = play.get('matchup', {})
                        batter_id = matchup.get('batter', {}).get('id')

                        if batter_id == player_id:
                            result = play.get('result', {})

                            conn.execute(text("""
                                INSERT INTO milb_plate_appearances (
                                    mlb_player_id, game_pk, game_date, season,
                                    level, at_bat_index, event_type, description,
                                    created_at
                                ) VALUES (
                                    :player_id, :game_pk, :game_date, :season,
                                    'AA', :at_bat_index, :event_type, :description,
                                    NOW()
                                )
                                ON CONFLICT (mlb_player_id, game_pk, at_bat_index) DO NOTHING
                            """), {
                                'player_id': player_id,
                                'game_pk': game_pk,
                                'game_date': game_date,
                                'season': int(game_date[:4]),
                                'at_bat_index': idx,
                                'event_type': result.get('event', '')[:50],
                                'description': result.get('description', '')[:200]
                            })
                            game_pas += 1

                    if game_pas > 0:
                        total_pas += game_pas
                        total_games += 1

                    time.sleep(0.2)  # Rate limiting

            except Exception as e:
                logger.error(f"  Error: {e}")

    logger.info(f"  Result: {total_games} games, {total_pas} PAs")
    return total_games, total_pas

def fetch_and_save_pitches(player_id, player_name, rank):
    """Fetch and save pitch data"""

    logger.info(f"[PITCH] Rank #{rank}: {player_name}")

    total_pitches = 0
    total_games = 0

    with engine.begin() as conn:
        # Get games from PBP data
        result = conn.execute(text("""
            SELECT DISTINCT game_pk, game_date, level
            FROM milb_plate_appearances
            WHERE mlb_player_id = :player_id
            AND season IN (2024, 2025)
            ORDER BY game_date DESC
            LIMIT 10
        """), {'player_id': player_id})

        games = [(row[0], row[1], row[2]) for row in result]

        if not games:
            logger.info(f"  No PBP games to add pitches to")
            return 0, 0

        logger.info(f"  Processing {len(games)} games for pitch data")

        for game_pk, game_date, level in games:
            pbp_url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

            try:
                response = requests.get(pbp_url, timeout=10)
                if response.status_code != 200:
                    continue

                pbp_data = response.json()
                plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                game_pitches = 0
                for play in plays:
                    matchup = play.get('matchup', {})
                    batter_id = matchup.get('batter', {}).get('id')
                    pitcher_id = matchup.get('pitcher', {}).get('id')

                    if batter_id != player_id:
                        continue

                    at_bat_index = play.get('atBatIndex', 0)
                    about = play.get('about', {})

                    for pitch_idx, event in enumerate(play.get('playEvents', [])):
                        if not event.get('isPitch', False):
                            continue

                        details = event.get('details', {})
                        pitch_data = event.get('pitchData', {})

                        conn.execute(text("""
                            INSERT INTO milb_batter_pitches (
                                mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                                level, at_bat_index, pitch_number, inning,
                                pitch_type, start_speed, spin_rate, zone,
                                pitch_call, pitch_result, is_strike,
                                balls, strikes, created_at
                            ) VALUES (
                                :batter_id, :pitcher_id, :game_pk, :game_date, :season,
                                :level, :at_bat_index, :pitch_number, :inning,
                                :pitch_type, :start_speed, :spin_rate, :zone,
                                :pitch_call, :pitch_result, :is_strike,
                                :balls, :strikes, NOW()
                            )
                            ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_number)
                            DO NOTHING
                        """), {
                            'batter_id': batter_id,
                            'pitcher_id': pitcher_id,
                            'game_pk': game_pk,
                            'game_date': game_date,
                            'season': int(str(game_date)[:4]),
                            'level': level or 'AA',
                            'at_bat_index': at_bat_index,
                            'pitch_number': pitch_idx + 1,
                            'inning': about.get('inning', 0),
                            'pitch_type': details.get('type', {}).get('code', '')[:10],
                            'start_speed': pitch_data.get('startSpeed'),
                            'spin_rate': pitch_data.get('breaks', {}).get('spinRate'),
                            'zone': pitch_data.get('zone'),
                            'pitch_call': details.get('call', {}).get('code', '')[:10],
                            'pitch_result': details.get('call', {}).get('description', '')[:100],
                            'is_strike': details.get('isStrike', False),
                            'balls': details.get('count', {}).get('balls', 0),
                            'strikes': details.get('count', {}).get('strikes', 0)
                        })
                        game_pitches += 1

                if game_pitches > 0:
                    total_pitches += game_pitches
                    total_games += 1

                time.sleep(0.2)

            except Exception as e:
                pass  # Continue on error

    logger.info(f"  Result: {total_games} games, {total_pitches} pitches")
    return total_games, total_pitches

def main():
    print("=" * 70)
    print("CONTINUING COLLECTION - GETTING A HEAD START")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    start_time = time.time()
    stats = {
        'pbp_collected': 0,
        'pitch_collected': 0,
        'total_pas': 0,
        'total_pitches': 0
    }

    # Phase 1: Collect PBP for prospects with no data
    print("\n=== PHASE 1: COLLECTING PBP FOR NO-DATA PROSPECTS ===")

    for prospect in PROSPECTS_NO_DATA[:5]:  # Start with first 5
        try:
            games, pas = fetch_and_save_pbp(
                prospect['mlb_id'],
                prospect['name'],
                prospect['rank']
            )

            if games > 0:
                stats['pbp_collected'] += 1
                stats['total_pas'] += pas

                # Also try to get pitch data
                p_games, pitches = fetch_and_save_pitches(
                    prospect['mlb_id'],
                    prospect['name'],
                    prospect['rank']
                )

                if pitches > 0:
                    stats['pitch_collected'] += 1
                    stats['total_pitches'] += pitches

            time.sleep(1)  # Delay between prospects

        except Exception as e:
            logger.error(f"Error with {prospect['name']}: {e}")

    # Phase 2: Add pitch data for PBP-only prospects
    print("\n=== PHASE 2: ADDING PITCH DATA TO PBP-ONLY PROSPECTS ===")

    for prospect in PROSPECTS_NEED_PITCH[:5]:  # First 5
        try:
            games, pitches = fetch_and_save_pitches(
                prospect['mlb_id'],
                prospect['name'],
                prospect['rank']
            )

            if pitches > 0:
                stats['pitch_collected'] += 1
                stats['total_pitches'] += pitches

            time.sleep(1)

        except Exception as e:
            logger.error(f"Error with {prospect['name']}: {e}")

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("COLLECTION SESSION COMPLETE")
    print("=" * 70)
    print(f"PBP collected: {stats['pbp_collected']} players")
    print(f"Total PAs: {stats['total_pas']}")
    print(f"Pitch data added: {stats['pitch_collected']} players")
    print(f"Total pitches: {stats['total_pitches']}")
    print(f"Time: {elapsed/60:.1f} minutes")

    # Verify coverage
    print("\n=== CHECKING UPDATED COVERAGE ===")

    with engine.connect() as conn:
        for prospect in PROSPECTS_NO_DATA[:5]:
            result = conn.execute(text("""
                SELECT
                    COUNT(DISTINCT pa.game_pk) as pbp_games,
                    COUNT(DISTINCT bp.game_pk) as pitch_games
                FROM prospects p
                LEFT JOIN milb_plate_appearances pa ON p.mlb_player_id::text = pa.mlb_player_id::text
                    AND pa.season IN (2024, 2025)
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id::text = bp.mlb_batter_id::text
                    AND bp.season IN (2024, 2025)
                WHERE p.mlb_player_id = :player_id
                GROUP BY p.mlb_player_id
            """), {'player_id': str(prospect['mlb_id'])})

            row = result.fetchone()
            if row:
                status = "COMPLETE" if row[0] > 0 and row[1] > 0 else "PARTIAL" if row[0] > 0 else "NO DATA"
                print(f"Rank #{prospect['rank']:2}: {prospect['name']:20} - {row[0]} PBP, {row[1]} Pitch - {status}")

    print("\n✅ Collection session complete! Continue running for more prospects.")

if __name__ == "__main__":
    main()