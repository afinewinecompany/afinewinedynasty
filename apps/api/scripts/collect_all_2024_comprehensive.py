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
SEASON = 2024

# Create connection pool
connection_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 10,
    DB_URL,
    connect_timeout=30
)

async def check_player_games(session: aiohttp.ClientSession, player_id: int, player_name: str) -> int:
    """Check if player has any 2024 MiLB games"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'gameType': 'R',  # Regular season MiLB
        'season': SEASON,
        'language': 'en'
    }

    try:
        async with session.get(url, params=params, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                if data.get('stats') and data['stats'][0].get('splits'):
                    game_count = len(data['stats'][0]['splits'])
                    if game_count > 0:
                        logger.info(f"  {player_name}: Found {game_count} games in 2024")
                    return game_count
    except Exception as e:
        logger.warning(f"  {player_name}: Error checking games - {str(e)}")

    return 0

async def collect_player_pitches(session: aiohttp.ClientSession, player_id: int, player_name: str, org: str, pa_count: int):
    """Collect pitch data for a single player"""
    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Get game list
        cur.execute("""
            SELECT DISTINCT game_pk, game_date
            FROM milb_plate_appearances
            WHERE mlb_player_id = %s AND season = %s
            ORDER BY game_date
        """, (player_id, SEASON))
        games = cur.fetchall()

        if not games:
            return 0

        total_pitches = 0
        successful_games = 0

        for game_pk, game_date in games:
            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

            try:
                async with session.get(url, timeout=30) as response:
                    if response.status != 200:
                        continue

                    data = await response.json()
                    all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

                    game_pitches = []
                    for play in all_plays:
                        # Check if player was the batter
                        matchup = play.get('matchup', {})
                        if matchup.get('batter', {}).get('id') != player_id:
                            continue

                        pitcher_id = matchup.get('pitcher', {}).get('id')
                        at_bat_index = play.get('atBatIndex', 0)

                        for i, event in enumerate(play.get('playEvents', [])):
                            if event.get('isPitch'):
                                pitch_data = event.get('pitchData', {})

                                # Prepare pitch record
                                pitch_record = (
                                    player_id, pitcher_id, game_pk, game_date, SEASON,
                                    'MiLB',  # level
                                    at_bat_index,
                                    i + 1,  # pitch_number
                                    play.get('about', {}).get('inning', 0),
                                    pitch_data.get('type', {}).get('code'),
                                    pitch_data.get('startSpeed'),
                                    pitch_data.get('breaks', {}).get('spinRate'),
                                    pitch_data.get('zone'),
                                    event.get('details', {}).get('call', {}).get('code'),
                                    event.get('details', {}).get('description'),
                                    event.get('details', {}).get('isStrike', False),
                                    event.get('count', {}).get('balls', 0),
                                    event.get('count', {}).get('strikes', 0),
                                    datetime.now()
                                )
                                game_pitches.append(pitch_record)

                    # Insert pitches
                    if game_pitches:
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
                        total_pitches += len(game_pitches)
                        successful_games += 1

            except Exception as e:
                logger.debug(f"    Game {game_pk}: {str(e)}")
                continue

        if total_pitches > 0:
            logger.info(f"  {player_name} ({org}) - {pa_count} PAs - Collected {total_pitches} pitches from {successful_games}/{len(games)} games")

        return total_pitches

    finally:
        connection_pool.putconn(conn)

async def process_batch(prospects: List[Tuple], batch_num: int, total_batches: int):
    """Process a batch of prospects"""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for name, mlb_id, org, pa_count in prospects:
            task = collect_player_pitches(session, int(mlb_id), name, org, pa_count)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_pitches = sum(r for r in results if isinstance(r, int))
        logger.info(f"  Batch {batch_num}/{total_batches} complete: {total_pitches} total pitches")
        return total_pitches

async def check_missing_prospects():
    """Check all prospects in database for any 2024 activity"""
    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Get all prospects without 2024 data
        cur.execute("""
            SELECT p.name, p.mlb_player_id, p.organization
            FROM prospects p
            LEFT JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id AND mpa.season = 2024
            WHERE mpa.mlb_player_id IS NULL
            ORDER BY p.name
            LIMIT 100
        """)
        prospects_to_check = cur.fetchall()

        logger.info(f"\nChecking {len(prospects_to_check)} prospects for any 2024 activity...")

        async with aiohttp.ClientSession() as session:
            found_count = 0
            for i, (name, mlb_id, org) in enumerate(prospects_to_check):
                if i % 10 == 0:
                    logger.info(f"  Checked {i}/{len(prospects_to_check)} prospects, found {found_count} with games")

                game_count = await check_player_games(session, int(mlb_id), name)
                if game_count > 0:
                    found_count += 1

            logger.info(f"\nFound {found_count} prospects with 2024 games that we can collect")

    finally:
        connection_pool.putconn(conn)

def main():
    print("=" * 70)
    print("COMPREHENSIVE 2024 PITCH DATA COLLECTION")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    conn = connection_pool.getconn()
    try:
        cur = conn.cursor()

        # Find prospects with 2024 PAs but no pitch data
        cur.execute("""
            SELECT p.name, p.mlb_player_id, p.organization, COUNT(mpa.id) as pa_count
            FROM prospects p
            JOIN milb_plate_appearances mpa ON p.mlb_player_id::INTEGER = mpa.mlb_player_id
            LEFT JOIN milb_batter_pitches mbp ON p.mlb_player_id::INTEGER = mbp.mlb_batter_id AND mbp.season = 2024
            WHERE mpa.season = 2024 AND mbp.mlb_batter_id IS NULL
            GROUP BY p.mlb_player_id, p.name, p.organization
            ORDER BY pa_count DESC
        """)
        missing_pitches = cur.fetchall()

        if not missing_pitches:
            print("\n✓ All prospects with 2024 plate appearances already have pitch data!")

            # Check for prospects without any data
            print("\nChecking for prospects who may have 2024 games not yet collected...")
            asyncio.run(check_missing_prospects())

        else:
            print(f"\nFound {len(missing_pitches)} prospects with 2024 PAs but no pitch data")
            print("\nTop prospects needing collection:")
            for name, mlb_id, org, pa_count in missing_pitches[:10]:
                print(f"  {name:30} ({org}) - {pa_count} PAs")

            print(f"\n=== COLLECTING 2024 PITCH DATA ===\n")

            # Process in batches
            batch_size = 5
            batches = [missing_pitches[i:i+batch_size] for i in range(0, len(missing_pitches), batch_size)]

            total_collected = 0
            for i, batch in enumerate(batches, 1):
                logger.info(f"\n=== 2024 BATCH {i}/{len(batches)}: {len(batch)} players ===")
                pitches = asyncio.run(process_batch(batch, i, len(batches)))
                total_collected += pitches

                # Progress report
                if i % 5 == 0:
                    cur.execute("""
                        SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2024
                    """)
                    total_in_db = cur.fetchone()[0]
                    logger.info(f"[PROGRESS] Completed {i}/{len(batches)} batches")
                    logger.info(f"  Total 2024 pitches in DB: {total_in_db:,}")
                    logger.info(f"  New pitches collected: {total_collected:,}")

            print("\n" + "=" * 70)
            print("2024 COLLECTION COMPLETE")

            # Final statistics
            cur.execute("""
                SELECT COUNT(*), COUNT(DISTINCT mlb_batter_id)
                FROM milb_batter_pitches
                WHERE season = 2024
            """)
            total_pitches, total_players = cur.fetchone()
            print(f"Total 2024 pitch records: {total_pitches:,}")
            print(f"Unique players with 2024 data: {total_players}")

    finally:
        connection_pool.putconn(conn)
        connection_pool.closeall()

    print(f"Ended: {datetime.now()}")
    print("=" * 70)

if __name__ == "__main__":
    main()