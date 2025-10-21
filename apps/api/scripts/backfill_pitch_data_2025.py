"""
Backfill 2025 pitch data using existing game_pk values from milb_game_logs.

Uses the correct milb_batter_pitches schema.
"""

import asyncio
import aiohttp
import psycopg2
from psycopg2 import pool
import logging
from datetime import datetime
import time
from typing import List, Dict, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025

connection_pool = None

def init_connection_pool():
    global connection_pool
    if not connection_pool:
        connection_pool = pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=DB_URL)
    return connection_pool

def get_prospects_needing_backfill():
    """Get prospects with incomplete pitch data coverage"""
    pool = init_connection_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        query = """
            WITH game_coverage AS (
                SELECT
                    gl.mlb_player_id,
                    COUNT(DISTINCT gl.game_pk) as total_games,
                    SUM(gl.plate_appearances) as total_pa,
                    COUNT(DISTINCT bp.game_pk) as games_with_pitches,
                    COUNT(bp.id) as total_pitches
                FROM milb_game_logs gl
                LEFT JOIN milb_batter_pitches bp
                    ON gl.game_pk = bp.game_pk
                    AND gl.mlb_player_id = bp.mlb_batter_id
                    AND gl.season = bp.season
                WHERE gl.season = %s
                  AND gl.plate_appearances > 0
                GROUP BY gl.mlb_player_id
            ),
            prospect_info AS (
                SELECT
                    p.name,
                    p.mlb_player_id,
                    gc.total_games,
                    gc.total_pa,
                    gc.total_pitches,
                    ROUND((COALESCE(gc.total_pitches, 0)::numeric / NULLIF(gc.total_pa * 4.5, 0)) * 100, 1) as coverage_pct
                FROM prospects p
                INNER JOIN game_coverage gc ON p.mlb_player_id::integer = gc.mlb_player_id
                WHERE p.position NOT IN ('SP', 'RP', 'P')
            )
            SELECT *
            FROM prospect_info
            WHERE coverage_pct < 50 OR total_pitches = 0
            ORDER BY total_pa DESC
            LIMIT 200
        """

        cursor.execute(query, (SEASON,))
        columns = [desc[0] for desc in cursor.description]
        prospects = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return prospects

    finally:
        pool.putconn(conn)

def get_games_for_prospect(mlb_player_id: int):
    """Get all games from milb_game_logs"""
    pool = init_connection_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        query = """
            SELECT game_pk, game_date, level, plate_appearances
            FROM milb_game_logs
            WHERE mlb_player_id = %s
              AND season = %s
              AND game_pk IS NOT NULL
              AND plate_appearances > 0
            ORDER BY game_date
        """

        cursor.execute(query, (mlb_player_id, SEASON))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    finally:
        pool.putconn(conn)

async def collect_game_pitches(session: aiohttp.ClientSession, batter_id: int, game_info: Dict) -> List[Tuple]:
    """Collect pitches for one game"""
    game_pk = game_info['game_pk']
    game_level = game_info['level']

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        timeout = aiohttp.ClientTimeout(total=45)
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                return []

            data = await response.json()
            game_data = data.get('gameData', {})
            game_date = game_data.get('datetime', {}).get('officialDate', str(game_info['game_date']))

            all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

            game_pitches = []
            for play in all_plays:
                matchup = play.get('matchup', {})

                # Only process plays where our batter was batting
                if matchup.get('batter', {}).get('id') != batter_id:
                    continue

                pitcher_id = matchup.get('pitcher', {}).get('id')
                at_bat_index = play.get('atBatIndex', 0)
                about = play.get('about', {})
                inning = about.get('inning', 0)

                play_events = play.get('playEvents', [])

                for i, event in enumerate(play_events):
                    if not event.get('isPitch'):
                        continue

                    pitch_data = event.get('pitchData', {})
                    details = event.get('details', {})
                    count = event.get('count', {})

                    # Match the schema from collect_batter_pitches_2025.py
                    pitch_record = (
                        batter_id,  # mlb_batter_id
                        pitcher_id,  # mlb_pitcher_id
                        game_pk,  # game_pk
                        game_date,  # game_date
                        SEASON,  # season
                        game_level,  # level - from game log
                        at_bat_index,  # at_bat_index
                        i + 1,  # pitch_number
                        inning,  # inning
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
        logger.debug(f"Error collecting game {game_pk}: {e}")
        return []

def insert_pitches_batch(pitches: List[Tuple]):
    """Insert pitches into database"""
    if not pitches:
        return 0

    pool = init_connection_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO milb_batter_pitches (
                mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                level, at_bat_index, pitch_number, inning,
                pitch_type, start_speed, spin_rate, zone,
                pitch_call, pitch_result, is_strike,
                balls, strikes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_batter_id) DO NOTHING
        """

        cursor.executemany(insert_query, pitches)
        conn.commit()

        return cursor.rowcount

    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting pitches: {e}")
        return 0
    finally:
        pool.putconn(conn)

async def process_prospect(session: aiohttp.ClientSession, prospect: Dict):
    """Process one prospect"""
    mlb_player_id = prospect['mlb_player_id']
    name = prospect['name']

    logger.info(f"\n{'='*80}")
    logger.info(f"Player: {name} (ID: {mlb_player_id})")

    games = get_games_for_prospect(mlb_player_id)

    if not games:
        logger.warning(f"No games found")
        return

    logger.info(f"Found {len(games)} games")

    # Group by level
    by_level = {}
    for game in games:
        level = game['level']
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(game)

    logger.info(f"Levels: {', '.join(f'{k}({len(v)})' for k, v in sorted(by_level.items()))}")

    total_pitches = 0

    for level in sorted(by_level.keys()):
        level_games = by_level[level]
        logger.info(f"\n  Level {level}: {len(level_games)} games")

        level_pitches = 0

        for game in level_games:
            pitches = await collect_game_pitches(session, mlb_player_id, game)

            if pitches:
                inserted = insert_pitches_batch(pitches)
                level_pitches += inserted

            await asyncio.sleep(0.3)

        logger.info(f"    {level}: {level_pitches} pitches")
        total_pitches += level_pitches

    logger.info(f"\n  Total: {total_pitches} pitches")

    return total_pitches

async def main():
    start_time = time.time()

    print("="*80)
    print("2025 MILB PITCH DATA BACKFILL")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    prospects = get_prospects_needing_backfill()

    if not prospects:
        print("\nNo prospects need backfill!")
        return

    print(f"\nFound {len(prospects)} prospects needing backfill")
    print(f"\nTop 20:")
    for i, p in enumerate(prospects[:20], 1):
        print(f"  {i:2d}. {p['name']:<25} - {p['total_games']} games, {p['total_pitches']} pitches ({p['coverage_pct']}%)")

    print(f"\nReady to collect data for {len(prospects)} prospects")
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled")
        return

    BATCH_SIZE = 10
    connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)

    async with aiohttp.ClientSession(connector=connector) as session:
        for i in range(0, len(prospects), BATCH_SIZE):
            batch = prospects[i:i+BATCH_SIZE]

            print(f"\n{'#'*80}")
            print(f"BATCH {i//BATCH_SIZE + 1}: {len(batch)} players")
            print(f"{'#'*80}")

            for prospect in batch:
                try:
                    await process_prospect(session, prospect)
                except Exception as e:
                    logger.error(f"Error processing {prospect['name']}: {e}")

                await asyncio.sleep(1.0)

    elapsed = time.time() - start_time
    print(f"\n{'='*80}")
    print("BACKFILL COMPLETE")
    print(f"Total Time: {elapsed/60:.1f} minutes")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
