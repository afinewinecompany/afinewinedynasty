"""
Check ALL possible game types for Bryce in 2024 with detailed output
"""
import asyncio
import aiohttp
import json

MILB_SPORT_IDS = {11: 'AAA', 12: 'AA', 13: 'A+', 14: 'A', 15: 'Rk', 16: 'FRk', 5442: 'CPX'}

# All known MLB API game type codes
GAME_TYPES = {
    'R': 'Regular Season',
    'F': 'Wild Card',
    'D': 'Division Series',
    'L': 'League Championship',
    'W': 'World Series',
    'S': 'Spring Training',
    'E': 'Exhibition',
    'A': 'All-Star Game',
    'I': 'Intrasquad',
    'P': 'Playoffs',
}

async def check_all_types():
    mlb_id = 805811
    season = 2024

    print("="*80)
    print(f"BRYCE ELDRIDGE - ALL GAME TYPES FOR 2024")
    print("="*80)

    async with aiohttp.ClientSession() as session:
        found_any = False

        for game_code, game_name in GAME_TYPES.items():
            url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
            params = {
                'stats': 'gameLog',
                'group': 'hitting',
                'gameType': game_code,
                'season': season
            }

            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        continue

                    data = await resp.json()

                    if 'stats' not in data or not data['stats']:
                        continue

                    stats = data['stats'][0]
                    if 'splits' not in stats or not stats['splits']:
                        continue

                    # Found data!
                    found_any = True
                    print(f"\n{'='*80}")
                    print(f"FOUND: {game_name} ({game_code})")
                    print(f"{'='*80}")

                    # Group by sport/level
                    by_level = {}
                    for split in stats['splits']:
                        sport_id = split.get('game', {}).get('sport', {}).get('id')
                        level = MILB_SPORT_IDS.get(sport_id, f"Unknown (sport_id:{sport_id})")

                        if level not in by_level:
                            by_level[level] = []
                        by_level[level].append(split)

                    for level, splits in sorted(by_level.items()):
                        total_pa = sum(s.get('stat', {}).get('plateAppearances', 0) for s in splits)
                        expected_pitches = int(total_pa * 4.5)

                        print(f"\n  {level}:")
                        print(f"    Games: {len(splits)}")
                        print(f"    PAs: {total_pa}")
                        print(f"    Expected pitches: ~{expected_pitches}")
                        print(f"    Dates: {splits[0].get('date')} to {splits[-1].get('date')}")

                        # Show sample game_pks
                        sample_pks = [s.get('game', {}).get('gamePk') for s in splits[:5]]
                        print(f"    Sample game_pks: {', '.join(map(str, sample_pks))}")

            except Exception as e:
                print(f"Error checking {game_code}: {e}")
                continue

        if not found_any:
            print("\n*** NO DATA FOUND FOR 2024 IN ANY GAME TYPE ***")

        # Also try without specifying game type
        print(f"\n{'='*80}")
        print("TRYING WITHOUT GAME TYPE FILTER")
        print(f"{'='*80}")

        url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        params = {
            'stats': 'gameLog',
            'group': 'hitting',
            'season': season
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if 'stats' in data and data['stats'] and data['stats'][0].get('splits'):
                        splits = data['stats'][0]['splits']
                        print(f"\nFound {len(splits)} games total")

                        # Show unique game types
                        game_types_found = set()
                        for split in splits:
                            gt = split.get('game', {}).get('type')
                            if gt:
                                game_types_found.add(gt)

                        print(f"Game types present: {', '.join(sorted(game_types_found))}")
                    else:
                        print("\nNo data found")
                else:
                    print(f"\nStatus: {resp.status}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_all_types())
