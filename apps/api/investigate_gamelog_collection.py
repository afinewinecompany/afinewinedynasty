"""
Investigate game log collection for Bryce Eldridge
Check ALL possible ways to query MLB API for game logs
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

BRYCE_ELDRIDGE_ID = 805811
SEASON = 2025

# All possible game type codes
GAME_TYPES = ['R', 'S', 'E', 'F', 'D', 'L', 'W', 'C', 'A', 'I', 'P']

# Sport ID mapping
SPORT_MAP = {
    1: 'MLB',
    11: 'AAA',
    12: 'AA',
    13: 'A+',
    14: 'A',
    15: 'Rk',
    16: 'FRk',
    586: 'FCL',
    5442: 'CPX',
    21: 'Independent',
    23: 'College',
    31: 'International'
}

async def check_gamelog_endpoint_method1(session):
    """Method 1: Using /stats endpoint with gameLog"""
    print("\n" + "="*80)
    print("METHOD 1: /stats endpoint with gameLog (current method)")
    print("="*80)

    for game_type in GAME_TYPES:
        url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'gameType': game_type,
            'season': SEASON
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    continue

                data = await resp.json()

                if not data.get('stats') or not data['stats'][0].get('splits'):
                    continue

                splits = data['stats'][0]['splits']

                # Group by sport
                by_sport = {}
                for split in splits:
                    sport_id = split.get('game', {}).get('sport', {}).get('id')
                    level = SPORT_MAP.get(sport_id, f"Sport_{sport_id}")

                    if level not in by_sport:
                        by_sport[level] = []
                    by_sport[level].append(split)

                if by_sport:
                    print(f"\nGame Type '{game_type}':")
                    for level, level_splits in sorted(by_sport.items()):
                        print(f"  {level}: {len(level_splits)} games")

                        # Show first 3 game_pks
                        sample_pks = [s.get('game', {}).get('gamePk') for s in level_splits[:3]]
                        sample_dates = [s.get('date') for s in level_splits[:3]]
                        print(f"    Sample: {list(zip(sample_pks, sample_dates))}")

        except Exception as e:
            print(f"Error checking game type {game_type}: {e}")

        await asyncio.sleep(0.2)

async def check_gamelog_endpoint_method2(session):
    """Method 2: Using /stats endpoint with different stat groups"""
    print("\n" + "="*80)
    print("METHOD 2: /stats endpoint with different stat groups")
    print("="*80)

    stat_groups = ['hitting', 'pitching', 'fielding']

    for stat_group in stat_groups:
        print(f"\nStat Group: {stat_group}")

        url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}/stats"
        params = {
            'stats': 'gameLog',
            'group': stat_group,
            'season': SEASON
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    print(f"  Status: {resp.status}")
                    continue

                data = await resp.json()

                if not data.get('stats') or not data['stats'][0].get('splits'):
                    print(f"  No data")
                    continue

                splits = data['stats'][0]['splits']

                # Group by sport
                by_sport = {}
                for split in splits:
                    sport_id = split.get('game', {}).get('sport', {}).get('id')
                    level = SPORT_MAP.get(sport_id, f"Sport_{sport_id}")

                    if level not in by_sport:
                        by_sport[level] = []
                    by_sport[level].append(split)

                for level, level_splits in sorted(by_sport.items()):
                    print(f"  {level}: {len(level_splits)} games")

        except Exception as e:
            print(f"  Error: {e}")

        await asyncio.sleep(0.2)

async def check_gamelog_endpoint_method3(session):
    """Method 3: Using season stats with byDateRange"""
    print("\n" + "="*80)
    print("METHOD 3: /stats endpoint with byDateRange (full season)")
    print("="*80)

    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}/stats"
    params = {
        'stats': 'byDateRange',
        'group': 'hitting',
        'startDate': f'{SEASON}-01-01',
        'endDate': f'{SEASON}-12-31',
        'season': SEASON
    }

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            print(f"Status: {resp.status}")

            if resp.status == 200:
                data = await resp.json()
                print(f"Response keys: {data.keys()}")

                if data.get('stats'):
                    print(f"Stats found: {len(data['stats'])} entries")
                    for stat in data['stats']:
                        print(f"  Type: {stat.get('type', {}).get('displayName')}")
                        if stat.get('splits'):
                            print(f"    Splits: {len(stat['splits'])}")

    except Exception as e:
        print(f"Error: {e}")

async def check_gamelog_endpoint_method4(session):
    """Method 4: Check player's full stat breakdown"""
    print("\n" + "="*80)
    print("METHOD 4: Full stat breakdown (yearByYear, career, etc.)")
    print("="*80)

    stat_types = [
        'yearByYear',
        'yearByYearAdvanced',
        'career',
        'careerAdvanced',
        'season',
        'seasonAdvanced'
    ]

    for stat_type in stat_types:
        print(f"\nStat Type: {stat_type}")

        url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}/stats"
        params = {
            'stats': stat_type,
            'group': 'hitting'
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    print(f"  Status: {resp.status}")
                    continue

                data = await resp.json()

                if not data.get('stats') or not data['stats'][0].get('splits'):
                    print(f"  No data")
                    continue

                splits = data['stats'][0]['splits']
                print(f"  Found {len(splits)} entries:")

                for split in splits:
                    season = split.get('season', 'N/A')
                    team = split.get('team', {}).get('name', 'Unknown')
                    sport = split.get('sport', {})
                    sport_id = sport.get('id')
                    level = SPORT_MAP.get(sport_id, sport.get('name', 'Unknown'))

                    stat = split.get('stat', {})
                    games = stat.get('gamesPlayed', 0)
                    pa = stat.get('plateAppearances', 0)

                    if games > 0:
                        print(f"    {season} - {level} ({team}): {games} games, {pa} PAs")

        except Exception as e:
            print(f"  Error: {e}")

        await asyncio.sleep(0.2)

async def check_gamelog_endpoint_method5(session):
    """Method 5: Direct person endpoint to see all available data"""
    print("\n" + "="*80)
    print("METHOD 5: Direct person endpoint")
    print("="*80)

    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}"
    params = {
        'hydrate': 'stats(group=[hitting,pitching],type=[yearByYear,career,gameLog],season=2025)'
    }

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            print(f"Status: {resp.status}")

            if resp.status == 200:
                data = await resp.json()

                if data.get('people'):
                    person = data['people'][0]
                    print(f"\nPlayer: {person.get('fullName')}")
                    print(f"Current Team: {person.get('currentTeam', {}).get('name', 'N/A')}")

                    if person.get('stats'):
                        print(f"\nStats found: {len(person['stats'])} groups")

                        for stat_group in person['stats']:
                            stat_type = stat_group.get('type', {}).get('displayName', 'Unknown')
                            group_name = stat_group.get('group', {}).get('displayName', 'Unknown')

                            if stat_group.get('splits'):
                                print(f"\n  {stat_type} - {group_name}: {len(stat_group['splits'])} entries")

                                # Show sport breakdown
                                by_sport = {}
                                for split in stat_group['splits']:
                                    sport_id = split.get('sport', {}).get('id')
                                    level = SPORT_MAP.get(sport_id, f"Sport_{sport_id}")

                                    if level not in by_sport:
                                        by_sport[level] = 0
                                    by_sport[level] += 1

                                for level, count in sorted(by_sport.items()):
                                    print(f"    {level}: {count} entries")

    except Exception as e:
        print(f"Error: {e}")

