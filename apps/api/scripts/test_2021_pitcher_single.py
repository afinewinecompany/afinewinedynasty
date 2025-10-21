import asyncio
import aiohttp
import psycopg2
from datetime import datetime
import logging

# Configure logging with DEBUG level for detailed diagnostics
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/2021_pitcher_test_single.log'),
        logging.StreamHandler()
    ]
)

# Database connection
DB_CONFIG = {
    'host': 'nozomi.proxy.rlwy.net',
    'port': 39235,
    'database': 'railway',
    'user': 'postgres',
    'password': 'BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp'
}

# API configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0
API_TIMEOUT = 30

# MiLB sport IDs
SPORT_IDS = {
    11: 'AAA',
    12: 'AA',
    13: 'High-A',
    14: 'Single-A'
}

async def fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count=0):
    """Fetch pitcher's game log for a specific sport level with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'sportId': sport_id,
        'group': 'pitching'
    }

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
            if response.status == 200:
                data = await response.json()
                if 'stats' in data and data['stats']:
                    for stat in data['stats']:
                        if 'splits' in stat:
                            return stat['splits']
                return []
            elif response.status == 429:  # Rate limited
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    logging.warning(f"Rate limited for pitcher {player_id}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
                else:
                    logging.error(f"Max retries exceeded for pitcher {player_id} (rate limit)")
                    return []
            else:
                return []
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            logging.warning(f"Timeout for pitcher {player_id} sport {sport_id}, retry {retry_count + 1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
        else:
            logging.error(f"Max retries exceeded for pitcher {player_id} (timeout)")
            return []
    except aiohttp.ClientError as e:
        if retry_count < MAX_RETRIES:
            logging.warning(f"Client error for pitcher {player_id}: {e}, retrying...")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
        else:
            logging.error(f"Max retries exceeded for pitcher {player_id}: {e}")
            return []
    except Exception as e:
        logging.error(f"Unexpected error for pitcher {player_id}: {e}")
        return []

async def fetch_play_by_play(session, game_pk, retry_count=0):
    """Fetch play-by-play data for a game with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
            if response.status == 200:
                data = await response.json()
                logging.debug(f"      PBP data fetched for game {game_pk} - Status: 200")
                return data
            elif response.status == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    return await fetch_play_by_play(session, game_pk, retry_count + 1)
            else:
                logging.debug(f"      PBP fetch failed for game {game_pk} - Status: {response.status}")
            return None
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_play_by_play(session, game_pk, retry_count + 1)
        logging.debug(f"      PBP fetch timeout for game {game_pk}")
        return None
    except Exception as e:
        logging.debug(f"      PBP fetch error for game {game_pk}: {e}")
        return None

def extract_pitcher_pitches(pbp_data, pitcher_id, game_pk=None):
    """Extract pitch data when this player was pitching"""
    if not pbp_data:
        logging.debug(f"      Game {game_pk}: No PBP data provided")
        return []

    if 'liveData' not in pbp_data:
        logging.debug(f"      Game {game_pk}: No 'liveData' key in PBP data. Keys: {list(pbp_data.keys())}")
        return []

    plays = pbp_data['liveData'].get('plays', {}).get('allPlays', [])
    if not plays:
        logging.debug(f"      Game {game_pk}: No plays found in liveData.plays.allPlays")
        return []

    logging.debug(f"      Game {game_pk}: Found {len(plays)} total plays, checking for pitcher {pitcher_id}")

    pitches = []
    plays_for_pitcher = 0
    plays_with_pitch_events = 0
    plays_with_pitch_data = 0

    for play in plays:
        if 'matchup' not in play or 'pitcher' not in play['matchup']:
            continue

        # Check if this pitcher was throwing (not batting!)
        if play['matchup']['pitcher'].get('id') != pitcher_id:
            continue

        plays_for_pitcher += 1
        batter_id = play['matchup'].get('batter', {}).get('id')
        play_events = play.get('playEvents', [])

        if play_events:
            plays_with_pitch_events += 1

        for pitch_data in play_events:
            if pitch_data.get('isPitch'):
                pitch_details = pitch_data.get('pitchData', {})
                if pitch_details:
                    plays_with_pitch_data += 1
                    pitches.append({
                        'batter_id': batter_id,
                        'pitch_number': pitch_data.get('pitchNumber'),
                        'pitch_type': pitch_details.get('typeDescription'),
                        'pitch_call': pitch_data.get('details', {}).get('call', {}).get('description'),
                        'start_speed': pitch_details.get('startSpeed'),
                        'end_speed': pitch_details.get('endSpeed'),
                        'zone': pitch_details.get('zone'),
                        'strikes': pitch_data.get('count', {}).get('strikes'),
                        'balls': pitch_data.get('count', {}).get('balls'),
                        'outs': pitch_data.get('count', {}).get('outs')
                    })

    if plays_for_pitcher == 0:
        logging.debug(f"      Game {game_pk}: No plays found for pitcher {pitcher_id}")
    elif plays_with_pitch_events == 0:
        logging.debug(f"      Game {game_pk}: Found {plays_for_pitcher} plays for pitcher but NO playEvents")
    elif plays_with_pitch_data == 0:
        logging.debug(f"      Game {game_pk}: Found {plays_for_pitcher} plays, {plays_with_pitch_events} with events, but NO pitchData")
    elif pitches:
        logging.debug(f"      Game {game_pk}: Successfully extracted {len(pitches)} pitches")

    return pitches

