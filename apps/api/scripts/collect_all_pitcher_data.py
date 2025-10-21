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

async def get_pitcher_games(session: aiohttp.ClientSession, pitcher_id: int, season: int) -> List[int]:
    """Get list of games where pitcher appeared in a specific season"""
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'pitching',  # Key: using 'pitching' group for pitchers
        'gameType': 'R',  # Regular season MiLB
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
                        game_pk = split['game']['gamePk']
                        games.append(game_pk)
                    return games
    except asyncio.TimeoutError:
        logger.debug(f"    Timeout getting games for pitcher {pitcher_id} in {season}")
    except Exception as e:
        logger.debug(f"    Error getting games for pitcher {pitcher_id} in {season}: {str(e)}")

    return []

async def collect_pitcher_pitches_for_season(
    session: aiohttp.ClientSession,
    pitcher_id: int,
    pitcher_name: str,
    org: str,
    season: int
) -> int:
    """Collect pitch data for a single pitcher for a specific season"""
    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Check if we already have data for this pitcher and season
        cur.execute("""
            SELECT COUNT(*) FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id = %s AND season = %s
        """, (pitcher_id, season))
        existing_count = cur.fetchone()[0]
        if existing_count > 100:  # Skip if we already have substantial data
            logger.debug(f"    Skipping {pitcher_name} {season} - already have {existing_count} pitches")
            return 0

        # Get pitcher's games for this season
        games = await get_pitcher_games(session, pitcher_id, season)

        if not games:
            return 0

        total_pitches = 0
        successful_games = 0

        for game_pk in games:
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

            try:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        continue

                    data = await response.json()

                    # Get game date
                    game_date = data.get('gameData', {}).get('datetime', {}).get('officialDate')

                    all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                    game_pitches = []
                    for play in all_plays:
                        # Check if our pitcher was pitching
                        matchup = play.get('matchup', {})
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
                            if not event.get('isPitch'):
                                continue

                            pitch_data = event.get('pitchData', {})
                            details = event.get('details', {})
                            count = event.get('count', {})

                            # Check if this is the final pitch of the PA
                            is_final = (i == num_events - 1)

                            # Prepare pitch record with all available fields
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
                                None,  # launch_speed (will update if available)
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
                                    # Update the record with hit data
                                    pitch_record = pitch_record[:37] + (
                                        hit_data.get('launchSpeed'),
                                        hit_data.get('launchAngle'),
                                        hit_data.get('totalDistance'),
                                        hit_data.get('trajectory'),
                                        hit_data.get('hardness'),
                                        datetime.now()
                                    )

                            game_pitches.append(pitch_record)

                    # Insert pitches
                    if game_pitches:
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
                        total_pitches += len(game_pitches)
                        successful_games += 1

            except asyncio.TimeoutError:
                logger.debug(f"      Game {game_pk}: Timeout")
                continue
            except Exception as e:
                logger.debug(f"      Game {game_pk}: {str(e)}")
                continue

        if total_pitches > 0:
            logger.info(f"    {pitcher_name} ({org}) {season}: Collected {total_pitches} pitches from {successful_games}/{len(games)} games")

        return total_pitches

    finally:
        connection_pool.putconn(conn)

async def collect_pitcher_all_seasons(
    session: aiohttp.ClientSession,
    pitcher_id: int,
    pitcher_name: str,
    org: str
) -> Dict[int, int]:
    """Collect pitch data for all seasons for a single pitcher"""
    results = {}
    for season in SEASONS:
        pitches = await collect_pitcher_pitches_for_season(session, pitcher_id, pitcher_name, org, season)
        results[season] = pitches

    total = sum(results.values())
    if total > 0:
        season_summary = ", ".join([f"{s}:{p}" for s, p in results.items() if p > 0])
        logger.info(f"  {pitcher_name} ({org}): Total {total} pitches ({season_summary})")

    return results

