"""
Simple backfill script for Bryce Eldridge and Konnor Griffin
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

# Target prospects
PROSPECTS = [
    {'name': 'Bryce Eldridge', 'mlb_id': 805811},
    {'name': 'Konnor Griffin', 'mlb_id': 804606}
]

def get_games_for_prospect(mlb_player_id):
    """Get games from milb_game_logs"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT game_pk, game_date, level
        FROM milb_game_logs
        WHERE mlb_player_id = %s
          AND season = %s
          AND game_pk IS NOT NULL
        ORDER BY game_date
    """, (mlb_player_id, SEASON))

    games = cursor.fetchall()
    conn.close()

    return [{'game_pk': g[0], 'game_date': g[1], 'level': g[2]} for g in games]

async def collect_game_pitches(session, batter_id, game_info):
    """Collect pitches for one game"""
    game_pk = game_info['game_pk']
    level = game_info['level']

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []

            data = await resp.json()
            game_data = data.get('gameData', {})
            game_date = game_data.get('datetime', {}).get('officialDate', str(game_info['game_date']))

            all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

            pitches = []
            for play in all_plays:
                if play.get('matchup', {}).get('batter', {}).get('id') != batter_id:
                    continue

                pitcher_id = play.get('matchup', {}).get('pitcher', {}).get('id')
                at_bat_index = play.get('atBatIndex', 0)
                inning = play.get('about', {}).get('inning', 0)

                for i, event in enumerate(play.get('playEvents', [])):
                    if not event.get('isPitch'):
                        continue

                    pitch_data = event.get('pitchData', {})
                    details = event.get('details', {})
                    count = event.get('count', {})

                    pitch_record = (
                        batter_id,
                        pitcher_id,
                        game_pk,
                        game_date,
                        SEASON,
                        level,
                        at_bat_index,
                        i + 1,
                        inning,
                        details.get('type', {}).get('code'),
                        pitch_data.get('startSpeed'),
                        pitch_data.get('breaks', {}).get('spinRate'),
                        pitch_data.get('zone'),
                        details.get('call', {}).get('code'),
                        details.get('description'),
                        details.get('isStrike', False),
                        count.get('balls', 0),
                        count.get('strikes', 0),
                        datetime.now()
                    )
                    pitches.append(pitch_record)

            return pitches

    except Exception as e:
        logger.debug(f"Error: {e}")
        return []

def insert_pitches(pitches):
    """Insert pitches into database"""
    if not pitches:
        return 0

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    try:
        cursor.executemany("""
            INSERT INTO milb_batter_pitches (
                mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                level, at_bat_index, pitch_number, inning,
                pitch_type, start_speed, spin_rate, zone,
                pitch_call, pitch_result, is_strike,
                balls, strikes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_batter_id) DO NOTHING
        """, pitches)

        conn.commit()
        inserted = cursor.rowcount
        conn.close()

        return inserted

    except Exception as e:
        logger.error(f"DB error: {e}")
        conn.rollback()
        conn.close()
        return 0

async def process_prospect(session, prospect):
    """Process one prospect"""
    name = prospect['name']
    mlb_id = prospect['mlb_id']

    logger.info(f"\n{'='*80}")
    logger.info(f"{name} (ID: {mlb_id})")
    logger.info('='*80)

    games = get_games_for_prospect(mlb_id)
    logger.info(f"Found {len(games)} games in game logs")

    # Group by level
    by_level = {}
    for game in games:
        level = game['level']
        if level not in by_level:
            by_level[level] = []
        by_level[level].append(game)

    total_pitches = 0

    for level in sorted(by_level.keys()):
        level_games = by_level[level]
        logger.info(f"\nLevel {level}: {len(level_games)} games")

        level_pitches = 0

        for game in level_games:
            pitches = await collect_game_pitches(session, mlb_id, game)

            if pitches:
                inserted = insert_pitches(pitches)
                level_pitches += inserted

            await asyncio.sleep(0.3)

        logger.info(f"  -> Collected {level_pitches} pitches")
        total_pitches += level_pitches

    logger.info(f"\nTOTAL: {total_pitches} pitches")

async def main():
    logger.info("="*80)
    logger.info("TARGETED BACKFILL: Bryce Eldridge & Konnor Griffin")
    logger.info("="*80)

    async with aiohttp.ClientSession() as session:
        for prospect in PROSPECTS:
            await process_prospect(session, prospect)
            await asyncio.sleep(2.0)

    logger.info("\n" + "="*80)
    logger.info("BACKFILL COMPLETE")
    logger.info("="*80)

if __name__ == "__main__":
    asyncio.run(main())
