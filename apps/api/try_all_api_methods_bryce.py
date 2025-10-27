"""
Try EVERY possible MLB API method to find Bryce Eldridge's AA/AAA games
"""

import asyncio
import aiohttp
import json

BRYCE_ID = 805811
SEASON = 2024  # Try 2024 since user said he should have AA/AAA data

SPORT_MAP = {
    1: 'MLB', 11: 'AAA', 12: 'AA', 13: 'A+', 14: 'A', 15: 'Rk',
    16: 'FRk', 586: 'FCL', 5442: 'CPX'
}

async def try_stats_with_sportid(session):
    """Try requesting stats with specific sportId parameter"""
    print("\n" + "="*80)
    print("METHOD: /stats endpoint WITH sportId parameter")
    print("="*80)

    for sport_id, level_name in SPORT_MAP.items():
        url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ID}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'season': SEASON,
            'sportId': sport_id
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    continue

                data = await resp.json()

                if not data.get('stats') or not data['stats'][0].get('splits'):
                    continue

                splits = data['stats'][0]['splits']
                if splits:
                    print(f"\n  sportId={sport_id} ({level_name}): {len(splits)} games found")

                    # Show first 3 games
                    for i, split in enumerate(splits[:3]):
                        date = split.get('date')
                        game_pk = split.get('game', {}).get('gamePk')
                        team = split.get('team', {}).get('name')
                        opponent = split.get('opponent', {}).get('name')
                        pa = split.get('stat', {}).get('plateAppearances', 0)

                        print(f"      {date} | game_pk={game_pk} | {team} vs {opponent} | {pa} PAs")

        except Exception as e:
            print(f"  sportId={sport_id}: Error - {e}")

        await asyncio.sleep(0.2)

async def try_team_roster_endpoint(session):
    """Try finding Bryce's team and checking its roster"""
    print("\n" + "="*80)
    print("METHOD: Check team rosters for Bryce Eldridge")
    print("="*80)

    # First, get Bryce's full player info
    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ID}"

    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            print(f"Error: Status {resp.status}")
            return

        data = await resp.json()
        person = data.get('people', [{}])[0]

        print(f"\nPlayer: {person.get('fullName')}")
        print(f"Current Team: {person.get('currentTeam', {}).get('name', 'N/A')}")

        # Check draft info
        draft = person.get('draftYear')
        if draft:
            print(f"Draft Year: {draft}")

        # Check all teams
        if person.get('teams'):
            print(f"\nAll Teams:")
            for team in person.get('teams', []):
                print(f"  {team.get('season')} - {team.get('name')}")

async def try_transactions_endpoint(session):
    """Check player transactions/assignments"""
    print("\n" + "="*80)
    print("METHOD: Check player transactions")
    print("="*80)

    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ID}"
    params = {
        'hydrate': 'transactions'
    }

    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            print(f"Error: Status {resp.status}")
            return

        data = await resp.json()
        person = data.get('people', [{}])[0]

        transactions = person.get('transactions', [])
        if transactions:
            print(f"\nFound {len(transactions)} transactions:")
            for trans in transactions:
                date = trans.get('date')
                from_team = trans.get('fromTeam', {}).get('name', 'N/A')
                to_team = trans.get('toTeam', {}).get('name', 'N/A')
                type_desc = trans.get('typeDesc', 'Unknown')

                print(f"  {date}: {type_desc}")
                print(f"    From: {from_team} -> To: {to_team}")
        else:
            print("No transactions found")

async def try_milb_central_registry(session):
    """Try querying MiLB Central Registry"""
    print("\n" + "="*80)
    print("METHOD: MiLB Central Registry search")
    print("="*80)

    # Try searching by name
    url = "https://statsapi.mlb.com/api/v1/people/search"
    params = {
        'names': 'Bryce Eldridge'
    }

    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            print(f"Error: Status {resp.status}")
            return

        data = await resp.json()
        people = data.get('people', [])

        if people:
            print(f"\nFound {len(people)} players:")
            for person in people:
                name = person.get('fullName')
                player_id = person.get('id')
                current_team = person.get('currentTeam', {}).get('name', 'N/A')

                print(f"  {name} (ID: {player_id}) - {current_team}")

async def try_prospects_endpoint(session):
    """Try prospects API endpoint"""
    print("\n" + "="*80)
    print("METHOD: Prospects API")
    print("="*80)

    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ID}"
    params = {
        'hydrate': 'rosterEntries'
    }

    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            print(f"Error: Status {resp.status}")
            return

        data = await resp.json()
        person = data.get('people', [{}])[0]

        roster_entries = person.get('rosterEntries', [])
        if roster_entries:
            print(f"\nFound {len(roster_entries)} roster entries:")
            for entry in roster_entries:
                team = entry.get('team', {}).get('name', 'Unknown')
                season = entry.get('season', 'Unknown')
                jersey_number = entry.get('jerseyNumber', 'N/A')

                print(f"  {season}: {team} (#{jersey_number})")
        else:
            print("No roster entries found")

async def try_season_specific_search(session):
    """Try each season individually with ALL game types"""
    print("\n" + "="*80)
    print("METHOD: Season-by-season search (2022-2025)")
    print("="*80)

    game_types = ['R', 'S', 'E', 'F', 'D', 'L', 'W', 'C', 'A', 'I', 'P']

    for season in [2022, 2023, 2024, 2025]:
        print(f"\n  SEASON {season}:")

        season_found = False

        for game_type in game_types:
            url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ID}/stats"
            params = {
                'stats': 'gameLog',
                'group': 'hitting',
                'season': season,
                'gameType': game_type
            }

            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        continue

                    data = await resp.json()

                    if not data.get('stats') or not data['stats'][0].get('splits'):
                        continue

                    splits = data['stats'][0]['splits']
                    if splits:
                        season_found = True

                        # Group by sport
                        by_sport = {}
                        for split in splits:
                            sport_id = split.get('sport', {}).get('id')
                            level = SPORT_MAP.get(sport_id, f"Sport_{sport_id}")

                            if level not in by_sport:
                                by_sport[level] = []
                            by_sport[level].append(split)

                        print(f"    Game Type '{game_type}':")
                        for level, level_splits in sorted(by_sport.items()):
                            print(f"      {level}: {len(level_splits)} games")

            except Exception as e:
                pass

            await asyncio.sleep(0.1)

        if not season_found:
            print(f"    No data found for {season}")

async def main():
    print("="*80)
    print("EXHAUSTIVE MLB API SEARCH FOR BRYCE ELDRIDGE AA/AAA GAMES")
    print("="*80)
    print(f"\nPlayer ID: {BRYCE_ID}")
    print(f"Primary Season: {SEASON}")
    print(f"\nTrying ALL possible API endpoints and parameters...")

    async with aiohttp.ClientSession() as session:
        await try_stats_with_sportid(session)
        await try_team_roster_endpoint(session)
        await try_transactions_endpoint(session)
        await try_milb_central_registry(session)
        await try_prospects_endpoint(session)
        await try_season_specific_search(session)

    print("\n" + "="*80)
    print("SEARCH COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
