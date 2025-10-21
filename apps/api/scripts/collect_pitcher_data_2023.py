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

async def get_pitcher_games(session: aiohttp.ClientSession, pitcher_id: int) -> List[Dict]:
    """Get all games for a pitcher in 2023"""
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'pitching',
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
                            'pitches': split['stat'].get('numberOfPitches', 0)
                        })
                    return games
    except:
        pass
    return []

async def collect_game_pitches(session: aiohttp.ClientSession, pitcher_id: int, game_info: Dict) -> List[Tuple]:
    """Collect all pitches from a single game"""
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

                # Only process plays where our pitcher was pitching
                if matchup.get('pitcher', {}).get('id') != pitcher_id:
                    continue

                batter_id = matchup.get('batter', {}).get('id')
                at_bat_index = play.get('atBatIndex', 0)
                inning = play.get('about', {}).get('inning', 0)
                half_inning = play.get('about', {}).get('halfInning', '')

                # Get PA result info
                pa_result = play.get('result', {}).get('eventType')
                pa_result_desc = play.get('result', {}).get('description')

                play_events = play.get('playEvents', [])
                num_events = len(play_events)

                for i, event in enumerate(play_events):
                    # Check if this is a pitch
                    if not event.get('isPitch'):
                        continue

                    pitch_data = event.get('pitchData', {})
                    details = event.get('details', {})
                    count = event.get('count', {})

                    # Determine if final pitch
                    is_final = (i == num_events - 1)

                    # Get outs from the correct location
                    outs = count.get('outs', 0)

                    # Create pitch record tuple (44 fields total)
                    pitch_record = (
                        pitcher_id,  # mlb_pitcher_id
                        batter_id,   # mlb_batter_id
                        game_pk,     # game_pk
                        game_date,   # game_date
                        SEASON,      # season
                        'MiLB',      # level
                        at_bat_index,  # at_bat_index
                        i + 1,       # pitch_number
                        inning,      # inning
                        half_inning, # half_inning
                        details.get('type', {}).get('code'),  # pitch_type
                        details.get('type', {}).get('description'),  # pitch_type_description
                        pitch_data.get('startSpeed'),  # start_speed
                        pitch_data.get('endSpeed'),    # end_speed
                        pitch_data.get('breaks', {}).get('breakX'),  # pfx_x
                        pitch_data.get('breaks', {}).get('breakY'),  # pfx_z
                        pitch_data.get('coordinates', {}).get('releasePos', {}).get('x'),  # release_pos_x
                        pitch_data.get('coordinates', {}).get('releasePos', {}).get('y'),  # release_pos_y
                        pitch_data.get('coordinates', {}).get('releasePos', {}).get('z'),  # release_pos_z
                        pitch_data.get('releaseExtension'),  # release_extension
                        pitch_data.get('breaks', {}).get('spinRate'),  # spin_rate
                        pitch_data.get('breaks', {}).get('spinDirection'),  # spin_direction
                        pitch_data.get('coordinates', {}).get('pX'),  # plate_x
                        pitch_data.get('coordinates', {}).get('pZ'),  # plate_z
                        pitch_data.get('zone'),  # zone
                        details.get('call', {}).get('code'),  # pitch_call
                        details.get('description'),  # pitch_result
                        details.get('isStrike', False),  # is_strike
                        count.get('balls', 0),  # balls
                        count.get('strikes', 0),  # strikes
                        outs,  # outs
                        details.get('code') in ['S', 'X', 'F', 'T', 'L', 'M', 'W'],  # swing
                        details.get('isInPlay', False),  # contact
                        details.get('code') == 'S',  # swing_and_miss
                        details.get('code') in ['F', 'T', 'L'],  # foul
                        is_final,  # is_final_pitch
                        pa_result if is_final else None,  # pa_result
                        pa_result_desc if is_final else None,  # pa_result_description
                        None,  # launch_speed
                        None,  # launch_angle
                        None,  # total_distance
                        None,  # trajectory
                        None,  # hardness
                        datetime.now()  # created_at
                    )

                    # If ball in play, try to add hit data - FIXED INDEX
                    if details.get('isInPlay'):
                        hit_data = event.get('hitData', {})
                        if hit_data:
                            # Use index 38 to keep first 38 fields, then add 6 more = 44 total
                            pitch_record = pitch_record[:38] + (
                                hit_data.get('launchSpeed'),
                                hit_data.get('launchAngle'),
                                hit_data.get('totalDistance'),
                                hit_data.get('trajectory'),
                                hit_data.get('hardness'),
                                datetime.now()
                            )

                    game_pitches.append(pitch_record)

            return game_pitches

    except Exception as e:
        logger.debug(f"      Error in game {game_pk}: {str(e)}")
        return []

