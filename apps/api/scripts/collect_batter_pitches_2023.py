import asyncio
import aiohttp
import psycopg2
from psycopg2 import pool
import logging
from datetime import datetime
import time
from typing import List, Dict, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2023

# Create connection pool
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 10,
    DB_URL,
    connect_timeout=30
)

async def get_batter_games(session: aiohttp.ClientSession, batter_id: int) -> List[Dict]:
    """Get all games for a batter in 2023"""
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',  # Key: 'hitting' for batters
        'gameType': 'R',
        'season': SEASON,
        'language': 'en'
    }

    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('stats') and data['stats'][0].get('splits'):
                    games = []
                    for split in data['stats'][0]['splits']:
                        games.append({
                            'gamePk': split['game']['gamePk'],
                            'date': split.get('date'),
                            'pas': split['stat'].get('plateAppearances', 0)
                        })
                    return games
    except:
        pass
    return []

async def collect_game_pitches(session: aiohttp.ClientSession, batter_id: int, game_info: Dict) -> List[Tuple]:
    """Collect all pitches faced by batter in a single game"""
    game_pk = game_info['gamePk']
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=30) as response:
            if response.status != 200:
                return []

            data = await response.json()
            game_date = data.get('gameData', {}).get('datetime', {}).get('officialDate', game_info['date'])
            all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

            game_pitches = []

            for play in all_plays:
                matchup = play.get('matchup', {})

                # Only process plays where our batter was batting
                if matchup.get('batter', {}).get('id') != batter_id:
                    continue

                pitcher_id = matchup.get('pitcher', {}).get('id')
                at_bat_index = play.get('atBatIndex', 0)
                inning = play.get('about', {}).get('inning', 0)

                play_events = play.get('playEvents', [])

                for i, event in enumerate(play_events):
                    # Check if this is a pitch
                    if not event.get('isPitch'):
                        continue

                    pitch_data = event.get('pitchData', {})
                    details = event.get('details', {})
                    count = event.get('count', {})

                    # Create pitch record tuple for milb_batter_pitches table
                    pitch_record = (
                        batter_id,   # mlb_batter_id
                        pitcher_id,  # mlb_pitcher_id
                        game_pk,     # game_pk
                        game_date,   # game_date
                        SEASON,      # season
                        'MiLB',      # level
                        at_bat_index,  # at_bat_index
                        i + 1,       # pitch_number
                        inning,      # inning
                        details.get('type', {}).get('code'),  # pitch_type
                        pitch_data.get('startSpeed'),  # start_speed
                        pitch_data.get('breaks', {}).get('spinRate'),  # spin_rate
                        pitch_data.get('zone'),  # zone
                        details.get('call', {}).get('code'),  # pitch_call
                        details.get('description'),  # pitch_result
                        details.get('isStrike', False),  # is_strike
                        count.get('balls', 0),  # balls
                        count.get('strikes', 0),  # strikes
                        datetime.now()  # created_at
                    )

                    game_pitches.append(pitch_record)

            return game_pitches

    except Exception as e:
        logger.debug(f"      Error in game {game_pk}: {str(e)}")
        return []

async def collect_batter_data(session: aiohttp.ClientSession, batter_id: int, batter_name: str, org: str) -> int:
    """Collect all 2023 pitches for a batter"""

    # Get games for 2023
    games = await get_batter_games(session, batter_id)

    if not games:
        return 0

    expected_pas = sum(g['pas'] for g in games)
    logger.info(f"  {batter_name} ({org}): {len(games)} games, {expected_pas} PAs")

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Check if we already have data for this batter
        cur.execute("""
            SELECT COUNT(*) FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = %s
        """, (batter_id, SEASON))
        existing = cur.fetchone()[0]

        if existing > 100:  # Skip if we already have substantial data
            logger.info(f"    -> Already have {existing} pitches, skipping")
            return 0

        total_collected = 0

        for game_info in games:
            # Collect pitches for this game
            game_pitches = await collect_game_pitches(session, batter_id, game_info)

            if game_pitches:
                # Insert into database
                try:
                    cur.executemany("""
                        INSERT INTO milb_batter_pitches (
                            mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                            level, at_bat_index, pitch_number, inning,
                            pitch_type, start_speed, spin_rate, zone,
                            pitch_call, pitch_result, is_strike,
                            balls, strikes, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_batter_id) DO NOTHING
                    """, game_pitches)
                    conn.commit()
                    total_collected += len(game_pitches)
                except Exception as e:
                    logger.error(f"    DB error for {batter_name}: {str(e)}")
                    conn.rollback()

        if total_collected > 0:
            logger.info(f"    -> Collected {total_collected} pitches")

        return total_collected

    finally:
        connection_pool.putconn(conn)

