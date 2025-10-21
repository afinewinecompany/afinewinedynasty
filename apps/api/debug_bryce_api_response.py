"""Debug what sport IDs are being returned for Bryce Eldridge"""
import asyncio
import aiohttp
import json

async def main():
    batter_id = 805811  # Bryce Eldridge
    season = 2025

    url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'gameType': 'R',
        'season': season
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status}")
                return

            data = await resp.json()

            # Pretty print the structure to see what we're getting
            print("="*80)
            print(f"BRYCE ELDRIDGE ({batter_id}) - 2025 SEASON")
            print("="*80)

            if 'stats' not in data or not data['stats']:
                print("No stats found")
                return

            stats = data['stats'][0]
            if 'splits' not in stats:
                print("No splits found")
                return

            print(f"\nTotal games: {len(stats['splits'])}")

            # Sample first game to see structure
            if stats['splits']:
                print("\n" + "="*80)
                print("FIRST GAME SAMPLE:")
                print("="*80)
                print(json.dumps(stats['splits'][0], indent=2))

            # Collect unique sport IDs
            sport_ids = {}
            for split in stats['splits']:
                game = split.get('game', {})
                sport = game.get('sport', {})
                sport_id = sport.get('id')
                sport_name = sport.get('name', 'Unknown')

                if sport_id:
                    if sport_id not in sport_ids:
                        sport_ids[sport_id] = {
                            'name': sport_name,
                            'count': 0
                        }
                    sport_ids[sport_id]['count'] += 1

            print("\n" + "="*80)
            print("SPORT IDs FOUND:")
            print("="*80)
            for sport_id, info in sorted(sport_ids.items()):
                print(f"  ID {sport_id}: {info['name']} ({info['count']} games)")

if __name__ == "__main__":
    asyncio.run(main())
