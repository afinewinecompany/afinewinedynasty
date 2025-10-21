import asyncio
import aiohttp
import psycopg2
from psycopg2 import pool
import logging
from datetime import datetime
import time
from typing import List, Dict, Tuple, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASONS = [2025, 2024, 2023]

# Create connection pool
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 10,
    DB_URL,
    connect_timeout=30
)

logger.info("Database connection pool initialized")

async def get_all_pitcher_games(session: aiohttp.ClientSession, pitcher_id: int, pitcher_name: str) -> Dict[int, List[Dict]]:
    """Get ALL games where pitcher appeared across all seasons"""
    all_games = {}

    for season in SEASONS:
        url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'pitching',
            'gameType': 'R',
            'season': season,
            'language': 'en'
        }

        try:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('stats') and data['stats'][0].get('splits'):
                        games = []
                        for split in data['stats'][0]['splits']:
                            game_info = {
                                'gamePk': split['game']['gamePk'],
                                'date': split.get('date'),
                                'inningsPitched': split['stat'].get('inningsPitched', 0),
                                'numberOfPitches': split['stat'].get('numberOfPitches', 0)
                            }
                            games.append(game_info)

                        if games:
                            all_games[season] = games
                            logger.debug(f"  {pitcher_name}: Found {len(games)} games in {season} (Total pitches: {sum(g['numberOfPitches'] for g in games)})")

        except asyncio.TimeoutError:
            logger.debug(f"    Timeout getting games for {pitcher_name} in {season}")
        except Exception as e:
            logger.debug(f"    Error getting games for {pitcher_name} in {season}: {str(e)}")

    return all_games