async def process_batch(batters: List[Tuple], batch_num: int, total_batches: int):
    """Process a batch of batters"""
    async with aiohttp.ClientSession() as session:
        tasks = []

        for name, mlb_id, org in batters:
            if mlb_id:  # Skip NULL IDs
                task = collect_batter_data(session, int(mlb_id), name, org)
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_pitches = 0
        for result in results:
            if isinstance(result, int):
                total_pitches += result
            elif isinstance(result, Exception):
                logger.error(f"  Batch error: {str(result)}")

        logger.info(f"  Batch {batch_num}/{total_batches} complete: {total_pitches} pitches collected")
        return total_pitches

def main():
    print("=" * 80)
    print("BATTER PITCH DATA COLLECTION - 2023 SEASON (MISSING DATA ONLY)")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Get batters with 2023 PAs but missing pitch data
        cur.execute("""
            SELECT DISTINCT p.name, p.mlb_player_id, p.organization
            FROM prospects p
            JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
            LEFT JOIN milb_batter_pitches mbp ON mpa.mlb_player_id = mbp.mlb_batter_id
                                               AND mpa.season = mbp.season
            WHERE mpa.season = 2023
            AND mbp.mlb_batter_id IS NULL
            AND p.position NOT IN ('P', 'SP', 'RP', 'LHP', 'RHP')
            AND p.mlb_player_id IS NOT NULL
            ORDER BY p.name
        """)
        missing_batters = cur.fetchall()

        print(f"\nFound {len(missing_batters)} batters missing 2023 pitch data")

        if len(missing_batters) > 0:
            print("\nSample of missing batters:")
            for name, _, org in missing_batters[:10]:
                print(f"  {name} ({org})")

        # Current status
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_batter_id), COUNT(*)
            FROM milb_batter_pitches
            WHERE season = 2023
        """)
        batters, pitches = cur.fetchone()
        print(f"\nCurrent 2023: {batters} batters, {pitches:,} pitches")

        print(f"\n=== STARTING 2023 COLLECTION FOR MISSING BATTERS ===\n")

        # Process in batches
        batch_size = 5
        batches = [missing_batters[i:i+batch_size] for i in range(0, len(missing_batters), batch_size)]

        total_collected = 0
        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            logger.info(f"\n=== BATCH {i}/{len(batches)}: {len(batch)} batters ===")

            pitches = asyncio.run(process_batch(batch, i, len(batches)))
            total_collected += pitches

            # Progress report every 5 batches (since fewer total batches)
            if i % 5 == 0 or i == len(batches):
                elapsed = time.time() - start_time
                rate = total_collected / elapsed if elapsed > 0 else 0
                eta = (len(batches) - i) * (elapsed / i) / 60 if i > 0 else 0

                print(f"\n[PROGRESS] Batch {i}/{len(batches)}")
                print(f"  New pitches: {total_collected:,}")
                print(f"  Rate: {rate:.1f} pitches/sec")
                print(f"  ETA: {eta:.1f} minutes")

                # Current DB total
                cur.execute("""
                    SELECT COUNT(DISTINCT mlb_batter_id), COUNT(*)
                    FROM milb_batter_pitches
                    WHERE season = 2023
                """)
                batters, pitches = cur.fetchone()
                print(f"  2023 in DB: {batters} batters, {pitches:,} pitches")

        print("\n" + "=" * 80)
        print("2023 BATTER COLLECTION COMPLETE")
        print("=" * 80)

        # Final statistics
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_batter_id), COUNT(*)
            FROM milb_batter_pitches
            WHERE season = 2023
        """)
        batters, pitches = cur.fetchone()
        print(f"\n2023 Final: {batters} batters, {pitches:,} pitches")
        print(f"New in this run: {total_collected:,} pitches")

        # Check remaining gaps
        cur.execute("""
            SELECT COUNT(DISTINCT p.mlb_player_id)
            FROM prospects p
            JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
            LEFT JOIN milb_batter_pitches mbp ON mpa.mlb_player_id = mbp.mlb_batter_id
                                               AND mpa.season = mbp.season
            WHERE mpa.season = 2023
            AND mbp.mlb_batter_id IS NULL
            AND p.position NOT IN ('P', 'SP', 'RP', 'LHP', 'RHP')
        """)
        remaining = cur.fetchone()[0]
        print(f"Remaining gaps: {remaining} batters")

    finally:
        connection_pool.putconn(conn)
        connection_pool.closeall()

    print(f"\nEnded: {datetime.now()}")
    print("=" * 80)

if __name__ == "__main__":
    main()