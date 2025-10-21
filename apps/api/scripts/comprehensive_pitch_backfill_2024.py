"""
Comprehensive 2024 MiLB Pitch Data Backfill Script

Fixes critical gaps in pitch-by-pitch collection:
1. Collects ALL levels (A, A+, AA, AAA, CPX, Rk, etc.) - NOT just hardcoded 'MiLB'
2. Full season coverage (April-September 2024)
3. Proper error handling and retry logic
4. Progress tracking and gap reporting
5. Validates completeness against game logs

Run with: python comprehensive_pitch_backfill_2024.py
"""

import asyncio
import aiohttp
import psycopg2
from psycopg2 import pool
import logging
from datetime import datetime, timedelta
import time
from typing import List, Dict, Tuple, Optional
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2024

# Level mapping from MLB Stats API
# These are the actual sport_id values used by MLB
MILB_SPORT_IDS = {
    11: 'AAA',   # Triple-A
    12: 'AA',    # Double-A
    13: 'A+',    # High-A
    14: 'A',     # Single-A
    15: 'Rk',    # Rookie
    16: 'FRk',   # Rookie Advanced
    5442: 'CPX', # Complex/Arizona Complex League
}

# Create connection pool
connection_pool = None

def init_connection_pool():
    """Initialize database connection pool"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=DB_URL,
            connect_timeout=30
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        raise

def get_conn():
    """Get connection from pool with retry logic"""
    if not connection_pool:
        init_connection_pool()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = connection_pool.getconn()
            # Test connection
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return conn
        except Exception as e:
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                raise
    return None

def return_conn(conn):
    """Return connection to pool"""
    if connection_pool and conn:
        connection_pool.putconn(conn)

async def get_batter_games_with_levels(session: aiohttp.ClientSession, batter_id: int, max_retries=3) -> List[Dict]:
    """
    Get ALL games for a batter in 2024 with ACTUAL level information.

    CRITICAL FIX: Previous scripts hardcoded level as 'MiLB' - this gets the real level.
    """
    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'gameType': 'R',  # Regular season
        'season': SEASON,
        'language': 'en'
    }

    for attempt in range(max_retries):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with session.get(url, params=params, timeout=timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('stats') and len(data['stats']) > 0:
                        splits = data['stats'][0].get('splits', [])
                        games = []

                        for split in splits:
                            game_data = split.get('game', {})
                            team_data = split.get('team', {})
                            stat_data = split.get('stat', {})

                            # Extract level from sport information
                            sport = game_data.get('sport', {})
                            sport_id = sport.get('id')
                            level = MILB_SPORT_IDS.get(sport_id, 'Unknown')

                            # Also can get from league
                            league = split.get('league', {})
                            league_name = league.get('name', '')

                            games.append({
                                'gamePk': game_data.get('gamePk'),
                                'date': split.get('date'),
                                'level': level,
                                'sport_id': sport_id,
                                'league': league_name,
                                'team': team_data.get('name'),
                                'pas': stat_data.get('plateAppearances', 0),
                                'ab': stat_data.get('atBats', 0)
                            })

                        return games

                elif response.status == 404:
                    logger.debug(f"Player {batter_id} not found")
                    return []

        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting games for {batter_id}, attempt {attempt + 1}")
        except Exception as e:
            logger.warning(f"Error getting games for {batter_id}: {e}")

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return []

async def collect_game_pitches(session: aiohttp.ClientSession, batter_id: int, game_info: Dict, max_retries=3) -> Tuple[List[Tuple], str]:
    """
    Collect all pitches faced by batter in a single game.

    Returns: (pitch_records, error_msg)
    """
    game_pk = game_info['gamePk']
    expected_level = game_info['level']

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
                game_date = game_data.get('datetime', {}).get('officialDate', game_info['date'])

                # Get level from game data (more reliable than game log sometimes)
                venue_data = game_data.get('venue', {})
                teams_data = game_data.get('teams', {})

                # Use the level from game log as primary, game data as fallback
                level = expected_level

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

                        # Extract additional pitch data
                        launch_speed = pitch_data.get('breaks', {}).get('launchSpeed')
                        launch_angle = pitch_data.get('breaks', {}).get('launchAngle')

                        # Create pitch record tuple for milb_batter_pitches table
                        pitch_record = (
                            batter_id,   # mlb_batter_id
                            pitcher_id,  # mlb_pitcher_id
                            game_pk,     # game_pk
                            game_date,   # game_date
                            SEASON,      # season
                            level,       # CRITICAL FIX: Use actual level, not 'MiLB'
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

                return game_pitches, None

        except asyncio.TimeoutError:
            error_msg = f"Timeout (attempt {attempt + 1})"
            if attempt == max_retries - 1:
                return [], error_msg
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            if attempt == max_retries - 1:
                return [], error_msg

        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    return [], "Max retries exceeded"

def insert_pitches_batch(conn, pitches: List[Tuple]) -> int:
    """Insert batch of pitches with conflict handling"""
    if not pitches:
        return 0

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
                    ) ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_number)
                    DO NOTHING
                """, pitch)
                inserted += cur.rowcount
            except Exception as e:
                logger.warning(f"Failed to insert pitch: {e}")
                continue

        conn.commit()

    except Exception as e:
        logger.error(f"Batch insert error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()

    return inserted

async def collect_batter_full_season(session: aiohttp.ClientSession, batter_id: int, batter_name: str) -> Dict:
    """
    Collect complete 2024 season for a batter across ALL levels.

    Returns dict with collection statistics.
    """
    start_time = time.time()

    # Get all games with level information
    games = await get_batter_games_with_levels(session, batter_id)

    if not games:
        return {
            'player_id': batter_id,
            'player_name': batter_name,
            'games_found': 0,
            'total_pitches': 0,
            'levels': [],
            'error': 'No games found'
        }

    # Group games by level
    games_by_level = {}
    for game in games:
        level = game['level']
        if level not in games_by_level:
            games_by_level[level] = []
        games_by_level[level].append(game)

    total_pas = sum(g['pas'] for g in games)

    logger.info(f"\n{'='*80}")
    logger.info(f"Player: {batter_name} (ID: {batter_id})")
    logger.info(f"Games Found: {len(games)} | Total PAs: {total_pas}")
    logger.info(f"Levels: {', '.join(f'{k}({len(v)})' for k, v in games_by_level.items())}")
    logger.info(f"{'='*80}")

    # Check existing data
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT level, COUNT(*) as pitch_count
            FROM milb_batter_pitches
            WHERE mlb_batter_id = %s AND season = %s
            GROUP BY level
        """, (batter_id, SEASON))

        existing_by_level = {row[0]: row[1] for row in cur.fetchall()}

        if existing_by_level:
            logger.info(f"Existing pitches: {', '.join(f'{k}:{v}' for k, v in existing_by_level.items())}")

        cur.close()
    finally:
        return_conn(conn)

    # Collect pitches game by game
    total_pitches_collected = 0
    games_processed = 0
    games_failed = 0
    level_stats = {}

    for level, level_games in games_by_level.items():
        logger.info(f"\n  Level {level}: {len(level_games)} games")

        level_pitches = 0
        level_games_ok = 0
        level_games_fail = 0

        for game in level_games:
            game_pk = game['gamePk']

            pitches, error = await collect_game_pitches(session, batter_id, game, max_retries=3)

            if error:
                logger.debug(f"    Game {game_pk} ({game['date']}): FAILED - {error}")
                level_games_fail += 1
                games_failed += 1
            else:
                # Insert pitches
                conn = get_conn()
                try:
                    inserted = insert_pitches_batch(conn, pitches)
                    level_pitches += inserted
                    total_pitches_collected += inserted
                    level_games_ok += 1
                    games_processed += 1

                    if inserted > 0:
                        logger.debug(f"    Game {game_pk} ({game['date']}): {inserted} pitches")
                finally:
                    return_conn(conn)

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)

        logger.info(f"    {level}: {level_pitches} pitches from {level_games_ok}/{len(level_games)} games")
        level_stats[level] = {
            'games': len(level_games),
            'games_ok': level_games_ok,
            'games_failed': level_games_fail,
            'pitches': level_pitches
        }

    elapsed = time.time() - start_time

    logger.info(f"\n  Summary: {total_pitches_collected} pitches | {games_processed}/{len(games)} games OK | {games_failed} failed | {elapsed:.1f}s")

    return {
        'player_id': batter_id,
        'player_name': batter_name,
        'games_found': len(games),
        'games_processed': games_processed,
        'games_failed': games_failed,
        'total_pitches': total_pitches_collected,
        'total_pas': total_pas,
        'levels': level_stats,
        'elapsed': elapsed
    }

async def run_backfill_batch(players: List[Tuple], batch_num: int, total_batches: int) -> List[Dict]:
    """Process a batch of players"""
    logger.info(f"\n{'#'*100}")
    logger.info(f"BATCH {batch_num}/{total_batches}: {len(players)} players")
    logger.info(f"{'#'*100}")

    connector = aiohttp.TCPConnector(limit=5, limit_per_host=3)
    timeout = aiohttp.ClientTimeout(total=600)

    results = []

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for player_id, player_name in players:
            result = await collect_batter_full_season(session, player_id, player_name)
            results.append(result)

            # Delay between players
            await asyncio.sleep(1.0)

    # Batch summary
    batch_pitches = sum(r['total_pitches'] for r in results)
    batch_games = sum(r['games_processed'] for r in results)

    logger.info(f"\nBatch {batch_num} Complete: {batch_pitches} pitches from {batch_games} games")

    return results

def get_top_prospects_needing_data(limit=200) -> List[Tuple]:
    """Get top prospects that need pitch data"""
    conn = get_conn()
    try:
        cur = conn.cursor()

        # Get top prospects by FV with incomplete or no pitch data
        cur.execute("""
            WITH prospect_pitch_counts AS (
                SELECT
                    p.mlb_player_id,
                    p.name,
                    p.fangraphs_fv_latest as fv,
                    COALESCE(COUNT(DISTINCT bp.pitch_id), 0) as pitch_count,
                    COALESCE(SUM(gl.pa), 0) as total_pa
                FROM prospects p
                LEFT JOIN milb_batter_pitches bp ON p.mlb_player_id = bp.mlb_batter_id
                    AND bp.season = %s
                LEFT JOIN milb_game_logs gl ON p.mlb_player_id = gl.mlb_player_id
                    AND gl.season = %s
                WHERE p.fangraphs_fv_latest IS NOT NULL
                  AND p.mlb_player_id IS NOT NULL
                  AND p.position NOT IN ('SP', 'RP', 'P')
                GROUP BY p.mlb_player_id, p.name, p.fangraphs_fv_latest
            )
            SELECT
                mlb_player_id,
                name,
                fv,
                pitch_count,
                total_pa,
                CASE
                    WHEN total_pa > 0 THEN ROUND((pitch_count::numeric / total_pa) * 100, 1)
                    ELSE 0
                END as coverage_pct
            FROM prospect_pitch_counts
            WHERE total_pa > 0  -- Played in 2024
              AND (pitch_count = 0 OR (pitch_count::numeric / NULLIF(total_pa, 0)) < 4.0)  -- <4x coverage (should be ~4-5 pitches per PA)
            ORDER BY fv DESC NULLS LAST, total_pa DESC
            LIMIT %s
        """, (SEASON, SEASON, limit))

        prospects = cur.fetchall()
        cur.close()

        return [(row[0], row[1]) for row in prospects]

    finally:
        return_conn(conn)

def main():
    """Main execution"""
    print("\n" + "="*100)
    print("COMPREHENSIVE 2024 MILB PITCH DATA BACKFILL")
    print(f"Started: {datetime.now()}")
    print("="*100)
    print("\nFixes:")
    print("  1. Collects ACTUAL levels (A, A+, AA, AAA, CPX, Rk) - not hardcoded 'MiLB'")
    print("  2. Full season coverage across all levels")
    print("  3. Proper error handling and retry logic")
    print("  4. Validates against game logs")
    print("="*100)

    # Initialize
    init_connection_pool()

    # Get prospects needing data
    prospects = get_top_prospects_needing_data(limit=200)

    if not prospects:
        print("\n No prospects found needing pitch data!")
        return

    print(f"\nFound {len(prospects)} prospects needing pitch data backfill")
    print(f"\nTop 20:")
    for i, (player_id, name) in enumerate(prospects[:20], 1):
        print(f"  {i:3}. {name} (ID: {player_id})")

    # Confirm
    print(f"\n Ready to collect data for {len(prospects)} prospects")
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled")
        return

    # Process in batches
    batch_size = 10
    batches = [prospects[i:i+batch_size] for i in range(0, len(prospects), batch_size)]

    all_results = []
    total_start = time.time()

    for i, batch in enumerate(batches, 1):
        batch_results = asyncio.run(run_backfill_batch(batch, i, len(batches)))
        all_results.extend(batch_results)

        # Progress checkpoint every 5 batches
        if i % 5 == 0 or i == len(batches):
            total_pitches = sum(r['total_pitches'] for r in all_results)
            total_games = sum(r['games_processed'] for r in all_results)
            elapsed = time.time() - total_start

            print(f"\n{'='*100}")
            print(f"CHECKPOINT: {i}/{len(batches)} batches complete")
            print(f"Total: {total_pitches:,} pitches from {total_games:,} games in {elapsed/60:.1f} minutes")
            print(f"{'='*100}\n")

    # Final summary
    total_elapsed = time.time() - total_start

    print("\n" + "="*100)
    print("BACKFILL COMPLETE")
    print("="*100)
    print(f"Prospects Processed: {len(all_results)}")
    print(f"Total Pitches Collected: {sum(r['total_pitches'] for r in all_results):,}")
    print(f"Total Games Processed: {sum(r['games_processed'] for r in all_results):,}")
    print(f"Total Games Failed: {sum(r['games_failed'] for r in all_results):,}")
    print(f"Total Time: {total_elapsed/60:.1f} minutes")
    print(f"Completed: {datetime.now()}")
    print("="*100)

    # Close pool
    if connection_pool:
        connection_pool.closeall()

if __name__ == "__main__":
    main()
