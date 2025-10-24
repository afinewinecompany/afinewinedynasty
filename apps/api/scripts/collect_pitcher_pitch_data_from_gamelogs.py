"""
Collect pitch-by-pitch data for PITCHERS with 2025 game logs
Runs in parallel with batter pitch collection
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025
BATCH_SIZE = 50  # Process 50 prospects at a time

async def collect_game_pitches(session, pitcher_id, game_info):
    """Collect pitches for one game where prospect was PITCHING"""
    game_pk = game_info['game_pk']
    level = game_info['level']
    game_date = game_info['game_date']

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []

            data = await resp.json()
            all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

            pitches = []
            for play in all_plays:
                matchup = play.get('matchup', {})

                # KEY DIFFERENCE: Check if this prospect is the PITCHER
                if matchup.get('pitcher', {}).get('id') != pitcher_id:
                    continue

                batter_id = matchup.get('batter', {}).get('id')
                at_bat_index = play.get('atBatIndex', 0)
                inning = play.get('about', {}).get('inning', 0)

                play_events = play.get('playEvents', [])
                for i, event in enumerate(play_events):
                    if not event.get('isPitch'):
                        continue

                    pitch_data = event.get('pitchData', {})
                    details = event.get('details', {})
                    count = event.get('count', {})

                    # Note: For pitchers, we store pitcher_id as mlb_pitcher_id
                    pitch_record = (
                        pitcher_id, batter_id, game_pk, game_date, SEASON,
                        level, at_bat_index, i + 1, inning,
                        details.get('type', {}).get('code'),
                        pitch_data.get('startSpeed'),
                        pitch_data.get('breaks', {}).get('spinRate'),
                        pitch_data.get('zone'),
                        details.get('call', {}).get('code'),
                        details.get('code'),
                        details.get('isStrike'),
                        count.get('balls', 0),
                        count.get('strikes', 0),
                        datetime.now()
                    )
                    pitches.append(pitch_record)

            return pitches

    except Exception as e:
        logger.error(f"  Error fetching game {game_pk}: {e}")
        return []

async def process_prospect(session, conn, cursor, prospect):
    """Process one pitcher prospect's games"""
    mlb_player_id, name = prospect

    # Get games for this pitcher
    cursor.execute("""
        SELECT game_pk, game_date, level
        FROM milb_game_logs
        WHERE mlb_player_id = %s
          AND season = %s
          AND game_pk IS NOT NULL
        ORDER BY game_date
    """, (mlb_player_id, SEASON))

    games = cursor.fetchall()
    if not games:
        return 0

    logger.info(f"  {name} ({mlb_player_id}): {len(games)} games")

    total_pitches = 0

    # Process games in batches
    for i in range(0, len(games), 10):
        batch = games[i:i+10]

        tasks = []
        for game in batch:
            game_info = {
                'game_pk': game[0],
                'game_date': game[1],
                'level': game[2]
            }
            tasks.append(collect_game_pitches(session, mlb_player_id, game_info))

        # Collect pitches for batch
        results = await asyncio.gather(*tasks)

        # Insert all pitches
        for pitches in results:
            if pitches:
                try:
                    cursor.executemany("""
                        INSERT INTO milb_pitcher_pitches (
                            mlb_pitcher_id, mlb_batter_id, game_pk, game_date, season,
                            level, at_bat_index, pitch_number, inning,
                            pitch_type, start_speed, spin_rate, zone,
                            pitch_call, pitch_result, is_strike,
                            balls, strikes, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_pitcher_id) DO NOTHING
                    """, pitches)
                    conn.commit()
                    total_pitches += len(pitches)
                except Exception as e:
                    logger.error(f"    Error inserting pitches: {e}")
                    conn.rollback()

        await asyncio.sleep(0.5)  # Rate limiting

    if total_pitches > 0:
        logger.info(f"    -> Collected {total_pitches} pitches")

    return total_pitches

async def main():
    logger.info("="*80)
    logger.info("PITCHER PITCH DATA COLLECTION FROM EXISTING GAME LOGS")
    logger.info("="*80)
    logger.info(f"Season: {SEASON}")
    logger.info(f"Batch size: {BATCH_SIZE} pitchers\n")

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # Get PITCHER prospects with game logs
    cursor.execute("""
        SELECT p.mlb_player_id::integer, p.name
        FROM prospects p
        JOIN milb_game_logs gl ON p.mlb_player_id::integer = gl.mlb_player_id
        WHERE gl.season = %s
          AND p.position IN ('SP', 'RP', 'P')
        GROUP BY p.mlb_player_id, p.name
        ORDER BY p.mlb_player_id
    """, (SEASON,))

    all_pitchers = cursor.fetchall()
    logger.info(f"Found {len(all_pitchers)} PITCHERS with {SEASON} game logs\n")

    total_collected = 0
    processed = 0

    async with aiohttp.ClientSession() as session:
        # Process in batches
        for i in range(0, len(all_pitchers), BATCH_SIZE):
            batch = all_pitchers[i:i+BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(all_pitchers) + BATCH_SIZE - 1) // BATCH_SIZE

            logger.info(f"\n{'='*80}")
            logger.info(f"BATCH {batch_num}/{total_batches} (Pitchers {i+1}-{min(i+BATCH_SIZE, len(all_pitchers))})")
            logger.info(f"{'='*80}\n")

            for pitcher in batch:
                pitches = await process_prospect(session, conn, cursor, pitcher)
                total_collected += pitches
                processed += 1

                if processed % 10 == 0:
                    logger.info(f"\nProgress: {processed}/{len(all_pitchers)} pitchers, {total_collected:,} pitches total\n")

    conn.close()

    logger.info(f"\n{'='*80}")
    logger.info(f"PITCHER COLLECTION COMPLETE")
    logger.info(f"{'='*80}")
    logger.info(f"Pitchers processed: {processed}")
    logger.info(f"Total pitches collected: {total_collected:,}")

if __name__ == "__main__":
    asyncio.run(main())
