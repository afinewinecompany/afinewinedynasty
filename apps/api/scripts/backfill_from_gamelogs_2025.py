"""
Backfill pitch data using existing game_pk values from milb_game_logs table.

This approach:
1. Queries milb_game_logs for all games we know about
2. For each game, fetches pitch-by-pitch data from MLB API
3. Inserts pitches with correct level from game logs

This solves the problem where the MLB Stats API gameLog endpoint doesn't return
all MiLB games for certain players.
"""

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
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025

# Create connection pool
connection_pool = None

def init_connection_pool():
    """Initialize database connection pool"""
    global connection_pool
    if not connection_pool:
        connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DB_URL
        )
    return connection_pool

def get_prospects_needing_backfill():
    """
    Get prospects who need pitch data backfill.
    Identifies those with game logs but limited pitch data.
    """
    pool = init_connection_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        # Find prospects with game logs but limited/no pitch data
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
                    p.id,
                    p.name,
                    p.mlb_player_id,
                    p.position,
                    gc.total_games,
                    gc.total_pa,
                    gc.games_with_pitches,
                    COALESCE(gc.total_pitches, 0) as total_pitches,
                    (gc.total_pa * 4.5) as expected_pitches,
                    ROUND((COALESCE(gc.total_pitches, 0)::numeric / NULLIF(gc.total_pa * 4.5, 0)) * 100, 1) as coverage_pct
                FROM prospects p
                INNER JOIN game_coverage gc ON p.mlb_player_id = gc.mlb_player_id
                WHERE p.position NOT IN ('SP', 'RP', 'P')  -- Hitters only
            )
            SELECT *
            FROM prospect_info
            WHERE coverage_pct < 50  -- Less than 50% coverage
               OR total_pitches = 0
            ORDER BY expected_pitches DESC
            LIMIT 200
        """

        cursor.execute(query, (SEASON,))

        if not cursor.description:
            logger.error("Query returned no description - likely a SQL error")
            return []

        columns = [desc[0] for desc in cursor.description]
        prospects = []
        for row in cursor.fetchall():
            prospects.append(dict(zip(columns, row)))

        logger.info(f"Found {len(prospects)} prospects needing pitch data backfill")
        return prospects

    finally:
        pool.putconn(conn)

def get_games_for_prospect(mlb_player_id: int):
    """Get all games for a prospect from milb_game_logs"""
    pool = init_connection_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        query = """
            SELECT
                game_pk,
                game_date,
                level,
                plate_appearances as pa,
                at_bats as ab
            FROM milb_game_logs
            WHERE mlb_player_id = %s
              AND season = %s
              AND game_pk IS NOT NULL
              AND plate_appearances > 0
            ORDER BY game_date
        """

        cursor.execute(query, (mlb_player_id, SEASON))
        columns = [desc[0] for desc in cursor.description]
        games = []
        for row in cursor.fetchall():
            games.append(dict(zip(columns, row)))

        return games

    finally:
        pool.putconn(conn)

async def collect_game_pitches(session: aiohttp.ClientSession, batter_id: int, game_info: Dict, max_retries=3) -> Tuple[List[Tuple], str]:
    """
    Collect all pitches faced by batter in a single game.

    Returns: (pitch_records, error_msg)
    """
    game_pk = game_info['game_pk']
    game_level = game_info['level']

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=45)
            async with session.get(url, timeout=timeout) as response:
                if response.status == 404:
                    return [], f"Game {game_pk} not found (404)"

                if response.status != 200:
                    return [], f"Status {response.status}"

                data = await response.json()

                # Extract game metadata
                game_data = data.get('gameData', {})
                game_date = game_data.get('datetime', {}).get('officialDate', str(game_info['game_date']))

                all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                game_pitches = []
                for play in all_plays:
                    matchup = play.get('matchup', {})
                    batter = matchup.get('batter', {})

                    # Only process plays where our target batter was batting
                    if batter.get('id') != batter_id:
                        continue

                    pitcher = matchup.get('pitcher', {})
                    pitcher_id = pitcher.get('id')

                    play_events = play.get('playEvents', [])
                    for event in play_events:
                        if not event.get('isPitch'):
                            continue

                        pitch_data = event.get('pitchData', {})
                        details = event.get('details', {})

                        pitch_id = event.get('playId', f"{game_pk}_{event.get('index', 0)}")

                        # Build pitch record tuple
                        pitch_record = (
                            batter_id,
                            pitcher_id,
                            game_pk,
                            game_date,
                            SEASON,
                            game_level,  # Use level from game log
                            pitch_id,
                            details.get('type', {}).get('code'),
                            details.get('type', {}).get('description'),
                            pitch_data.get('startSpeed'),
                            pitch_data.get('endSpeed'),
                            pitch_data.get('zone'),
                            pitch_data.get('coordinates', {}).get('pX'),
                            pitch_data.get('coordinates', {}).get('pZ'),
                            pitch_data.get('coordinates', {}).get('aX'),
                            pitch_data.get('coordinates', {}).get('aY'),
                            pitch_data.get('coordinates', {}).get('aZ'),
                            pitch_data.get('coordinates', {}).get('vX0'),
                            pitch_data.get('coordinates', {}).get('vY0'),
                            pitch_data.get('coordinates', {}).get('vZ0'),
                            pitch_data.get('breaks', {}).get('breakAngle'),
                            pitch_data.get('breaks', {}).get('breakLength'),
                            pitch_data.get('breaks', {}).get('breakY'),
                            pitch_data.get('breaks', {}).get('spinRate'),
                            pitch_data.get('breaks', {}).get('spinDirection'),
                            details.get('call', {}).get('code'),
                            details.get('call', {}).get('description')
                        )
                        game_pitches.append(pitch_record)

                return game_pitches, ""

        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return [], "Timeout"
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return [], str(e)

    return [], "Max retries exceeded"

def insert_pitches_batch(pitches: List[Tuple]):
    """Insert a batch of pitches into the database"""
    if not pitches:
        return 0

    pool = init_connection_pool()
    conn = pool.getconn()
    try:
        cursor = conn.cursor()

        insert_query = """
            INSERT INTO milb_batter_pitches (
                mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season, level, pitch_id,
                pitch_type, pitch_description, start_speed, end_speed, zone,
                px, pz, ax, ay, az, vx0, vy0, vz0,
                break_angle, break_length, break_y, spin_rate, spin_direction,
                call_code, call_description
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (pitch_id, mlb_batter_id, game_pk) DO NOTHING
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
    """Process one prospect - collect all missing pitch data"""
    mlb_player_id = prospect['mlb_player_id']
    name = prospect['name']

    logger.info(f"\n{'='*80}")
    logger.info(f"Player: {name} (ID: {mlb_player_id})")

    # Get all games from game logs
    games = get_games_for_prospect(mlb_player_id)

    if not games:
        logger.warning(f"No games found for {name}")
        return

    logger.info(f"Found {len(games)} games in game logs")

    # Group by level
    by_level = {}
    for game in games:
        level = game['level']
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(game)

    logger.info(f"Levels: {', '.join(f'{k}({len(v)})' for k, v in sorted(by_level.items()))}")

    total_pitches = 0
    total_games_ok = 0
    total_games_failed = 0

    # Process each level
    for level in sorted(by_level.keys()):
        level_games = by_level[level]
        logger.info(f"\n  Level {level}: {len(level_games)} games")

        level_pitches = 0
        games_ok = 0
        games_failed = 0

        for game in level_games:
            pitches, error = await collect_game_pitches(session, mlb_player_id, game)

            if pitches:
                inserted = insert_pitches_batch(pitches)
                level_pitches += inserted
                games_ok += 1
            else:
                games_failed += 1
                if error and "404" not in error:
                    logger.debug(f"    Game {game['game_pk']} failed: {error}")

            await asyncio.sleep(0.3)  # Rate limit

        logger.info(f"    {level}: {level_pitches} pitches from {games_ok}/{len(level_games)} games")
        total_pitches += level_pitches
        total_games_ok += games_ok
        total_games_failed += games_failed

    logger.info(f"\n  Summary: {total_pitches} pitches | {total_games_ok}/{len(games)} games OK | {total_games_failed} failed")

    return {
        'name': name,
        'pitches': total_pitches,
        'games_ok': total_games_ok,
        'games_total': len(games)
    }

async def main():
    """Main backfill process"""
    start_time = time.time()

    print("="*80)
    print("COMPREHENSIVE 2025 MILB PITCH DATA BACKFILL (FROM GAME LOGS)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    print("\nStrategy:")
    print("  - Uses existing game_pk values from milb_game_logs")
    print("  - Fetches play-by-play data for each game")
    print("  - Inserts pitches with correct level from game logs")
    print("  - Safe to re-run (ON CONFLICT DO NOTHING)")
    print("="*80)

    # Get prospects needing backfill
    prospects = get_prospects_needing_backfill()

    if not prospects:
        print("\nNo prospects need backfill!")
        return

    print(f"\nFound {len(prospects)} prospects needing pitch data backfill")
    print(f"\nTop 20:")
    for i, p in enumerate(prospects[:20], 1):
        print(f"  {i:2d}. {p['name']:<25} (ID: {p['mlb_player_id']}) - {p['total_games']} games, {p['total_pitches']} pitches ({p['coverage_pct']}%)")

    # Confirm
    print(f"\n Ready to collect data for {len(prospects)} prospects")
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled")
        return

    # Process in batches
    BATCH_SIZE = 10
    total_batches = (len(prospects) + BATCH_SIZE - 1) // BATCH_SIZE

    connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)
    timeout = aiohttp.ClientTimeout(total=600, connect=30, sock_read=60)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for batch_num in range(total_batches):
            start_idx = batch_num * BATCH_SIZE
            end_idx = min(start_idx + BATCH_SIZE, len(prospects))
            batch = prospects[start_idx:end_idx]

            print(f"\n{'#'*80}")
            print(f"BATCH {batch_num + 1}/{total_batches}: {len(batch)} players")
            print(f"{'#'*80}")

            batch_start = time.time()

            for prospect in batch:
                try:
                    await process_prospect(session, prospect)
                except Exception as e:
                    logger.error(f"Error processing {prospect['name']}: {e}")

                await asyncio.sleep(1.0)  # Rate limit between players

            batch_elapsed = time.time() - batch_start
            logger.info(f"\nBatch {batch_num + 1} completed in {batch_elapsed/60:.1f} minutes")

    elapsed = time.time() - start_time
    print(f"\n{'='*80}")
    print("BACKFILL COMPLETE")
    print("="*80)
    print(f"Prospects Processed: {len(prospects)}")
    print(f"Total Time: {elapsed/60:.1f} minutes")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
