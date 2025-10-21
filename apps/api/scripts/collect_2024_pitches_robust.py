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
        logging.info("Database connection pool initialized for 2024 collection")
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

def extract_pitches(pbp_data, player_id):
    """Extract pitch data for a batter from PBP data"""
    pitches = []

    if not pbp_data or 'liveData' not in pbp_data:
        return pitches

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')

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
                    'season': 2024,  # Fixed to 2024 for this script
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

                pitches.append(pitch)

    return pitches

async def collect_player_pitches(session, player_id, name, pa_count=None):
    """Collect 2024 pitch data for a single player with proper error handling"""
    conn = None
    cur = None
    total_pitches = 0

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if player already has 2024 pitch data
        cur.execute("""
            SELECT COUNT(*) FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = 2024
        """, (player_id,))

        existing_count = cur.fetchone()[0]
        if existing_count > 0:
            logging.info(f"  {name}: Already has {existing_count} pitches for 2024, skipping")
            return 0

        # Get game PKs from PBP table for 2024
        cur.execute("""
            SELECT DISTINCT game_pk, game_date
            FROM milb_plate_appearances
            WHERE mlb_player_id = %s AND season = 2024
            ORDER BY game_date
            LIMIT 150
        """, (player_id,))

        games = cur.fetchall()
        game_pks = [g[0] for g in games]

        if not game_pks:
            logging.info(f"  {name}: No 2024 games to process")
            return 0

        games_processed = 0
        batch_pitches = []

        for game_pk in game_pks:
            # Fetch PBP data
            pbp_data = await fetch_pbp_data(session, game_pk)
            if not pbp_data:
                continue

            # Extract pitches
            game_pitches = extract_pitches(pbp_data, player_id)
            if game_pitches:
                games_processed += 1
                batch_pitches.extend(game_pitches)

                # Insert in batches of 100 to avoid keeping too much in memory
                if len(batch_pitches) >= 100:
                    inserted = insert_pitches_batch(conn, batch_pitches)
                    total_pitches += inserted
                    batch_pitches = []

        # Insert remaining pitches
        if batch_pitches:
            inserted = insert_pitches_batch(conn, batch_pitches)
            total_pitches += inserted

        pa_info = f"({pa_count} PAs) " if pa_count else ""
        logging.info(f"  {name} {pa_info}- 2024: Collected {total_pitches} pitches from {games_processed}/{len(game_pks)} games")

    except Exception as e:
        logging.error(f"Error collecting 2024 data for {name}: {e}")
        logging.error(traceback.format_exc())
    finally:
        if cur:
            cur.close()
        if conn:
            return_connection(conn)

    return total_pitches

def insert_pitches_batch(conn, pitches):
    """Insert a batch of pitches with proper error handling"""
    inserted = 0
    cur = None

    try:
        cur = conn.cursor()

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

async def collect_batch(players: List[Tuple], batch_num: int, total_batches: int):
    """Collect 2024 pitch data for a batch of players"""
    logging.info(f"\n=== 2024 BATCH {batch_num}/{total_batches}: {len(players)} players ===")

    connector = aiohttp.TCPConnector(limit=3, limit_per_host=3)  # Limit connections
    timeout = aiohttp.ClientTimeout(total=300)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        batch_total = 0

        for player_data in players:
            player_id = int(player_data[0])
            name = player_data[1]
            pa_count = int(player_data[3]) if len(player_data) > 3 else None

            result = await collect_player_pitches(session, player_id, name, pa_count)
            batch_total += result

            # Small delay between players to avoid overwhelming the API
            await asyncio.sleep(0.5)

        logging.info(f"  2024 Batch {batch_num} complete: {batch_total} total pitches")
        return batch_total

def main():
    print("\n" + "="*70)
    print("ROBUST 2024 PITCH COLLECTION - DEDICATED")
    print(f"Started: {datetime.now()}")
    print("="*70)

    # Initialize connection pool
    init_connection_pool()

    # Get prospects that need 2024 pitch data
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT p.mlb_player_id, p.name, p.organization,
               COUNT(DISTINCT mpa.id) as pa_count
        FROM prospects p
        JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
        LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id
            AND mbp.season = 2024
        WHERE mpa.season = 2024
            AND p.mlb_player_id IS NOT NULL
            AND mbp.id IS NULL
        GROUP BY p.mlb_player_id, p.name, p.organization
        HAVING COUNT(DISTINCT mpa.id) > 0
        ORDER BY COUNT(DISTINCT mpa.id) DESC
    """)

    prospects_2024 = cur.fetchall()
    print(f"\nFound {len(prospects_2024)} prospects needing 2024 pitch data")

    if len(prospects_2024) > 0:
        print(f"\nTop 10 prospects by PA count:")
        for player_id, name, org, pa_count in prospects_2024[:10]:
            print(f"  {name:30} ({org:3}) - {pa_count:4} PAs")

    cur.close()
    return_connection(conn)

    # Process 2024 data
    if prospects_2024:
        print(f"\n=== COLLECTING 2024 PITCH DATA ===")
        batch_size = 5  # Smaller batches for better reliability
        batches = [prospects_2024[i:i+batch_size] for i in range(0, len(prospects_2024), batch_size)]

        total_collected = 0
        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            try:
                batch_result = asyncio.run(collect_batch(batch, i, len(batches)))
                total_collected += batch_result

                # Progress report every 5 batches
                if i % 5 == 0:
                    elapsed = time.time() - start_time
                    rate = total_collected / elapsed if elapsed > 0 else 0
                    eta = (len(batches) - i) * (elapsed / i) if i > 0 else 0

                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2024")
                    total_2024 = cur.fetchone()[0]
                    cur.close()
                    return_connection(conn)

                    print(f"\n[PROGRESS] Completed {i}/{len(batches)} batches")
                    print(f"  Total 2024 pitches in DB: {total_2024:,}")
                    print(f"  New pitches collected: {total_collected:,}")
                    print(f"  Collection rate: {rate:.1f} pitches/sec")
                    print(f"  ETA: {eta/60:.1f} minutes")

            except Exception as e:
                logging.error(f"Batch {i} failed: {e}")
                continue

    # Final report
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2024")
    total_2024 = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season = 2024")
    unique_players = cur.fetchone()[0]

    cur.close()
    return_connection(conn)

    # Close the connection pool
    if connection_pool:
        connection_pool.closeall()

    print("\n" + "="*70)
    print("2024 COLLECTION COMPLETE")
    print(f"Total 2024 pitch records: {total_2024:,}")
    print(f"Unique players with 2024 data: {unique_players:,}")
    print(f"Ended: {datetime.now()}")
    print("="*70)

if __name__ == "__main__":
    main()