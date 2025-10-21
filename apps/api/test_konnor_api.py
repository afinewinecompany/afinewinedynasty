"""Test if MLB API returns Konnor's MiLB games"""
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

async def main():
    batter_id = 804606  # Konnor Griffin
    season = 2025

    async with aiohttp.ClientSession() as session:
        url = f"https://statsapi.mlb.com/api/v1/people/{batter_id}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'gameType': 'R',
            'season': season
        }

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                print(f"Error: {resp.status}")
                return

            data = await resp.json()

            if 'stats' not in data or not data['stats']:
                print("No stats found")
                return

            stats = data['stats'][0]
            if 'splits' not in stats:
                print("No splits found")
                return

            # Group by level
            by_level = {}
            for split in stats['splits']:
                game = split.get('game', {})
                sport = game.get('sport', {})
                sport_id = sport.get('id')
                level = MILB_SPORT_IDS.get(sport_id, f"Unknown ({sport_id})")

                pa = split.get('stat', {}).get('plateAppearances', 0)

                if level not in by_level:
                    by_level[level] = {'games': 0, 'pa': 0}
                by_level[level]['games'] += 1
                by_level[level]['pa'] += pa

            print("\n" + "="*80)
            print(f"KONNOR GRIFFIN - 2025 SEASON (MLB API)")
            print("="*80)
            print(f"\nTotal games returned: {len(stats['splits'])}")

            for level in sorted(by_level.keys()):
                info = by_level[level]
                expected_pitches = int(info['pa'] * 4.5)
                print(f"\n{level}:")
                print(f"  Games: {info['games']}")
                print(f"  PAs: {info['pa']}")
                print(f"  Expected pitches: ~{expected_pitches}")

            total_pa = sum(info['pa'] for info in by_level.values())
            print(f"\nTOTAL PAs: {total_pa}")
            print(f"TOTAL Expected pitches: ~{int(total_pa * 4.5)}")

if __name__ == "__main__":
    asyncio.run(main())
