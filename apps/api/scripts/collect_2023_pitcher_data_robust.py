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
        logging.FileHandler('logs/2023_pitcher_collection.log'),
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

def extract_pitcher_pitches(pbp_data, pitcher_id):
    """Extract pitch data when this player was pitching"""
    if not pbp_data or 'liveData' not in pbp_data:
        return []

    plays = pbp_data['liveData'].get('plays', {}).get('allPlays', [])
    pitches = []

    for play in plays:
        if 'matchup' not in play or 'pitcher' not in play['matchup']:
            continue

        # Check if this pitcher was throwing (not batting!)
        if play['matchup']['pitcher'].get('id') != pitcher_id:
            continue

        batter_id = play['matchup'].get('batter', {}).get('id')

        for pitch_data in play.get('playEvents', []):
            if pitch_data.get('isPitch'):
                pitch_details = pitch_data.get('pitchData', {})
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

    return pitches

def insert_pitcher_appearances(conn, pitcher_id, season, game_logs):
    """Insert pitcher game logs into database"""
    cur = conn.cursor()
    inserted = 0

    for game_info in game_logs:
        game_pk = game_info['game']['gamePk']
        game_date = game_info['date']
        stat = game_info.get('stat', {})

        # Determine level from sport info
        sport_id = game_info.get('sport', {}).get('id')
        level = SPORT_IDS.get(sport_id, 'Unknown')

        try:
            cur.execute("""
                INSERT INTO milb_pitcher_appearances (
                    mlb_player_id, game_pk, game_date, season, level,
                    innings_pitched, hits, runs, earned_runs, walks, strikeouts,
                    home_runs, pitches_thrown, strikes, batters_faced
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (mlb_player_id, game_pk, season) DO NOTHING
            """, (
                pitcher_id, game_pk, game_date, season, level,
                stat.get('inningsPitched'), stat.get('hits'), stat.get('runs'),
                stat.get('earnedRuns'), stat.get('baseOnBalls'), stat.get('strikeOuts'),
                stat.get('homeRuns'), stat.get('numberOfPitches'), stat.get('strikes'),
                stat.get('battersFaced')
            ))
            if cur.rowcount > 0:
                inserted += 1
        except Exception as e:
            logging.error(f"Error inserting appearance for pitcher {pitcher_id}, game {game_pk}: {e}")
            continue

    conn.commit()
    cur.close()
    return inserted

def insert_pitcher_pitches(conn, pitcher_id, season, game_data_list):
    """Insert pitcher pitches into database"""
    cur = conn.cursor()
    inserted = 0

    for game_info, pitches in game_data_list:
        game_pk = game_info['game']['gamePk']
        game_date = game_info['date']

        for pitch in pitches:
            try:
                cur.execute("""
                    INSERT INTO milb_pitcher_pitches (
                        mlb_pitcher_id, mlb_batter_id, game_pk, game_date, season,
                        pitch_number, pitch_type, pitch_call, start_speed, end_speed,
                        zone, strikes, balls, outs
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (mlb_pitcher_id, game_pk, pitch_number, season) DO NOTHING
                """, (
                    pitcher_id, pitch['batter_id'], game_pk, game_date, season,
                    pitch['pitch_number'], pitch['pitch_type'], pitch['pitch_call'],
                    pitch['start_speed'], pitch['end_speed'], pitch['zone'],
                    pitch['strikes'], pitch['balls'], pitch['outs']
                ))
                if cur.rowcount > 0:
                    inserted += 1
            except Exception as e:
                logging.error(f"Error inserting pitch for pitcher {pitcher_id}, game {game_pk}: {e}")
                continue

    conn.commit()
    cur.close()
    return inserted

async def collect_pitcher_data(session, conn, pitcher_id, name, position, season):
    """Collect all 2023 pitching data for a single pitcher"""
    all_games = []

    # Fetch game logs for all levels
    for sport_id, level_name in SPORT_IDS.items():
        games = await fetch_pitching_game_log_for_level(session, pitcher_id, season, sport_id)
        if games:
            logging.info(f"  -> Found {len(games)} games at {level_name}")
            all_games.extend(games)

    if not all_games:
        logging.info(f"  -> No {season} MiLB pitching games found")
        return 0, 0

    logging.info(f"  -> Total games: {len(all_games)}")

    # Insert game logs
    insert_pitcher_appearances(conn, pitcher_id, season, all_games)

    # Fetch play-by-play for pitch data
    pitch_data = []
    total_pitches = 0

    for i, game_info in enumerate(all_games):
        game_pk = game_info['game']['gamePk']
        pbp_data = await fetch_play_by_play(session, game_pk)

        if pbp_data:
            pitches = extract_pitcher_pitches(pbp_data, pitcher_id)
            if pitches:
                pitch_data.append((game_info, pitches))
                total_pitches += len(pitches)

        # Progress update every 10 games
        if (i + 1) % 10 == 0:
            logging.info(f"  -> Processed {i+1}/{len(all_games)} games ({total_pitches} pitches so far)")

    # Insert pitches
    if pitch_data:
        insert_pitcher_pitches(conn, pitcher_id, season, pitch_data)

    logging.info(f"  -> COMPLETE: {len(all_games)} games, {total_pitches} pitches")
    return len(all_games), total_pitches

async def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get pitchers missing 2023 data
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.position,
            p.organization,
            pr.v7_rank
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND (
            NOT EXISTS (
                SELECT 1 FROM milb_pitcher_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2023
            )
            OR NOT EXISTS (
                SELECT 1 FROM milb_pitcher_pitches mpp
                WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2023
            )
        )
        ORDER BY COALESCE(pr.v7_rank, 9999), p.name
    """)

    pitchers = cur.fetchall()

    logging.info("")
    logging.info("="*80)
    logging.info("ROBUST 2023 PITCHER DATA COLLECTION - WITH RETRY LOGIC")
    logging.info("="*80)
    logging.info(f"\nFound {len(pitchers)} pitchers needing 2023 data collection")

    # Breakdown
    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2023
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2023
        )
    """)
    missing_both = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2023
        )
        AND EXISTS (
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2023
        )
    """)
    missing_appearances = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND EXISTS (
            SELECT 1 FROM milb_pitcher_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2023
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2023
        )
    """)
    missing_pitches = cur.fetchone()[0]

    logging.info("\nBreakdown:")
    logging.info(f"  Missing BOTH appearances and pitches: {missing_both}")
    logging.info(f"  Missing appearances only: {missing_appearances}")
    logging.info(f"  Missing pitches only: {missing_pitches}")

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
        total_games = 0
        total_pitches = 0

        for idx, (player_id, name, position, org, rank) in enumerate(pitchers):
            try:
                logging.info(f"\nCollecting: {name} ({position}, #{rank if rank else 'unranked'}, ID: {player_id})")

                games, pitches = await collect_pitcher_data(session, conn, player_id, name, position, 2023)

                if games > 0 or pitches > 0:
                    successful += 1
                    total_games += games
                    total_pitches += pitches
                else:
                    no_data += 1

                # Progress report every 25 pitchers
                if (idx + 1) % 25 == 0:
                    logging.info("")
                    logging.info("="*70)
                    logging.info(f"PROGRESS: {idx+1}/{len(pitchers)} pitchers")
                    logging.info(f"Successful: {successful} | No Data: {no_data} | Failed: {failed}")
                    logging.info(f"Total: {total_games:,} games, {total_pitches:,} pitches")
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
    logging.info(f"Total Collected: {total_games:,} games, {total_pitches:,} pitches")
    logging.info("="*80 + "\n")

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
