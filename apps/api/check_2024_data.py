"""Check 2024 season data for prospects"""
import asyncio
import aiohttp

MILB_SPORT_IDS = {
    11: 'AAA',
    12: 'AA',
    13: 'A+',
    14: 'A',
    15: 'Rk',
    16: 'FRk',
    5442: 'CPX',
}

async def check_bryce_2024():
    batter_id = 805811  # Bryce Eldridge

    async with aiohttp.ClientSession() as session:
        url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'gameType': 'R',
            'season': 2024
        }

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status}")
                return

            data = await resp.json()

            if 'stats' not in data or not data['stats'] or not data['stats'][0].get('splits'):
                print("No 2024 stats found for Bryce Eldridge")
                return

            stats = data['stats'][0]['splits']

            # Group by level
            by_level = {}
            for split in stats:
                game = split.get('game', {})
                sport = game.get('sport', {})
                sport_id = sport.get('id')
                level = MILB_SPORT_IDS.get(sport_id, f"MLB" if sport_id == 1 else f"Unknown ({sport_id})")

                pa = split.get('stat', {}).get('plateAppearances', 0)

                if level not in by_level:
                    by_level[level] = {'games': 0, 'pa': 0}
                by_level[level]['games'] += 1
                by_level[level]['pa'] += pa

            print("\n" + "="*80)
            print("BRYCE ELDRIDGE - 2024 SEASON")
            print("="*80)
            print(f"\nTotal games: {len(stats)}")

            for level in sorted(by_level.keys()):
                info = by_level[level]
                expected_pitches = int(info['pa'] * 4.5)
                print(f"\n{level}:")
                print(f"  Games: {info['games']}")
                print(f"  PAs: {info['pa']}")
                print(f"  Expected pitches: ~{expected_pitches}")

            total_pa = sum(info['pa'] for info in by_level.values())
            print(f"\nTOTAL: {total_pa} PAs, ~{int(total_pa * 4.5)} expected pitches")

async def check_konnor_2024():
    batter_id = 804606  # Konnor Griffin

    async with aiohttp.ClientSession() as session:
        url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'gameType': 'R',
            'season': 2024
        }

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status}")
                return

            data = await resp.json()

            if 'stats' not in data or not data['stats'] or not data['stats'][0].get('splits'):
                print("No 2024 stats found for Konnor Griffin")
                return

            stats = data['stats'][0]['splits']

            # Group by level
            by_level = {}
            for split in stats:
                game = split.get('game', {})
                sport = game.get('sport', {})
                sport_id = sport.get('id')
                level = MILB_SPORT_IDS.get(sport_id, f"MLB" if sport_id == 1 else f"Unknown ({sport_id})")

                pa = split.get('stat', {}).get('plateAppearances', 0)

                if level not in by_level:
                    by_level[level] = {'games': 0, 'pa': 0}
                by_level[level]['games'] += 1
                by_level[level]['pa'] += pa

            print("\n" + "="*80)
            print("KONNOR GRIFFIN - 2024 SEASON")
            print("="*80)
            print(f"\nTotal games: {len(stats)}")

            for level in sorted(by_level.keys()):
                info = by_level[level]
                expected_pitches = int(info['pa'] * 4.5)
                print(f"\n{level}:")
                print(f"  Games: {info['games']}")
                print(f"  PAs: {info['pa']}")
                print(f"  Expected pitches: ~{expected_pitches}")

            total_pa = sum(info['pa'] for info in by_level.values())
            print(f"\nTOTAL: {total_pa} PAs, ~{int(total_pa * 4.5)} expected pitches")

async def main():
    await check_bryce_2024()
    print("\n\n")
    await check_konnor_2024()

if __name__ == "__main__":
    asyncio.run(main())