async def collect_game_pitches(
    session: aiohttp.ClientSession,
    pitcher_id: int,
    game_info: Dict,
    season: int
) -> List[Tuple]:
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

                # Check if our pitcher was pitching
                if matchup.get('pitcher', {}).get('id') != pitcher_id:
                    continue

                batter_id = matchup.get('batter', {}).get('id')
                at_bat_index = play.get('atBatIndex', 0)
                inning = play.get('about', {}).get('inning', 0)
                half_inning = play.get('about', {}).get('halfInning', '')
                outs = play.get('count', {}).get('outs', 0)

                # Get PA result for final pitch
                pa_result = play.get('result', {}).get('eventType')
                pa_result_desc = play.get('result', {}).get('description')

                play_events = play.get('playEvents', [])
                num_events = len(play_events)

                for i, event in enumerate(play_events):
                    # Check both isPitch and presence of pitchData
                    if not (event.get('isPitch') or 'pitchData' in event):
                        continue

                    pitch_data = event.get('pitchData', {})
                    details = event.get('details', {})
                    count = event.get('count', {})

                    # Check if this is the final pitch of the PA
                    is_final = (i == num_events - 1)

                    # Build pitch record
                    pitch_record = (
                        pitcher_id,  # mlb_pitcher_id
                        batter_id,   # mlb_batter_id
                        game_pk,     # game_pk
                        game_date,   # game_date
                        season,      # season
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
                        details.get('isInPlay', False) or details.get('code') in ['X', 'D', 'E', 'F'],  # contact
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

                    # If ball was hit into play, try to get hit data
                    if details.get('isInPlay'):
                        hit_data = event.get('hitData', {})
                        if hit_data:
                            pitch_record = pitch_record[:37] + (
                                hit_data.get('launchSpeed'),
                                hit_data.get('launchAngle'),
                                hit_data.get('totalDistance'),
                                hit_data.get('trajectory'),
                                hit_data.get('hardness'),
                                datetime.now()
                            )

                    game_pitches.append(pitch_record)

            return game_pitches

    except asyncio.TimeoutError:
        logger.debug(f"      Game {game_pk}: Timeout")
    except Exception as e:
        logger.debug(f"      Game {game_pk}: {str(e)}")

    return []

async def collect_pitcher_all_data(
    session: aiohttp.ClientSession,
    pitcher_id: int,
    pitcher_name: str,
    org: str
) -> int:
    """Collect ALL pitch data for a pitcher across all seasons"""

    # First get ALL games
    all_games = await get_all_pitcher_games(session, pitcher_id, pitcher_name)

    if not all_games:
        return 0

    total_games = sum(len(games) for games in all_games.values())
    expected_pitches = sum(sum(g['numberOfPitches'] for g in games) for games in all_games.values())

    logger.info(f"  {pitcher_name} ({org}): {total_games} games across {list(all_games.keys())} (Expected: {expected_pitches} pitches)")

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        total_collected = 0
        games_with_data = 0

        for season, games in all_games.items():
            season_pitches = 0

            for game_info in games:
                # Collect pitches for this game
                game_pitches = await collect_game_pitches(session, pitcher_id, game_info, season)

                if game_pitches:
                    # Insert into database
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

                    season_pitches += len(game_pitches)
                    games_with_data += 1

            if season_pitches > 0:
                logger.info(f"    {season}: Collected {season_pitches} pitches from {len(games)} games")
                total_collected += season_pitches

        if total_collected > 0:
            success_rate = (total_collected / expected_pitches * 100) if expected_pitches > 0 else 0
            logger.info(f"    TOTAL: {total_collected}/{expected_pitches} pitches ({success_rate:.1f}% success rate)")

        return total_collected

    finally:
        connection_pool.putconn(conn)

async def process_batch(pitchers: List[Tuple], batch_num: int, total_batches: int):
    """Process a batch of pitchers"""
    async with aiohttp.ClientSession() as session:
        tasks = []

        for name, mlb_id, org in pitchers:
            if mlb_id:  # Skip NULL IDs
                task = collect_pitcher_all_data(session, int(mlb_id), name, org)
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_pitches = 0
        for result in results:
            if isinstance(result, int):
                total_pitches += result
            elif isinstance(result, Exception):
                logger.error(f"  Error in batch: {str(result)}")

        logger.info(f"  Batch {batch_num}/{total_batches} complete: {total_pitches} total pitches collected")
        return total_pitches

def main():
    print("=" * 80)
    print("COMPLETE PITCHER DATA COLLECTION - ALL GAMES, ALL SEASONS")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Get all pitchers from prospects table
        cur.execute("""
            SELECT name, mlb_player_id, organization
            FROM prospects
            WHERE position IN ('P', 'RHP', 'LHP', 'RP', 'SP')
            AND mlb_player_id IS NOT NULL
            ORDER BY name
        """)
        all_pitchers = cur.fetchall()

        print(f"\nFound {len(all_pitchers)} pitchers with valid MLB IDs")

        # Show current status
        cur.execute("""
            SELECT season, COUNT(DISTINCT mlb_pitcher_id) as pitchers, COUNT(*) as pitches
            FROM milb_pitcher_pitches
            GROUP BY season
            ORDER BY season DESC
        """)
        for season, pitchers, pitches in cur.fetchall():
            print(f"Current {season}: {pitchers} pitchers, {pitches:,} pitches")

        print(f"\n=== STARTING COMPREHENSIVE COLLECTION ===\n")

        # Process in smaller batches for better monitoring
        batch_size = 3  # Smaller batches for better progress tracking
        batches = [all_pitchers[i:i+batch_size] for i in range(0, len(all_pitchers), batch_size)]

        total_collected = 0
        start_time = time.time()

        for i, batch in enumerate(batches, 1):
            logger.info(f"\n=== BATCH {i}/{len(batches)}: Processing {len(batch)} pitchers ===")

            # Show who we're processing
            for name, mlb_id, org in batch:
                logger.info(f"  - {name} ({org}) - ID: {mlb_id}")

            pitches = asyncio.run(process_batch(batch, i, len(batches)))
            total_collected += pitches

            # Progress report every 5 batches
            if i % 5 == 0 or i == len(batches):
                elapsed = time.time() - start_time
                rate = total_collected / elapsed if elapsed > 0 else 0
                remaining_batches = len(batches) - i
                eta = remaining_batches * (elapsed / i) / 60 if i > 0 else 0

                print(f"\n[PROGRESS UPDATE - Batch {i}/{len(batches)}]")
                print(f"  Pitchers processed: {i * batch_size}/{len(all_pitchers)}")
                print(f"  New pitches collected: {total_collected:,}")
                print(f"  Collection rate: {rate:.1f} pitches/sec")
                print(f"  ETA: {eta:.1f} minutes")

                # Current database totals
                for season in SEASONS:
                    cur.execute("""
                        SELECT COUNT(DISTINCT mlb_pitcher_id), COUNT(*)
                        FROM milb_pitcher_pitches
                        WHERE season = %s
                    """, (season,))
                    pitchers, pitches = cur.fetchone()
                    if pitches > 0:
                        print(f"  {season} total: {pitchers} pitchers, {pitches:,} pitches")

        print("\n" + "=" * 80)
        print("COLLECTION COMPLETE")
        print("=" * 80)

        # Final statistics
        print("\n### FINAL RESULTS ###")

        grand_total = 0
        all_pitchers_with_data = set()

        for season in SEASONS:
            cur.execute("""
                SELECT COUNT(DISTINCT mlb_pitcher_id), COUNT(*)
                FROM milb_pitcher_pitches
                WHERE season = %s
            """, (season,))
            pitchers, pitches = cur.fetchone()
            print(f"\n{season}:")
            print(f"  Pitchers with data: {pitchers}")
            print(f"  Total pitches: {pitches:,}")
            grand_total += pitches

            # Get pitcher names
            cur.execute("""
                SELECT DISTINCT p.name, COUNT(*) as pitch_count
                FROM milb_pitcher_pitches mpp
                JOIN prospects p ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
                WHERE mpp.season = %s
                GROUP BY p.name
                ORDER BY pitch_count DESC
                LIMIT 3
            """, (season,))
            top_pitchers = cur.fetchall()
            if top_pitchers:
                print(f"  Top pitchers:")
                for name, count in top_pitchers:
                    print(f"    - {name}: {count:,} pitches")

            cur.execute("SELECT DISTINCT mlb_pitcher_id FROM milb_pitcher_pitches WHERE season = %s", (season,))
            for (pid,) in cur.fetchall():
                all_pitchers_with_data.add(pid)

        print(f"\n### GRAND TOTALS ###")
        print(f"Total unique pitchers with data: {len(all_pitchers_with_data)}")
        print(f"Total pitches collected: {grand_total:,}")
        print(f"New pitches in this run: {total_collected:,}")
        print(f"Success rate: {len(all_pitchers_with_data)}/{len(all_pitchers)} pitchers ({len(all_pitchers_with_data)/len(all_pitchers)*100:.1f}%)")

    finally:
        connection_pool.putconn(conn)
        connection_pool.closeall()

    print(f"\nEnded: {datetime.now()}")
    print("=" * 80)

if __name__ == "__main__":
    main()