"""
Simple 2025 game log collection for prospects with missing data.

Focuses on prospects who have 0 or very few game logs for 2025.
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025

# Sport IDs for MiLB levels
MILB_SPORT_IDS = {11, 12, 13, 14, 15, 16, 5442}  # AAA, AA, A+, A, Rk, FRk, CPX

def get_prospects_needing_gamelogs():
    """Get prospects with <10 games in 2025"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.position,
            COALESCE(COUNT(DISTINCT gl.game_pk), 0) as game_count
        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id::integer = gl.mlb_player_id
            AND gl.season = %s
        WHERE p.position NOT IN ('SP', 'RP', 'P')
          AND p.mlb_player_id IS NOT NULL
          AND p.mlb_player_id != ''
        GROUP BY p.mlb_player_id, p.name, p.position
        HAVING COUNT(DISTINCT gl.game_pk) < 10
        ORDER BY game_count, p.name
        LIMIT 50
    """, (SEASON,))

    prospects = []
    for row in cursor.fetchall():
        prospects.append({
            'mlb_id': int(row[0]),
            'name': row[1],
            'position': row[2],
            'current_games': row[3]
        })

    conn.close()

    return prospects

async def get_player_gamelogs(session: aiohttp.ClientSession, mlb_id: int) -> List[Dict]:
    """Fetch game logs from MLB Stats API"""
    url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'gameType': 'R',
        'season': SEASON
    }

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []

            data = await resp.json()

            if 'stats' not in data or not data['stats'] or not data['stats'][0].get('splits'):
                return []

            games = []
            for split in data['stats'][0]['splits']:
                game_data = split.get('game', {})
                sport_id = game_data.get('sport', {}).get('id')

                # Only include MiLB games
                if sport_id not in MILB_SPORT_IDS:
                    continue

                stat = split.get('stat', {})
                games.append({
                    'game_pk': game_data.get('gamePk'),
                    'game_date': split.get('date'),
                    'team': split.get('team', {}).get('name'),
                    'opponent': split.get('opponent', {}).get('name'),
                    'is_home': game_data.get('type') == 'home',
                    'sport_id': sport_id,
                    'pa': stat.get('plateAppearances', 0),
                    'ab': stat.get('atBats', 0),
                    'hits': stat.get('hits', 0),
                    'hr': stat.get('homeRuns', 0),
                    'rbi': stat.get('rbi', 0),
                    'bb': stat.get('baseOnBalls', 0),
                    'so': stat.get('strikeOuts', 0)
                })

            return games

    except Exception as e:
        logger.debug(f"Error fetching games for {mlb_id}: {e}")
        return []

def get_level_from_sport_id(sport_id: int) -> str:
    """Convert sport_id to level name"""
    mapping = {
        11: 'AAA',
        12: 'AA',
        13: 'A+',
        14: 'A',
        15: 'Rk',
        16: 'FRk',
        5442: 'Complex'
    }
    return mapping.get(sport_id, 'Unknown')

def insert_gamelogs(mlb_id: int, games: List[Dict]):
    """Insert game logs into database"""
    if not games:
        return 0

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    inserted = 0
    for game in games:
        try:
            cursor.execute("""
                INSERT INTO milb_game_logs (
                    mlb_player_id, game_pk, game_date, season, level,
                    team, opponent, is_home, plate_appearances, at_bats,
                    hits, home_runs, rbi, walks, strikeouts, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_pk, mlb_player_id) DO NOTHING
            """, (
                mlb_id,
                game['game_pk'],
                game['game_date'],
                SEASON,
                get_level_from_sport_id(game['sport_id']),
                game['team'],
                game['opponent'],
                game['is_home'],
                game['pa'],
                game['ab'],
                game['hits'],
                game['hr'],
                game['rbi'],
                game['bb'],
                game['so'],
                datetime.now()
            ))
            inserted += cursor.rowcount

        except Exception as e:
            logger.debug(f"Error inserting game {game['game_pk']}: {e}")
            continue

    conn.commit()
    conn.close()

    return inserted

async def process_prospect(session: aiohttp.ClientSession, prospect: Dict):
    """Process one prospect"""
    mlb_id = prospect['mlb_id']
    name = prospect['name']

    logger.info(f"  {name} (ID: {mlb_id}) - current: {prospect['current_games']} games")

    games = await get_player_gamelogs(session, mlb_id)

    if games:
        inserted = insert_gamelogs(mlb_id, games)
        logger.info(f"    -> Found {len(games)} games, inserted {inserted} new")
    else:
        logger.info(f"    -> No MiLB games found for 2025")

    await asyncio.sleep(0.5)

async def main():
    logger.info("="*80)
    logger.info("COLLECT 2025 GAME LOGS FOR PROSPECTS WITH MISSING DATA")
    logger.info("="*80)

    prospects = get_prospects_needing_gamelogs()

    logger.info(f"\nFound {len(prospects)} prospects with <10 game logs")
    logger.info(f"\nProcessing...")

    async with aiohttp.ClientSession() as session:
        for prospect in prospects:
            await process_prospect(session, prospect)

    logger.info("\n" + "="*80)
    logger.info("COLLECTION COMPLETE")
    logger.info("="*80)

if __name__ == "__main__":
    asyncio.run(main())
