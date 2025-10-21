import asyncio
import aiohttp
import psycopg2
from psycopg2 import sql
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/2024_batter_collection.log'),
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
BATCH_SIZE = 100

# MiLB sport IDs
SPORT_IDS = {
    11: 'AAA',
    12: 'AA',
    13: 'High-A',
    14: 'Single-A'
}

async def fetch_game_log_for_level(session, player_id, season, sport_id, retry_count=0):
    """Fetch player's game log for a specific sport level with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'sportId': sport_id,
        'group': 'hitting'
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
                    logging.warning(f"Rate limited for player {player_id}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await fetch_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
                else:
                    logging.error(f"Max retries exceeded for player {player_id} (rate limit)")
                    return []
            else:
                return []
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            logging.warning(f"Timeout for player {player_id} sport {sport_id}, retry {retry_count + 1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
        else:
            logging.error(f"Max retries exceeded for player {player_id} (timeout)")
            return []
    except aiohttp.ClientError as e:
        if retry_count < MAX_RETRIES:
            logging.warning(f"Client error for player {player_id}: {e}, retrying...")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
        else:
            logging.error(f"Max retries exceeded for player {player_id}: {e}")
            return []
    except Exception as e:
        logging.error(f"Unexpected error for player {player_id}: {e}")
        return []

async def fetch_play_by_play(session, game_pk, retry_count=0):
    """Fetch play-by-play data for a game with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    return await fetch_play_by_play(session, game_pk, retry_count + 1)
            return None
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_play_by_play(session, game_pk, retry_count + 1)
        return None
    except Exception:
        return None

def extract_plate_appearances(game_data, player_id):
    """Extract plate appearances for this batter"""
    if not game_data or 'liveData' not in game_data:
        return []

    plays = game_data['liveData'].get('plays', {}).get('allPlays', [])
    plate_appearances = []

    for play in plays:
        if 'matchup' not in play or 'batter' not in play['matchup']:
            continue

        if play['matchup']['batter'].get('id') != player_id:
            continue

        result = play.get('result', {})
        plate_appearances.append({
            'event': result.get('event'),
            'event_type': result.get('eventType'),
            'description': result.get('description'),
            'rbi': result.get('rbi', 0),
            'away_score': result.get('awayScore'),
            'home_score': result.get('homeScore')
        })

    return plate_appearances

