import psycopg2
import logging
from datetime import datetime
import asyncio
import aiohttp
from aiohttp import ClientTimeout, ClientError

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0
API_TIMEOUT = 30  # seconds

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
        async with session.get(url, params=params, timeout=ClientTimeout(total=API_TIMEOUT)) as response:
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
                    logging.error(f"Max retries reached for player {player_id}, sport {sport_id}")
                    return []
            else:
                logging.error(f"HTTP {response.status} for player {player_id}, sport {sport_id}")
                return []
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            logging.warning(f"Timeout for player {player_id} sport {sport_id}, retry {retry_count + 1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
        else:
            logging.error(f"Timeout after {MAX_RETRIES} retries for player {player_id}")
            return []
    except ClientError as e:
        logging.error(f"Client error fetching game log for {player_id} sportId {sport_id}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error fetching game log for {player_id} sportId {sport_id}: {e}")
        return []

async def fetch_pbp_data(session, game_pk, retry_count=0):
    """Fetch play-by-play data for a game with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=ClientTimeout(total=API_TIMEOUT)) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:  # Rate limited
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    return await fetch_pbp_data(session, game_pk, retry_count + 1)
            return None
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_pbp_data(session, game_pk, retry_count + 1)
        return None
    except Exception as e:
        logging.error(f"Error fetching PBP for game {game_pk}: {e}")
        return None

def extract_plate_appearances(pbp_data, player_id):
    """Extract plate appearances for a player from PBP data"""
    plate_appearances = []

    if not pbp_data or 'liveData' not in pbp_data:
        return plate_appearances

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')

    for play in plays:
        if 'matchup' in play and 'batter' in play['matchup']:
            if play['matchup']['batter'].get('id') == player_id:
                about = play.get('about', {})
                result = play.get('result', {})

                pa = {
                    'mlb_player_id': player_id,
                    'game_pk': game_pk,
                    'game_date': game_date,
                    'season': 2025,
                    'level': pbp_data.get('gameData', {}).get('game', {}).get('type', ''),
                    'at_bat_index': about.get('atBatIndex', 0),
                    'inning': about.get('inning', 0),
                    'half_inning': about.get('halfInning', ''),
                    'event_type': result.get('eventType', ''),
                    'event_type_desc': result.get('event', ''),
                    'description': result.get('description', ''),
                    'launch_speed': None,
                    'launch_angle': None,
                    'total_distance': None,
                    'created_at': datetime.now()
                }

                if 'hitData' in play:
                    hit_data = play['hitData']
                    pa['launch_speed'] = hit_data.get('launchSpeed')
                    pa['launch_angle'] = hit_data.get('launchAngle')
                    pa['total_distance'] = hit_data.get('totalDistance')

                plate_appearances.append(pa)

    return plate_appearances

def extract_pitches(pbp_data, player_id):
    """Extract pitch data for a batter from PBP data"""
    pitches = []

    if not pbp_data or 'liveData' not in pbp_data:
        return pitches

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')
    season = 2025

    for play in plays:
        if 'matchup' not in play or 'batter' not in play['matchup']:
            continue

        if play['matchup']['batter'].get('id') != player_id:
            continue

        about = play.get('about', {})
        pitcher_id = play['matchup'].get('pitcher', {}).get('id')
        play_events = play.get('playEvents', [])

        for event in play_events:
            if event.get('isPitch'):
                details = event.get('details', {})
                pitch_data = event.get('pitchData', {})

                pitch = {
                    'mlb_batter_id': player_id,
                    'mlb_pitcher_id': pitcher_id,
                    'game_pk': game_pk,
                    'game_date': game_date,
                    'season': season,
                    'level': pbp_data.get('gameData', {}).get('game', {}).get('type', ''),
                    'at_bat_index': about.get('atBatIndex', 0),
                    'pitch_number': event.get('pitchNumber', 0),
                    'inning': about.get('inning', 0),
                    'pitch_type': details.get('type', {}).get('code', ''),
                    'start_speed': pitch_data.get('startSpeed'),
                    'spin_rate': pitch_data.get('breaks', {}).get('spinRate'),
                    'zone': pitch_data.get('zone'),
                    'pitch_call': details.get('call', {}).get('code', ''),
                    'pitch_result': details.get('description', ''),
                    'is_strike': details.get('isStrike', False),
                    'balls': details.get('count', {}).get('balls', 0),
                    'strikes': details.get('count', {}).get('strikes', 0),
                    'created_at': datetime.now()
                }

                pitches.append(pitch)

    return pitches

async def collect_player_data(session, player_id, name, org, conn):
    """Collect complete batting data for a player"""

    cur = conn.cursor()

    # Check if already has complete data
    cur.execute("""
        SELECT COUNT(*) FROM milb_plate_appearances
        WHERE mlb_player_id = %s AND season = 2025
    """, (player_id,))
    existing_pbp = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
    """, (player_id,))
    existing_pitch = cur.fetchone()[0]

    if existing_pbp > 0 and existing_pitch > 0:
        logging.info(f"  {name} - Already complete ({existing_pbp} PAs, {existing_pitch} pitches)")
        return True, 0, 0

    logging.info(f"\nCollecting: {name} ({org}, ID: {player_id})")

    # Query EACH MiLB level separately with retry logic
    sport_ids = [11, 12, 13, 14]  # AAA, AA, High-A, Single-A
    sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}

    all_game_pks = set()
    api_call_success = False

    for sport_id in sport_ids:
        games = await fetch_game_log_for_level(session, player_id, 2025, sport_id)
        if games is not None:  # Check for None vs empty list
            api_call_success = True
            if games:
                logging.info(f"  -> Found {len(games)} games at {sport_names[sport_id]}")
                for g in games:
                    if 'game' in g:
                        game_pk = g['game'].get('gamePk')
                        if game_pk:
                            all_game_pks.add(game_pk)
        await asyncio.sleep(0.3)  # Rate limiting

    if not api_call_success:
        logging.error(f"  -> ALL API CALLS FAILED for {name}!")
        return False, 0, 0

    if not all_game_pks:
        logging.info(f"  -> No 2025 MiLB games found")
        return True, 0, 0  # Success but no data

    game_pks = list(all_game_pks)
    logging.info(f"  -> Total games: {len(game_pks)}")

    total_pbp = 0
    total_pitches = 0

    for i, game_pk in enumerate(game_pks, 1):
        pbp_data = await fetch_pbp_data(session, game_pk)
        if not pbp_data:
            logging.warning(f"  -> Failed to get PBP for game {game_pk}")
            continue

        # Extract and save plate appearances
        pas = extract_plate_appearances(pbp_data, player_id)
        for pa in pas:
            try:
                cur.execute("""
                    INSERT INTO milb_plate_appearances (
                        mlb_player_id, game_pk, game_date, season, level,
                        at_bat_index, inning, half_inning, event_type, event_type_desc,
                        description, launch_speed, launch_angle, total_distance,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    ) ON CONFLICT DO NOTHING
                """, (
                    pa['mlb_player_id'], pa['game_pk'], pa['game_date'], pa['season'],
                    pa['level'], pa['at_bat_index'], pa['inning'], pa['half_inning'],
                    pa['event_type'], pa['event_type_desc'], pa['description'],
                    pa['launch_speed'], pa['launch_angle'], pa['total_distance'],
                    pa['created_at']
                ))
                total_pbp += 1
            except Exception as e:
                logging.error(f"Error inserting PA: {e}")

        # Extract and save pitches
        pitches = extract_pitches(pbp_data, player_id)
        for pitch in pitches:
            try:
                cur.execute("""
                    INSERT INTO milb_batter_pitches (
                        mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                        level, at_bat_index, pitch_number, inning,
                        pitch_type, start_speed, spin_rate, zone,
                        pitch_call, pitch_result, is_strike,
                        balls, strikes, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT DO NOTHING
                """, (
                    pitch['mlb_batter_id'], pitch['mlb_pitcher_id'], pitch['game_pk'],
                    pitch['game_date'], pitch['season'], pitch['level'],
                    pitch['at_bat_index'], pitch['pitch_number'], pitch['inning'],
                    pitch['pitch_type'], pitch['start_speed'], pitch['spin_rate'],
                    pitch['zone'], pitch['pitch_call'], pitch['pitch_result'],
                    pitch['is_strike'], pitch['balls'], pitch['strikes'], pitch['created_at']
                ))
                total_pitches += 1
            except Exception as e:
                logging.error(f"Error inserting pitch: {e}")

        conn.commit()

        if i % 10 == 0:
            logging.info(f"  -> Processed {i}/{len(game_pks)} games ({total_pbp} PAs, {total_pitches} pitches)")

        await asyncio.sleep(0.5)  # Rate limiting between games

    logging.info(f"  -> COMPLETE: {total_pbp} PAs, {total_pitches} pitches from {len(game_pks)} games")
    return True, total_pbp, total_pitches

