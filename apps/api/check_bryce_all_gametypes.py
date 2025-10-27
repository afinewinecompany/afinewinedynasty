"""Check all game types for Bryce Eldridge in 2024"""
import asyncio
import aiohttp

MILB_SPORT_IDS = {11: 'AAA', 12: 'AA', 13: 'A+', 14: 'A', 15: 'Rk', 16: 'FRk', 5442: 'CPX'}

async def main():
    mlb_id = 805811
    season = 2024

    # Try different game types
    game_types = ['R', 'S', 'E', 'F', 'D', 'L', 'W', 'C']  # R=Regular, S=Spring, E=Exhibition, etc.

    async with aiohttp.ClientSession() as session:
        for game_type in game_types:
            print(f"\n{'='*80}")
            print(f"GAME TYPE: {game_type} (Season 2024)")
            print(f"{'='*80}")

            url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
            params = {
                'stats': 'gameLog',
                'group': 'hitting',
                'gameType': game_type,
                'season': season
            }

            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        print(f"  Status: {resp.status}")
                        continue

                    data = await resp.json()

                    if 'stats' not in data or not data['stats']:
                        print(f"  No stats")
                        continue

                    stats = data['stats'][0]
                    if 'splits' not in stats or not stats['splits']:
                        print(f"  No games")
                        continue

                    # Group by sport_id
                    by_sport = {}
                    for split in stats['splits']:
                        sport_id = split.get('game', {}).get('sport', {}).get('id')
                        if sport_id not in by_sport:
                            by_sport[sport_id] = []
                        by_sport[sport_id].append(split)

                    print(f"\n  Found {len(stats['splits'])} games")

                    for sport_id, splits in sorted(by_sport.items()):
                        level = MILB_SPORT_IDS.get(sport_id, f"sport_id:{sport_id}")
                        total_pa = sum(s.get('stat', {}).get('plateAppearances', 0) for s in splits)
                        expected_pitches = int(total_pa * 4.5)

                        print(f"\n    {level}: {len(splits)} games, {total_pa} PAs, ~{expected_pitches} pitches")
                        print(f"      Dates: {splits[0].get('date')} to {splits[-1].get('date')}")

            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
