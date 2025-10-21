"""Check what MiLB data exists for Bryce Eldridge via MLB API"""
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
    batter_id = 805811
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

            # Categorize games by sport_id
            mlb_games = []
            milb_games = []

            for split in stats['splits']:
                game = split.get('game', {})
                sport = game.get('sport', {})
                sport_id = sport.get('id')
                game_pk = game.get('gamePk')
                game_date = split.get('date')
                pa = split.get('stat', {}).get('plateAppearances', 0)

                if sport_id == 1:  # MLB
                    mlb_games.append({
                        'game_pk': game_pk,
                        'date': game_date,
                        'pa': pa
                    })
                elif sport_id in MILB_SPORT_IDS:
                    level = MILB_SPORT_IDS[sport_id]
                    milb_games.append({
                        'game_pk': game_pk,
                        'date': game_date,
                        'level': level,
                        'pa': pa
                    })

            print("\n" + "="*80)
            print(f"BRYCE ELDRIDGE - 2025 SEASON (MLB API)")
            print("="*80)

            if mlb_games:
                total_mlb_pa = sum(g['pa'] for g in mlb_games)
                print(f"\nMLB Games: {len(mlb_games)}")
                print(f"  Total PAs: {total_mlb_pa}")
                print(f"  Expected pitches: ~{int(total_mlb_pa * 4.5)}")
                print(f"  Date range: {mlb_games[0]['date']} to {mlb_games[-1]['date']}")

            if milb_games:
                total_milb_pa = sum(g['pa'] for g in milb_games)
                print(f"\nMiLB Games: {len(milb_games)}")
                print(f"  Total PAs: {total_milb_pa}")
                print(f"  Expected pitches: ~{int(total_milb_pa * 4.5)}")

                # Break down by level
                by_level = {}
                for g in milb_games:
                    level = g['level']
                    if level not in by_level:
                        by_level[level] = []
                    by_level[level].append(g)

                for level, games in sorted(by_level.items()):
                    level_pa = sum(g['pa'] for g in games)
                    print(f"\n  {level}: {len(games)} games, {level_pa} PAs")
                    print(f"    Expected pitches: ~{int(level_pa * 4.5)}")
                    print(f"    Date range: {games[0]['date']} to {games[-1]['date']}")
            else:
                print("\nNo MiLB games found in 2025")

            # Try 2024
            print("\n" + "="*80)
            print("Checking 2024 season...")
            print("="*80)

        params['season'] = 2024
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if 'stats' in data and data['stats']:
                    stats = data['stats'][0]
                    if 'splits' in stats and stats['splits']:
                        total_games = len(stats['splits'])
                        total_pa = sum(s.get('stat', {}).get('plateAppearances', 0) for s in stats['splits'])
                        print(f"\n2024: {total_games} games, {total_pa} PAs")
                        print(f"Expected pitches: ~{int(total_pa * 4.5)}")

                        # Sample first game
                        first = stats['splits'][0]
                        sport_id = first.get('game', {}).get('sport', {}).get('id')
                        level_name = MILB_SPORT_IDS.get(sport_id, f"Unknown ({sport_id})")
                        print(f"First game level: {level_name}")
                    else:
                        print("No 2024 games found")

if __name__ == "__main__":
    asyncio.run(main())
