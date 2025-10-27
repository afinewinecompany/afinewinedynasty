"""Check details of one of Bryce's games to see what sport_id it has"""
import asyncio
import aiohttp
import json

async def main():
    # One of Bryce's games from Sept 2025
    game_pk = 776309

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status}")
                return

            data = await resp.json()

            game_data = data.get('gameData', {})

            print("="*80)
            print(f"GAME {game_pk} DETAILS")
            print("="*80)

            # Check teams
            teams = game_data.get('teams', {})
            away = teams.get('away', {})
            home = teams.get('home', {})

            print(f"\nAway: {away.get('name')} (ID: {away.get('id')})")
            print(f"Home: {home.get('name')} (ID: {home.get('id')})")

            # Check venue
            venue = game_data.get('venue', {})
            print(f"\nVenue: {venue.get('name')}")

            # Check datetime
            dt = game_data.get('datetime', {})
            print(f"Date: {dt.get('officialDate')}")

            # Check status
            status = game_data.get('status', {})
            print(f"Status: {status.get('detailedState')}")

            # Most importantly - check if this is MLB or MiLB
            print(f"\nGame Type: {game_data.get('gameType')}")

            # Check players to see if Bryce is there
            all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])

            bryce_plays = 0
            bryce_pitches = 0
            for play in all_plays:
                if play.get('matchup', {}).get('batter', {}).get('id') == 805811:
                    bryce_plays += 1
                    for event in play.get('playEvents', []):
                        if event.get('isPitch'):
                            bryce_pitches += 1

            print(f"\nBryce Eldridge:")
            print(f"  Plate appearances: {bryce_plays}")
            print(f"  Pitches faced: {bryce_pitches}")

            # Check if MLB or MiLB by looking at team IDs
            if away.get('id') in [108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 158]:
                print(f"\n*** THIS IS AN MLB GAME ***")
            else:
                print(f"\n*** THIS IS A MiLB GAME (team ID: {away.get('id')}) ***")

if __name__ == "__main__":
    asyncio.run(main())
