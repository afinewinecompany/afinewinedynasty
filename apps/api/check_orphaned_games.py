"""
Check what the orphaned 'AA' games actually are
"""
import asyncio
import aiohttp

# The 10 orphaned game_pks labeled as "AA"
GAME_PKS = [776309, 776279, 776271, 776233, 776227, 776220, 776211, 776196, 776166, 776137]

async def check_game(session, game_pk):
    """Check a specific game in MLB API"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"game_pk={game_pk}: API returned {resp.status}")
                return

            data = await resp.json()
            game_data = data.get('gameData', {})

            game_date = game_data.get('datetime', {}).get('officialDate', 'Unknown')
            venue = game_data.get('venue', {}).get('name', 'Unknown')
            away_team = game_data.get('teams', {}).get('away', {}).get('name', 'Unknown')
            home_team = game_data.get('teams', {}).get('home', {}).get('name', 'Unknown')

            # Get sport info
            status = data.get('gameData', {}).get('status', {})
            game_type = status.get('codedGameState', 'Unknown')

            # Sport level
            teams_data = game_data.get('teams', {})
            home_sport_id = teams_data.get('home', {}).get('sport', {}).get('id', 'Unknown')
            away_sport_id = teams_data.get('away', {}).get('sport', {}).get('id', 'Unknown')

            sport_map = {1: 'MLB', 11: 'AAA', 12: 'AA', 13: 'A+', 14: 'A', 15: 'Rk', 16: 'FRk', 5442: 'CPX'}
            home_level = sport_map.get(home_sport_id, f"Sport_{home_sport_id}")
            away_level = sport_map.get(away_sport_id, f"Sport_{away_sport_id}")

            print(f"\ngame_pk={game_pk} | {game_date}")
            print(f"  {away_team} ({away_level}) @ {home_team} ({home_level})")
            print(f"  Venue: {venue}")
            print(f"  Sport ID: Home={home_sport_id}, Away={away_sport_id}")

    except Exception as e:
        print(f"game_pk={game_pk}: Error - {e}")

async def main():
    print("="*80)
    print("CHECKING ORPHANED 'AA' GAMES")
    print("="*80)
    print("\nThese games have pitch data labeled 'AA' but no corresponding game logs.")
    print("Let's find out what they actually are:\n")

    async with aiohttp.ClientSession() as session:
        for game_pk in GAME_PKS:
            await check_game(session, game_pk)
            await asyncio.sleep(0.3)

    print("\n" + "="*80)
    print("CONCLUSION")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
