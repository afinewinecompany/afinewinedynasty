"""Check Bryce Eldridge's season stats to see what levels he played"""
import asyncio
import aiohttp
import json

MILB_SPORT_IDS = {11: 'AAA', 12: 'AA', 13: 'A+', 14: 'A', 15: 'Rk', 16: 'FRk', 5442: 'CPX'}

async def main():
    mlb_id = 805811

    async with aiohttp.ClientSession() as session:
        # Try season stats instead of game log
        for season in [2025, 2024]:
            print(f"\n{'='*80}")
            print(f"SEASON {season} - SEASON STATS BY TEAM")
            print(f"{'='*80}")

            url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
            params = {
                'stats': 'season',
                'group': 'hitting',
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

                    for stat_group in data['stats']:
                        if 'splits' not in stat_group:
                            continue

                        for split in stat_group['splits']:
                            team = split.get('team', {})
                            sport = split.get('sport', {})
                            league = split.get('league', {})
                            stat = split.get('stat', {})

                            sport_id = sport.get('id')
                            level = MILB_SPORT_IDS.get(sport_id, sport.get('name', 'Unknown'))

                            games = stat.get('gamesPlayed', 0)
                            pa = stat.get('plateAppearances', 0)
                            avg = stat.get('avg', '.000')

                            print(f"\n  {team.get('name', 'Unknown')} - {level}")
                            print(f"    League: {league.get('name', 'Unknown')}")
                            print(f"    Games: {games}, PAs: {pa}")
                            print(f"    AVG: {avg}")
                            print(f"    Expected pitches: ~{int(pa * 4.5)}")

            except Exception as e:
                print(f"  Error: {e}")

        # Also try yearByYear stats
        print(f"\n{'='*80}")
        print(f"YEAR BY YEAR STATS")
        print(f"{'='*80}")

        url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        params = {
            'stats': 'yearByYear',
            'group': 'hitting'
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()

                    if 'stats' in data and data['stats']:
                        for stat_group in data['stats']:
                            if 'splits' not in stat_group:
                                continue

                            for split in stat_group['splits']:
                                season = split.get('season')
                                team = split.get('team', {})
                                sport = split.get('sport', {})
                                stat = split.get('stat', {})

                                sport_id = sport.get('id')
                                level = MILB_SPORT_IDS.get(sport_id, sport.get('name', 'Unknown'))

                                games = stat.get('gamesPlayed', 0)
                                pa = stat.get('plateAppearances', 0)
                                avg = stat.get('avg', '.000')

                                if games > 0:
                                    print(f"\n  {season} - {team.get('name', 'Unknown')} ({level})")
                                    print(f"    Games: {games}, PAs: {pa}, AVG: {avg}")
                                    print(f"    Expected pitches: ~{int(pa * 4.5)}")

        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
