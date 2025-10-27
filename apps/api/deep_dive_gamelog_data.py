"""
Deep dive into the actual game log data structure
to find where the sport/level information is stored
"""

import asyncio
import aiohttp
import json

BRYCE_ELDRIDGE_ID = 805811
SEASON = 2025

async def deep_dive_gamelog_structure(session):
    """Examine the full structure of game log response"""
    print("="*80)
    print("DEEP DIVE: Game Log Data Structure")
    print("="*80)

    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'gameType': 'R',
        'season': SEASON
    }

    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            print(f"Error: Status {resp.status}")
            return

        data = await resp.json()

        if not data.get('stats') or not data['stats'][0].get('splits'):
            print("No splits found")
            return

        splits = data['stats'][0]['splits']
        print(f"\nFound {len(splits)} game log entries\n")

        # Examine first 3 games in detail
        for i, split in enumerate(splits[:3]):
            print(f"\n{'='*80}")
            print(f"GAME {i+1}")
            print(f"{'='*80}")

            # Game info
            game = split.get('game', {})
            print(f"\nGAME INFO:")
            print(f"  game_pk: {game.get('gamePk')}")
            print(f"  game_date: {split.get('date')}")

            # Check ALL keys in game object
            print(f"\n  All game keys: {list(game.keys())}")

            # Sport info
            sport = game.get('sport', {})
            print(f"\n  Sport object: {sport}")
            print(f"    sport.id: {sport.get('id')}")
            print(f"    sport.name: {sport.get('name')}")
            print(f"    sport.link: {sport.get('link')}")

            # Teams
            teams = game.get('teams', {})
            print(f"\n  Teams object keys: {list(teams.keys())}")

            if teams:
                away = teams.get('away', {})
                home = teams.get('home', {})

                print(f"\n  Away Team:")
                print(f"    name: {away.get('name')}")
                print(f"    team.id: {away.get('team', {}).get('id')}")
                if away.get('team'):
                    print(f"    team keys: {list(away.get('team', {}).keys())}")

                print(f"\n  Home Team:")
                print(f"    name: {home.get('name')}")
                print(f"    team.id: {home.get('team', {}).get('id')}")
                if home.get('team'):
                    print(f"    team keys: {list(home.get('team', {}).keys())}")

            # Team in split level
            team = split.get('team', {})
            print(f"\n  Split-level team:")
            print(f"    team.name: {team.get('name')}")
            print(f"    team.id: {team.get('id')}")
            print(f"    team keys: {list(team.keys())}")

            # League
            league = split.get('league', {})
            print(f"\n  League:")
            print(f"    league.id: {league.get('id')}")
            print(f"    league.name: {league.get('name')}")

            # Sport at split level
            split_sport = split.get('sport', {})
            print(f"\n  Split-level sport:")
            print(f"    sport.id: {split_sport.get('id')}")
            print(f"    sport.name: {split_sport.get('name')}")

            # Player
            player = split.get('player', {})
            print(f"\n  Player:")
            print(f"    player.id: {player.get('id')}")
            print(f"    player.fullName: {player.get('fullName')}")

            # Stats
            stat = split.get('stat', {})
            print(f"\n  Stats:")
            print(f"    gamesPlayed: {stat.get('gamesPlayed')}")
            print(f"    plateAppearances: {stat.get('plateAppearances')}")
            print(f"    atBats: {stat.get('atBats')}")

            # Dump full split structure
            print(f"\n  ALL SPLIT KEYS: {list(split.keys())}")

            # Save full JSON for first game
            if i == 0:
                print(f"\n  FULL GAME 1 JSON:")
                print(json.dumps(split, indent=2))

async def check_specific_game_feed(session, game_pk):
    """Check the game feed endpoint for sport info"""
    print(f"\n{'='*80}")
    print(f"GAME FEED CHECK: game_pk={game_pk}")
    print(f"{'='*80}")

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            print(f"Error: Status {resp.status}")
            return

        data = await resp.json()
        game_data = data.get('gameData', {})

        print(f"\nGame Data:")
        print(f"  date: {game_data.get('datetime', {}).get('officialDate')}")

        # Teams
        teams = game_data.get('teams', {})
        print(f"\nTeams:")

        for side in ['away', 'home']:
            team_data = teams.get(side, {})
            print(f"\n  {side.upper()}:")
            print(f"    name: {team_data.get('name')}")
            print(f"    id: {team_data.get('id')}")

            # Sport info at team level
            sport = team_data.get('sport', {})
            print(f"    sport.id: {sport.get('id')}")
            print(f"    sport.name: {sport.get('name')}")

            # League
            league = team_data.get('league', {})
            print(f"    league.id: {league.get('id')}")
            print(f"    league.name: {league.get('name')}")

            # Division
            division = team_data.get('division', {})
            print(f"    division.id: {division.get('id')}")
            print(f"    division.name: {division.get('name')}")

async def check_game_schedule_endpoint(session):
    """Check schedule endpoint for Bryce's team"""
    print(f"\n{'='*80}")
    print(f"SCHEDULE ENDPOINT CHECK")
    print(f"{'='*80}")

    # First, get Bryce's team ID from one of his games
    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ELDRIDGE_ID}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'gameType': 'R',
        'season': SEASON
    }

    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        data = await resp.json()
        splits = data['stats'][0]['splits']

        if splits:
            team_id = splits[0].get('team', {}).get('id')
            print(f"\nBryce's team ID: {team_id}")

            # Now check schedule for this team
            schedule_url = f"https://statsapi.mlb.com/api/v1/schedule"
            schedule_params = {
                'teamId': team_id,
                'season': SEASON,
                'sportId': '12',  # Try AA
                'gameType': 'R'
            }

            async with session.get(schedule_url, params=schedule_params, timeout=aiohttp.ClientTimeout(total=30)) as schedule_resp:
                print(f"\nSchedule request for AA (sportId=12):")
                print(f"  Status: {schedule_resp.status}")

                if schedule_resp.status == 200:
                    schedule_data = await schedule_resp.json()
                    total_games = schedule_data.get('totalGames', 0)
                    print(f"  Total games: {total_games}")

                    if total_games > 0:
                        dates = schedule_data.get('dates', [])
                        print(f"  Dates with games: {len(dates)}")

            # Try AAA
            schedule_params['sportId'] = '11'
            async with session.get(schedule_url, params=schedule_params, timeout=aiohttp.ClientTimeout(total=30)) as schedule_resp:
                print(f"\nSchedule request for AAA (sportId=11):")
                print(f"  Status: {schedule_resp.status}")

                if schedule_resp.status == 200:
                    schedule_data = await schedule_resp.json()
                    total_games = schedule_data.get('totalGames', 0)
                    print(f"  Total games: {total_games}")

async def main():
    async with aiohttp.ClientSession() as session:
        await deep_dive_gamelog_structure(session)

        # Check specific games from game feed
        print("\n" + "="*80)
        print("CHECKING SPECIFIC GAMES FROM GAME FEED")
        print("="*80)

        # Check the first Complex League game
        await check_specific_game_feed(session, 807831)

        # Check the first Regular Season game
        await check_specific_game_feed(session, 776309)

        # Check schedule endpoint
        await check_game_schedule_endpoint(session)

if __name__ == "__main__":
    asyncio.run(main())