async def collect_pitcher_data(session: aiohttp.ClientSession, pitcher_id: int, pitcher_name: str, org: str) -> int:
    """Collect all 2023 pitches for a pitcher"""

    # Get games for 2023
    games = await get_pitcher_games(session, pitcher_id)

    if not games:
        return 0

    expected_pitches = sum(g['pitches'] for g in games)
    logger.info(f"  {pitcher_name} ({org}): {len(games)} games, {expected_pitches} expected pitches")

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()
        total_collected = 0

        for game_info in games:
            # Collect pitches for this game
            game_pitches = await collect_game_pitches(session, pitcher_id, game_info)

            if game_pitches:
                # Insert into database
                try:
                    cur.executemany("""
                        INSERT INTO milb_pitcher_pitches (
                            mlb_pitcher_id, mlb_batter_id, game_pk, game_date, season,
                            level, at_bat_index, pitch_number, inning, half_inning,
                            pitch_type, pitch_type_description, start_speed, end_speed,
                            pfx_x, pfx_z, release_pos_x, release_pos_y, release_pos_z,
                            release_extension, spin_rate, spin_direction, plate_x, plate_z,
                            zone, pitch_call, pitch_result, is_strike, balls, strikes,
                            outs, swing, contact, swing_and_miss, foul, is_final_pitch,
                            pa_result, pa_result_description, launch_speed, launch_angle,
                            total_distance, trajectory, hardness, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s
                        )
                        ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_pitcher_id) DO NOTHING
                    """, game_pitches)
                    conn.commit()
                    total_collected += len(game_pitches)
                except Exception as e:
                    logger.error(f"    DB error for {pitcher_name}: {str(e)}")
                    conn.rollback()

        if total_collected > 0:
            success_rate = (total_collected / expected_pitches * 100) if expected_pitches > 0 else 0
            logger.info(f"    -> Collected {total_collected}/{expected_pitches} pitches ({success_rate:.1f}%)")

        return total_collected

    finally:
        connection_pool.putconn(conn)

async def process_batch(pitchers: List[Tuple], batch_num: int, total_batches: int):
    """Process a batch of pitchers"""
    async with aiohttp.ClientSession() as session:
        tasks = []

        for name, mlb_id, org in pitchers:
            if mlb_id:  # Skip NULL IDs
                task = collect_pitcher_data(session, int(mlb_id), name, org)
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
    print("PITCHER DATA COLLECTION - 2023 SEASON")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Get all pitchers
        cur.execute("""
            SELECT name, mlb_player_id, organization
            FROM prospects
            WHERE position IN ('P', 'RHP', 'LHP', 'RP', 'SP')
            AND mlb_player_id IS NOT NULL
            ORDER BY name
        """)
        all_pitchers = cur.fetchall()

        print(f"\nFound {len(all_pitchers)} pitchers to process for 2023")

        # Current status
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_pitcher_id), COUNT(*)
            FROM milb_pitcher_pitches
            WHERE season = 2023
        """)
        pitchers, pitches = cur.fetchone()
        print(f"Current 2023: {pitchers} pitchers, {pitches:,} pitches")

        print(f"\n=== STARTING 2023 COLLECTION ===\n")

        # Process in batches
        batch_size = 5
        batches = [all_pitchers[i:i+batch_size] for i in range(0, len(all_pitchers), batch_size)]

        total_collected = 0
        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            logger.info(f"\n=== BATCH {i}/{len(batches)}: {len(batch)} pitchers ===")

            pitches = asyncio.run(process_batch(batch, i, len(batches)))
            total_collected += pitches

            # Progress report every 10 batches
            if i % 10 == 0:
                elapsed = time.time() - start_time
                rate = total_collected / elapsed if elapsed > 0 else 0
                eta = (len(batches) - i) * (elapsed / i) / 60 if i > 0 else 0

                print(f"\n[PROGRESS] Batch {i}/{len(batches)}")
                print(f"  New pitches: {total_collected:,}")
                print(f"  Rate: {rate:.1f} pitches/sec")
                print(f"  ETA: {eta:.1f} minutes")

                # Current DB total
                cur.execute("""
                    SELECT COUNT(DISTINCT mlb_pitcher_id), COUNT(*)
                    FROM milb_pitcher_pitches
                    WHERE season = 2023
                """)
                pitchers, pitches = cur.fetchone()
                print(f"  2023 in DB: {pitchers} pitchers, {pitches:,} pitches")

        print("\n" + "=" * 80)
        print("2023 COLLECTION COMPLETE")
        print("=" * 80)

        # Final statistics
        cur.execute("""
            SELECT COUNT(DISTINCT mlb_pitcher_id), COUNT(*)
            FROM milb_pitcher_pitches
            WHERE season = 2023
        """)
        pitchers, pitches = cur.fetchone()
        print(f"\n2023 Final: {pitchers} pitchers, {pitches:,} pitches")
        print(f"New in this run: {total_collected:,} pitches")

        # Top pitchers
        cur.execute("""
            SELECT p.name, COUNT(*) as pitch_count
            FROM milb_pitcher_pitches mpp
            JOIN prospects p ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
            WHERE mpp.season = 2023
            GROUP BY p.name
            ORDER BY pitch_count DESC
            LIMIT 10
        """)
        top_pitchers = cur.fetchall()
        if top_pitchers:
            print("\nTop 10 pitchers by pitch count:")
            for name, count in top_pitchers:
                print(f"  {name:30} - {count:,} pitches")

    finally:
        connection_pool.putconn(conn)
        connection_pool.closeall()

    print(f"\nEnded: {datetime.now()}")
    print("=" * 80)

if __name__ == "__main__":
    main()