async def process_batch(pitchers: List[Tuple], batch_num: int, total_batches: int):
    """Process a batch of pitchers for all seasons"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for name, mlb_id, org in pitchers:
            if mlb_id:  # Skip NULL IDs
                task = collect_pitcher_all_seasons(session, int(mlb_id), name, org)
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_pitches = 0
        for result in results:
            if isinstance(result, dict):
                total_pitches += sum(result.values())

        logger.info(f"  Batch {batch_num}/{total_batches} complete: {total_pitches} total pitches")
        return total_pitches

def main():
    print("=" * 80)
    print("COMPREHENSIVE PITCHER DATA COLLECTION - 2023, 2024, 2025")
    print(f"Started: {datetime.now()}")
    print("=" * 80)

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Get all pitchers from prospects table (filter out NULL mlb_player_id)
        cur.execute("""
            SELECT name, mlb_player_id, organization
            FROM prospects
            WHERE position IN ('P', 'RHP', 'LHP', 'RP', 'SP')
            AND mlb_player_id IS NOT NULL
            ORDER BY name
        """)
        all_pitchers = cur.fetchall()

        print(f"\nFound {len(all_pitchers)} pitchers with valid MLB IDs")

        # Check current data status
        for season in SEASONS:
            cur.execute("""
                SELECT COUNT(DISTINCT mlb_pitcher_id), COUNT(*)
                FROM milb_pitcher_pitches
                WHERE season = %s
            """, (season,))
            pitchers, pitches = cur.fetchone()
            print(f"{season}: {pitchers} pitchers, {pitches:,} pitches")

        print(f"\n=== COLLECTING PITCHER DATA FOR {', '.join(map(str, SEASONS))} ===\n")

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
                remaining_batches = len(batches) - i
                eta = remaining_batches * (elapsed / i) / 60

                print(f"\n[PROGRESS] Completed {i}/{len(batches)} batches")
                print(f"  New pitches collected: {total_collected:,}")
                print(f"  Collection rate: {rate:.1f} pitches/sec")
                print(f"  ETA: {eta:.1f} minutes")

                # Show current DB totals
                for season in SEASONS:
                    cur.execute("""
                        SELECT COUNT(*), COUNT(DISTINCT mlb_pitcher_id)
                        FROM milb_pitcher_pitches
                        WHERE season = %s
                    """, (season,))
                    total_pitches, total_pitchers = cur.fetchone()
                    print(f"  {season} in DB: {total_pitchers} pitchers, {total_pitches:,} pitches")

        print("\n" + "=" * 80)
        print("PITCHER COLLECTION COMPLETE")
        print("=" * 80)

        # Final statistics
        for season in SEASONS:
            cur.execute("""
                SELECT COUNT(*), COUNT(DISTINCT mlb_pitcher_id)
                FROM milb_pitcher_pitches
                WHERE season = %s
            """, (season,))
            total_pitches, total_pitchers = cur.fetchone()
            print(f"\n{season} Final:")
            print(f"  Total pitches: {total_pitches:,}")
            print(f"  Unique pitchers: {total_pitchers}")

            # Show top pitchers for this season
            cur.execute("""
                SELECT p.name, COUNT(*) as pitch_count
                FROM milb_pitcher_pitches mpp
                JOIN prospects p ON p.mlb_player_id::INTEGER = mpp.mlb_pitcher_id
                WHERE mpp.season = %s
                GROUP BY p.name
                ORDER BY pitch_count DESC
                LIMIT 5
            """, (season,))
            top_pitchers = cur.fetchall()
            if top_pitchers:
                print(f"  Top pitchers:")
                for name, count in top_pitchers:
                    print(f"    {name:30} - {count:,} pitches")

        # Overall totals
        cur.execute("""
            SELECT COUNT(*), COUNT(DISTINCT mlb_pitcher_id)
            FROM milb_pitcher_pitches
        """)
        grand_total_pitches, grand_total_pitchers = cur.fetchone()
        print(f"\nGRAND TOTAL:")
        print(f"  {grand_total_pitchers} unique pitchers")
        print(f"  {grand_total_pitches:,} total pitches across all seasons")
        print(f"  {total_collected:,} new pitches collected in this run")

    finally:
        connection_pool.putconn(conn)
        connection_pool.closeall()

    print(f"\nEnded: {datetime.now()}")
    print("=" * 80)

if __name__ == "__main__":
    main()