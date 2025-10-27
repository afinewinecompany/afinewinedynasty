"""Check Bryce Eldridge's full career stats"""
import asyncio
import aiohttp

MILB_SPORT_IDS = {11: 'AAA', 12: 'AA', 13: 'A+', 14: 'A', 15: 'Rk', 16: 'FRk', 5442: 'CPX'}

async def main():
    mlb_id = 805811

    async with aiohttp.ClientSession() as session:
        # Get career stats (all seasons combined)
        print("="*80)
        print("BRYCE ELDRIDGE - CAREER STATS (ALL LEVELS)")
        print("="*80)

        url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        params = {
            'stats': 'career',
            'group': 'hitting'
        }

        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    print(f"Status: {resp.status}")
                    return

                data = await resp.json()

                if 'stats' not in data or not data['stats']:
                    print("No stats found")
                    return

                for stat_group in data['stats']:
                    if 'splits' not in stat_group:
                        continue

                    print(f"\nStat Type: {stat_group.get('type', {}).get('displayName')}")

                    for split in stat_group['splits']:
                        team = split.get('team', {})
                        sport = split.get('sport', {})
                        stat = split.get('stat', {})

                        sport_id = sport.get('id')
                        level = MILB_SPORT_IDS.get(sport_id, sport.get('name', 'Unknown'))

                        games = stat.get('gamesPlayed', 0)
                        pa = stat.get('plateAppearances', 0)

                        if games > 0:
                            print(f"\n  {level} - {team.get('name', 'Unknown')}")
                            print(f"    Games: {games}, PAs: {pa}")
                            print(f"    Expected pitches: ~{int(pa * 4.5)}")
                            print(f"    AVG: {stat.get('avg', '.000')}")

        except Exception as e:
            print(f"Error: {e}")

        # Try year-by-year with more detail
        print("\n" + "="*80)
        print("YEAR BY YEAR (ALL SEASONS)")
        print("="*80)

        url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
        params = {
            'stats': 'yearByYearAdvanced',
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

                            total_pa_all = 0
                            for split in stat_group['splits']:
                                season = split.get('season')
                                team = split.get('team', {})
                                sport = split.get('sport', {})
                                stat = split.get('stat', {})

                                sport_id = sport.get('id')
                                level = MILB_SPORT_IDS.get(sport_id, sport.get('name', 'Unknown'))

                                games = stat.get('gamesPlayed', 0)
                                pa = stat.get('plateAppearances', 0)
                                total_pa_all += pa

                                if games > 0:
                                    print(f"\n{season} - {level} ({team.get('name', 'Unknown')})")
                                    print(f"  Games: {games}, PAs: {pa}, Expected pitches: ~{int(pa * 4.5)}")

                            print(f"\n*** CAREER TOTAL PAs: {total_pa_all} ***")
                            print(f"*** Expected TOTAL pitches: ~{int(total_pa_all * 4.5)} ***")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
