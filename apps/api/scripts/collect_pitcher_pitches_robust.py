import psycopg2
import psycopg2.pool
import requests
import logging
from datetime import datetime
import time
import asyncio
import aiohttp
from typing import List, Dict, Tuple, Optional
import traceback

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Database configuration
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Create a connection pool to handle reconnections
connection_pool = None

def init_connection_pool():
    """Initialize the database connection pool"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            1, 10,  # min and max connections
            DB_URL,
            connect_timeout=30
        )
        logging.info("Database connection pool initialized")
    except Exception as e:
        logging.error(f"Failed to initialize connection pool: {e}")
        raise

def get_db_connection():
    """Get a connection from the pool with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if connection_pool:
                conn = connection_pool.getconn()
                # Test the connection
                cur = conn.cursor()
                cur.execute("SELECT 1")
                cur.close()
                return conn
        except Exception as e:
            logging.warning(f"Connection attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                # Reinitialize the pool if all retries failed
                init_connection_pool()
                return connection_pool.getconn()

def return_connection(conn):
    """Return a connection to the pool"""
    if connection_pool and conn:
        connection_pool.putconn(conn)

async def fetch_pbp_data(session, game_pk, max_retries=3):
    """Fetch play-by-play data with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    logging.warning(f"Game {game_pk} not found (404)")
                    return None
        except asyncio.TimeoutError:
            logging.warning(f"Timeout fetching game {game_pk}, attempt {attempt+1}")
        except aiohttp.ClientError as e:
            logging.warning(f"Client error for game {game_pk}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error fetching game {game_pk}: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return None

def extract_pitcher_pitches(pbp_data, pitcher_id):
    """Extract pitch data for a PITCHER from PBP data (pitches they threw)"""
    pitches = []

    if not pbp_data or 'liveData' not in pbp_data:
        return pitches

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')

    for play in plays:
        if 'matchup' not in play or 'pitcher' not in play['matchup']:
            continue

        # Check if THIS pitcher threw the pitches
        if play['matchup']['pitcher'].get('id') != pitcher_id:
            continue

        about = play.get('about', {})
        batter_id = play['matchup'].get('batter', {}).get('id')
        play_events = play.get('playEvents', [])

        for event in play_events:
            if event.get('isPitch'):
                details = event.get('details', {})
                pitch_data = event.get('pitchData', {})

                pitch = {
                    'mlb_pitcher_id': pitcher_id,
                    'mlb_batter_id': batter_id,
                    'game_pk': game_pk,
                    'game_date': game_date,
                    'season': None,  # Will be determined by year
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
                    'balls': details.get('ballColor', '').count('green'),
                    'strikes': details.get('strikeColor', '').count('red'),
                    'created_at': datetime.now()
                }

                # Determine season from game date
                if game_date:
                    try:
                        year = int(game_date[:4])
                        pitch['season'] = year
                    except:
                        pass

                pitches.append(pitch)

    return pitches

async def get_pitcher_games(conn, pitcher_id, season):
    """Get games where a pitcher appeared"""
    cur = conn.cursor()

    # Try to get games from plate appearances table (if pitcher also bats)
    # Or from any other source - we'll need to search by pitcher ID in games
    # For now, we'll use a different approach: search recent games

    # First check if we have any PA data for this pitcher
    cur.execute("""
        SELECT DISTINCT game_pk
        FROM milb_plate_appearances
        WHERE mlb_player_id = %s AND season = %s
        ORDER BY game_date
    """, (pitcher_id, season))

    games = [row[0] for row in cur.fetchall()]
    cur.close()

    return games

async def collect_pitcher_pitches(session, pitcher_id, name, season, position):
    """Collect pitch data for a single pitcher with proper error handling"""
    conn = None
    cur = None
    total_pitches = 0

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if pitcher already has pitch data for this season
        cur.execute("""
            SELECT COUNT(*) FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id = %s AND season = %s
        """, (pitcher_id, season))

        existing_count = cur.fetchone()[0]
        if existing_count > 0:
            logging.info(f"  {name} ({position}): Already has {existing_count} pitches for {season}, skipping")
            return 0

        # Get game PKs - try from PA table first
        cur.execute("""
            SELECT DISTINCT game_pk, game_date
            FROM milb_plate_appearances
            WHERE mlb_player_id = %s AND season = %s
            ORDER BY game_date
            LIMIT 200
        """, (pitcher_id, season))

        games = cur.fetchall()
        game_pks = [g[0] for g in games]

        if not game_pks:
            logging.info(f"  {name} ({position}): No {season} games found")
            return 0

        games_processed = 0
        batch_pitches = []

        for game_pk in game_pks:
            # Fetch PBP data
            pbp_data = await fetch_pbp_data(session, game_pk)
            if not pbp_data:
                continue

            # Extract pitches THROWN by this pitcher
            game_pitches = extract_pitcher_pitches(pbp_data, pitcher_id)
            if game_pitches:
                games_processed += 1
                batch_pitches.extend(game_pitches)

                # Insert in batches of 100 to avoid keeping too much in memory
                if len(batch_pitches) >= 100:
                    inserted = insert_pitcher_pitches_batch(conn, batch_pitches)
                    total_pitches += inserted
                    batch_pitches = []

        # Insert remaining pitches
        if batch_pitches:
            inserted = insert_pitcher_pitches_batch(conn, batch_pitches)
            total_pitches += inserted

        logging.info(f"  {name} ({position}): Collected {total_pitches} pitches from {games_processed}/{len(game_pks)} games")

    except Exception as e:
        logging.error(f"Error collecting for {name}: {e}")
        logging.error(traceback.format_exc())
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)

    return total_pitches

def insert_pitcher_pitches_batch(conn, pitches):
    """Insert a batch of pitcher pitches with proper error handling"""
    inserted = 0
    cur = None

    try:
        cur = conn.cursor()

        for pitch in pitches:
            try:
                cur.execute("""
                    INSERT INTO milb_pitcher_pitches (
                        mlb_pitcher_id, mlb_batter_id, game_pk, game_date, season,
                        level, at_bat_index, pitch_number, inning,
                        pitch_type, start_speed, spin_rate, zone,
                        pitch_call, pitch_result, is_strike,
                        balls, strikes, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT DO NOTHING
                """, (
                    pitch['mlb_pitcher_id'], pitch['mlb_batter_id'], pitch['game_pk'],
                    pitch['game_date'], pitch['season'], pitch['level'],
                    pitch['at_bat_index'], pitch['pitch_number'], pitch['inning'],
                    pitch['pitch_type'], pitch['start_speed'], pitch['spin_rate'],
                    pitch['zone'], pitch['pitch_call'], pitch['pitch_result'],
                    pitch['is_strike'], pitch['balls'], pitch['strikes'], pitch['created_at']
                ))
                inserted += cur.rowcount
            except Exception as e:
                logging.warning(f"Failed to insert pitch: {e}")
                continue

        conn.commit()
    except Exception as e:
        logging.error(f"Batch insert error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()

    return inserted

async def collect_batch(pitchers: List[Tuple], batch_num: int, total_batches: int, season: int):
    """Collect pitch data for a batch of pitchers"""
    logging.info(f"\n=== BATCH {batch_num}/{total_batches}: {len(pitchers)} pitchers ===")

    connector = aiohttp.TCPConnector(limit=3, limit_per_host=3)  # Limit connections
    timeout = aiohttp.ClientTimeout(total=300)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        batch_total = 0

        for pitcher_data in pitchers:
            pitcher_id = int(pitcher_data[0])
            name = pitcher_data[1]
            position = pitcher_data[2]

            result = await collect_pitcher_pitches(session, pitcher_id, name, season, position)
            batch_total += result

            # Small delay between pitchers to avoid overwhelming the API
            await asyncio.sleep(0.5)

        logging.info(f"  Batch {batch_num} complete: {batch_total} total pitches")
        return batch_total

def main():
    print("\n" + "="*70)
    print("ROBUST PITCHER PITCH COLLECTION - RESUMABLE")
    print(f"Started: {datetime.now()}")
    print("="*70)

    # Initialize connection pool
    init_connection_pool()

    # Determine which pitchers need collection
    conn = get_db_connection()
    cur = conn.cursor()

    # Get ALL pitcher prospects (P, RP, SP positions)
    cur.execute("""
        SELECT DISTINCT p.mlb_player_id, p.name, p.position, p.organization
        FROM prospects p
        LEFT JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
            AND mpp.season = 2025
        WHERE p.position IN ('P', 'RP', 'SP')
            AND p.mlb_player_id IS NOT NULL
            AND mpp.id IS NULL
        ORDER BY p.position, p.name
    """)

    pitchers_2025 = cur.fetchall()
    print(f"\nFound {len(pitchers_2025)} pitcher prospects needing 2025 pitch data")
    print(f"  Position breakdown:")

    # Count by position
    cur.execute("""
        SELECT p.position, COUNT(DISTINCT p.mlb_player_id)
        FROM prospects p
        LEFT JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
            AND mpp.season = 2025
        WHERE p.position IN ('P', 'RP', 'SP')
            AND p.mlb_player_id IS NOT NULL
            AND mpp.id IS NULL
        GROUP BY p.position
        ORDER BY p.position
    """)

    for pos, count in cur.fetchall():
        print(f"    {pos}: {count} pitchers")

    # Get pitchers needing 2024 data
    cur.execute("""
        SELECT DISTINCT p.mlb_player_id, p.name, p.position, p.organization
        FROM prospects p
        LEFT JOIN milb_pitcher_pitches mpp ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
            AND mpp.season = 2024
        WHERE p.position IN ('P', 'RP', 'SP')
            AND p.mlb_player_id IS NOT NULL
            AND mpp.id IS NULL
        ORDER BY p.position, p.name
    """)

    pitchers_2024 = cur.fetchall()
    print(f"\nFound {len(pitchers_2024)} pitcher prospects needing 2024 pitch data")

    cur.close()
    return_connection(conn)

    # Process 2025 first
    if pitchers_2025:
        print(f"\n=== COLLECTING 2025 PITCHER PITCH DATA ===")
        batch_size = 5  # Smaller batches for better reliability
        batches = [pitchers_2025[i:i+batch_size] for i in range(0, len(pitchers_2025), batch_size)]

        total_collected = 0
        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            try:
                batch_result = asyncio.run(collect_batch(batch, i, len(batches), 2025))
                total_collected += batch_result

                # Progress report every 10 batches
                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = total_collected / elapsed if elapsed > 0 else 0
                    print(f"\n[PROGRESS] Completed {i}/{len(batches)} batches")
                    print(f"  Total pitches collected: {total_collected:,}")
                    print(f"  Collection rate: {rate:.1f} pitches/sec")

            except Exception as e:
                logging.error(f"Batch {i} failed: {e}")
                continue

    # Process 2024
    if pitchers_2024:
        print(f"\n=== COLLECTING 2024 PITCHER PITCH DATA ===")
        batch_size = 5
        batches = [pitchers_2024[i:i+batch_size] for i in range(0, len(pitchers_2024), batch_size)]

        total_collected = 0
        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            try:
                batch_result = asyncio.run(collect_batch(batch, i, len(batches), 2024))
                total_collected += batch_result

                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = total_collected / elapsed if elapsed > 0 else 0
                    print(f"\n[PROGRESS] Completed {i}/{len(batches)} batches")
                    print(f"  Total pitches collected: {total_collected:,}")
                    print(f"  Collection rate: {rate:.1f} pitches/sec")

            except Exception as e:
                logging.error(f"Batch {i} failed: {e}")
                continue

    # Final report
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM milb_pitcher_pitches WHERE season = 2025")
    total_2025 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM milb_pitcher_pitches WHERE season = 2024")
    total_2024 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_pitcher_id) FROM milb_pitcher_pitches WHERE season IN (2024, 2025)")
    unique_pitchers = cur.fetchone()[0]

    cur.close()
    return_connection(conn)

    # Close the connection pool
    if connection_pool:
        connection_pool.closeall()

    print("\n" + "="*70)
    print("COLLECTION COMPLETE")
    print(f"Total 2025 pitcher pitch records: {total_2025:,}")
    print(f"Total 2024 pitcher pitch records: {total_2024:,}")
    print(f"Unique pitchers with data: {unique_pitchers:,}")
    print(f"Ended: {datetime.now()}")
    print("="*70)

if __name__ == "__main__":
    main()