async def main():
    """Main collection function"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("ROBUST BATTER DATA COLLECTION - WITH RETRY LOGIC")
    logging.info("="*80)

    # Get ALL prospects missing EITHER PBP or Pitch data for 2025
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.organization,
            pr.v7_rank,
            EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                   WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_pbp,
            EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                   WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025) as has_pitch
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position != 'P'  -- Skip pitchers, they have separate collection
        AND (
            NOT EXISTS (
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
            )
            OR NOT EXISTS (
                SELECT 1 FROM milb_batter_pitches mbp
                WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025
            )
        )
        ORDER BY COALESCE(pr.v7_rank, 9999), p.name  -- Top prospects first
    """)

    missing_prospects = cur.fetchall()
    cur.close()

    logging.info(f"\nFound {len(missing_prospects)} non-pitcher prospects missing 2025 data")

    if not missing_prospects:
        logging.info("\n>>> All prospects have complete 2025 data!")
        conn.close()
        return

    # Categorize
    missing_both = [p for p in missing_prospects if not p[4] and not p[5]]
    missing_pitch_only = [p for p in missing_prospects if p[4] and not p[5]]

    logging.info(f"\nBreakdown:")
    logging.info(f"  Missing BOTH PBP and Pitch: {len(missing_both)}")
    logging.info(f"  Missing Pitch only: {len(missing_pitch_only)}")

    logging.info("\n" + "="*80)
    logging.info("STARTING COLLECTION")
    logging.info("="*80)

    successful = 0
    no_data = 0
    failed = 0
    total_pbp = 0
    total_pitches = 0

    # Create session with connection pooling
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = ClientTimeout(total=60, connect=10, sock_read=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for idx, (mlb_id, name, org, rank, has_pbp, has_pitch) in enumerate(missing_prospects, 1):
            try:
                success, pbp_count, pitch_count = await collect_player_data(
                    session, int(mlb_id), name, org or 'N/A', conn
                )

                if success:
                    if pbp_count > 0 or pitch_count > 0:
                        successful += 1
                        total_pbp += pbp_count
                        total_pitches += pitch_count
                    else:
                        no_data += 1
                else:
                    failed += 1

            except Exception as e:
                logging.error(f"ERROR collecting data for {name}: {e}")
                failed += 1

            # Progress update every 25 prospects
            if idx % 25 == 0:
                logging.info("\n" + "="*70)
                logging.info(f"PROGRESS: {idx}/{len(missing_prospects)} prospects")
                logging.info(f"Successful: {successful} | No Data: {no_data} | Failed: {failed}")
                logging.info(f"Total: {total_pbp:,} PAs, {total_pitches:,} pitches")
                logging.info("="*70 + "\n")

    # Final summary
    logging.info("\n" + "="*80)
    logging.info("COLLECTION COMPLETE")
    logging.info("="*80)
    logging.info(f"Prospects processed:   {len(missing_prospects)}")
    logging.info(f"Successful:            {successful}")
    logging.info(f"No data available:     {no_data}")
    logging.info(f"Failed:                {failed}")
    logging.info(f"Total PAs collected:   {total_pbp:,}")
    logging.info(f"Total pitches:         {total_pitches:,}")
    logging.info("="*80)

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