async def check_database_gamelogs():
    """Check what we currently have in database"""
    print("\n" + "="*80)
    print("CURRENT DATABASE GAME LOGS")
    print("="*80)

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT season, level, COUNT(*) as games,
               MIN(game_date) as first_date,
               MAX(game_date) as last_date,
               SUM(plate_appearances) as total_pa
        FROM milb_game_logs
        WHERE mlb_player_id = %s
        GROUP BY season, level
        ORDER BY season DESC, level
    """, (BRYCE_ELDRIDGE_ID,))

    results = cursor.fetchall()

    if results:
        print("\nGame logs in database:")
        for row in results:
            season, level, games, first, last, pa = row
            print(f"  {season} {level}: {games} games, {pa} PAs")
            print(f"    Date range: {first} to {last}")
    else:
        print("\nNo game logs found in database")

    conn.close()

async def main():
    print("="*80)
    print("COMPREHENSIVE GAME LOG COLLECTION INVESTIGATION")
    print(f"Player: Bryce Eldridge (ID: {BRYCE_ELDRIDGE_ID})")
    print(f"Season: {SEASON}")
    print("="*80)

    # Check database first
    await check_database_gamelogs()

    # Check MLB API with all methods
    async with aiohttp.ClientSession() as session:
        await check_gamelog_endpoint_method1(session)
        await check_gamelog_endpoint_method2(session)
        await check_gamelog_endpoint_method3(session)
        await check_gamelog_endpoint_method4(session)
        await check_gamelog_endpoint_method5(session)

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("1. Compare database vs API results")
    print("2. Identify any missing game logs")
    print("3. Update collection script if needed")

if __name__ == "__main__":
    asyncio.run(main())