def extract_pitches(game_data, player_id):
    """Extract pitch-by-pitch data when this player was batting"""
    if not game_data or 'liveData' not in game_data:
        return []

    plays = game_data['liveData'].get('plays', {}).get('allPlays', [])
    pitches = []

    for play in plays:
        if 'matchup' not in play or 'batter' not in play['matchup']:
            continue

        if play['matchup']['batter'].get('id') != player_id:
            continue

        pitcher_id = play['matchup'].get('pitcher', {}).get('id')

        for pitch_data in play.get('playEvents', []):
            if pitch_data.get('isPitch'):
                pitch_details = pitch_data.get('pitchData', {})
                pitches.append({
                    'pitcher_id': pitcher_id,
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

    return pitches

def insert_plate_appearances(conn, player_id, season, game_data_list):
    """Insert plate appearances into database"""
    cur = conn.cursor()
    inserted = 0

    for game_info, pas in game_data_list:
        game_pk = game_info['game']['gamePk']
        game_date = game_info['date']

        for pa in pas:
            try:
                cur.execute("""
                    INSERT INTO milb_plate_appearances (
                        mlb_player_id, game_pk, game_date, season,
                        event, event_type, description, rbi, away_score, home_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (mlb_player_id, game_pk, season) DO NOTHING
                """, (
                    player_id, game_pk, game_date, season,
                    pa['event'], pa['event_type'], pa['description'],
                    pa['rbi'], pa['away_score'], pa['home_score']
                ))
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logging.error(f"Error inserting PA for player {player_id}, game {game_pk}: {e}")
                continue

    conn.commit()
    cur.close()
    return inserted

def insert_pitches(conn, batter_id, season, game_data_list):
    """Insert pitches into database"""
    cur = conn.cursor()
    inserted = 0

    for game_info, pitches in game_data_list:
        game_pk = game_info['game']['gamePk']
        game_date = game_info['date']

        for pitch in pitches:
            try:
                cur.execute("""
                    INSERT INTO milb_batter_pitches (
                        mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                        pitch_number, pitch_type, pitch_call, start_speed, end_speed,
                        zone, strikes, balls, outs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (mlb_batter_id, game_pk, pitch_number, season) DO NOTHING
                """, (
                    batter_id, pitch['pitcher_id'], game_pk, game_date, season,
                    pitch['pitch_number'], pitch['pitch_type'], pitch['pitch_call'],
                    pitch['start_speed'], pitch['end_speed'], pitch['zone'],
                    pitch['strikes'], pitch['balls'], pitch['outs']
                ))
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logging.error(f"Error inserting pitch for batter {batter_id}, game {game_pk}: {e}")
                continue

    conn.commit()
    cur.close()
    return inserted

async def collect_player_data(session, conn, player_id, name, season):
    """Collect all 2024 data for a single player"""
    all_games = []

    # Fetch game logs for all levels
    for sport_id, level_name in SPORT_IDS.items():
        games = await fetch_game_log_for_level(session, player_id, season, sport_id)
        if games:
            logging.info(f"  -> Found {len(games)} games at {level_name}")
            all_games.extend(games)

    if not all_games:
        logging.info(f"  -> No {season} MiLB games found")
        return 0, 0

    logging.info(f"  -> Total games: {len(all_games)}")

    # Fetch play-by-play for each game
    pa_data = []
    pitch_data = []
    total_pas = 0
    total_pitches = 0

    for i, game_info in enumerate(all_games):
        game_pk = game_info['game']['gamePk']
        pbp_data = await fetch_play_by_play(session, game_pk)

        if pbp_data:
            pas = extract_plate_appearances(pbp_data, player_id)
            pitches = extract_pitches(pbp_data, player_id)

            if pas:
                pa_data.append((game_info, pas))
                total_pas += len(pas)

            if pitches:
                pitch_data.append((game_info, pitches))
                total_pitches += len(pitches)

        # Progress update every 10 games
        if (i + 1) % 10 == 0:
            logging.info(f"  -> Processed {i+1}/{len(all_games)} games ({total_pas} PAs, {total_pitches} pitches)")

    # Insert into database
    if pa_data:
        insert_plate_appearances(conn, player_id, season, pa_data)

    if pitch_data:
        insert_pitches(conn, player_id, season, pitch_data)

    logging.info(f"  -> COMPLETE: {total_pas} PAs, {total_pitches} pitches from {len(all_games)} games")
    return total_pas, total_pitches

async def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get batters missing 2024 data (properly exclude ALL pitcher positions)
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.organization,
            pr.v7_rank
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND (
            NOT EXISTS (
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2024
            )
            OR NOT EXISTS (
                SELECT 1 FROM milb_batter_pitches mbp
                WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2024
            )
        )
        ORDER BY COALESCE(pr.v7_rank, 9999), p.name
    """)

    prospects = cur.fetchall()

    logging.info("")
    logging.info("="*80)
    logging.info("ROBUST 2024 BATTER DATA COLLECTION - WITH RETRY LOGIC")
    logging.info("="*80)
    logging.info(f"\nFound {len(prospects)} non-pitcher prospects missing 2024 data")

    # Breakdown
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND NOT EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2024
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2024
        )
    """)
    missing_both = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2024
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2024
        )
    """)
    missing_pitch_only = cur.fetchone()[0]

    logging.info("\nBreakdown:")
    logging.info(f"  Missing BOTH PBP and Pitch: {missing_both}")
    logging.info(f"  Missing Pitch only: {missing_pitch_only}")

    logging.info("\n" + "="*80)
    logging.info("STARTING COLLECTION")
    logging.info("="*80)

    cur.close()

    # Create aiohttp session with connection pooling
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        successful = 0
        no_data = 0
        failed = 0
        total_pas = 0
        total_pitches = 0

        for idx, (player_id, name, org, rank) in enumerate(prospects):
            try:
                logging.info(f"\nCollecting: {name} ({org}, ID: {player_id})")

                pas, pitches = await collect_player_data(session, conn, player_id, name, 2024)

                if pas > 0 or pitches > 0:
                    successful += 1
                    total_pas += pas
                    total_pitches += pitches
                else:
                    no_data += 1

                # Progress report every 25 prospects
                if (idx + 1) % 25 == 0:
                    logging.info("")
                    logging.info("="*70)
                    logging.info(f"PROGRESS: {idx+1}/{len(prospects)} prospects")
                    logging.info(f"Successful: {successful} | No Data: {no_data} | Failed: {failed}")
                    logging.info(f"Total: {total_pas:,} PAs, {total_pitches:,} pitches")
                    logging.info("="*70)

                # Small delay to avoid overwhelming the API
                await asyncio.sleep(0.1)

            except Exception as e:
                logging.error(f"Failed to collect data for {name} ({player_id}): {e}")
                failed += 1
                continue

    logging.info("\n" + "="*80)
    logging.info("COLLECTION COMPLETE")
    logging.info("="*80)
    logging.info(f"Successful: {successful}")
    logging.info(f"No Data: {no_data}")
    logging.info(f"Failed: {failed}")
    logging.info(f"Total Collected: {total_pas:,} PAs, {total_pitches:,} pitches")
    logging.info("="*80 + "\n")

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