async def test_single_pitcher():
    """Test collection for a single pitcher with detailed logging"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get ONE pitcher who has appearances in 2021 but no pitch data
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.position,
            p.organization,
            COUNT(mpa.game_pk) as game_count
        FROM prospects p
        INNER JOIN milb_pitcher_appearances mpa ON mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2021
        WHERE p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2021
        )
        GROUP BY p.mlb_player_id, p.name, p.position, p.organization
        ORDER BY COUNT(mpa.game_pk) DESC
        LIMIT 1
    """)

    result = cur.fetchone()
    if not result:
        logging.error("No pitcher found with 2021 appearances but no pitch data!")
        cur.close()
        conn.close()
        return

    pitcher_id, name, position, org, game_count = result

    logging.info("="*80)
    logging.info(f"TESTING SINGLE PITCHER: {name} (ID: {pitcher_id})")
    logging.info(f"Position: {position}, Org: {org}")
    logging.info(f"Has {game_count} game appearances in 2021")
    logging.info("="*80)

    # Get the actual games from the database
    cur.execute("""
        SELECT game_pk, game_date, level
        FROM milb_pitcher_appearances
        WHERE mlb_player_id = %s AND season = 2021
        ORDER BY game_date
        LIMIT 5
    """, (pitcher_id,))

    db_games = cur.fetchall()
    logging.info(f"\nFirst 5 games from database:")
    for game_pk, game_date, level in db_games:
        logging.info(f"  Game PK: {game_pk}, Date: {game_date}, Level: {level}")

    cur.close()

    # Now fetch via API
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        all_games = []

        # Fetch game logs for all levels
        for sport_id, level_name in SPORT_IDS.items():
            games = await fetch_pitching_game_log_for_level(session, pitcher_id, 2021, sport_id)
            if games:
                logging.info(f"\nFound {len(games)} games at {level_name} via API")
                all_games.extend(games)

        if not all_games:
            logging.error("No games found via API!")
            conn.close()
            return

        logging.info(f"\nTotal API games: {len(all_games)}")
        logging.info(f"\nTesting play-by-play fetch for first 3 games...")

        for i, game_info in enumerate(all_games[:3]):
            game_pk = game_info['game']['gamePk']
            game_date = game_info.get('date', 'unknown')

            logging.info(f"\n--- Game {i+1}: PK={game_pk}, Date={game_date} ---")

            pbp_data = await fetch_play_by_play(session, game_pk)

            if pbp_data:
                logging.info(f"  ✓ Got play-by-play data")
                pitches = extract_pitcher_pitches(pbp_data, pitcher_id, game_pk)
                logging.info(f"  Extracted {len(pitches)} pitches")
            else:
                logging.warning(f"  ✗ No play-by-play data!")

    conn.close()
    logging.info("\n" + "="*80)
    logging.info("TEST COMPLETE")
    logging.info("="*80)

if __name__ == "__main__":
    asyncio.run(test_single_pitcher())
