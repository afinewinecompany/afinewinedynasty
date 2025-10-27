"""
Comprehensive investigation of Bryce Eldridge's data across all sources
"""

import asyncio
import aiohttp
import psycopg2

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

MILB_SPORT_IDS = {
    11: 'AAA',
    12: 'AA',
    13: 'A+',
    14: 'A',
    15: 'Rk',
    16: 'FRk',
    5442: 'CPX',
}

async def check_mlb_api_all_seasons():
    """Check MLB API for all available seasons"""
    mlb_id = 805811  # Bryce Eldridge

    print("="*80)
    print("BRYCE ELDRIDGE - MLB STATS API CHECK (ALL SEASONS)")
    print("="*80)

    async with aiohttp.ClientSession() as session:
        for season in [2025, 2024, 2023, 2022]:
            print(f"\n{'='*80}")
            print(f"SEASON {season}")
            print(f"{'='*80}")

            url = f"https://statsapi.mlb.com/api/v1/people/{mlb_id}/stats"
            params = {
                'stats': 'gameLog',
                'group': 'hitting',
                'gameType': 'R',
                'season': season
            }

            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        print(f"  Status: {resp.status}")
                        continue

                    data = await resp.json()

                    if 'stats' not in data or not data['stats']:
                        print(f"  No stats found")
                        continue

                    stats = data['stats'][0]
                    if 'splits' not in stats or not stats['splits']:
                        print(f"  No games found")
                        continue

                    # Group by sport_id
                    by_sport = {}
                    total_games = len(stats['splits'])

                    for split in stats['splits']:
                        game = split.get('game', {})
                        sport = game.get('sport', {})
                        sport_id = sport.get('id')
                        sport_name = sport.get('name', 'Unknown')

                        if sport_id not in by_sport:
                            by_sport[sport_id] = {
                                'name': sport_name,
                                'games': [],
                                'total_pa': 0
                            }

                        pa = split.get('stat', {}).get('plateAppearances', 0)
                        by_sport[sport_id]['games'].append({
                            'date': split.get('date'),
                            'game_pk': game.get('gamePk'),
                            'pa': pa
                        })
                        by_sport[sport_id]['total_pa'] += pa

                    print(f"\n  Total games: {total_games}")

                    for sport_id, info in sorted(by_sport.items()):
                        level = MILB_SPORT_IDS.get(sport_id, info['name'])
                        expected_pitches = int(info['total_pa'] * 4.5)

                        print(f"\n  {level} (sport_id: {sport_id}):")
                        print(f"    Games: {len(info['games'])}")
                        print(f"    Total PAs: {info['total_pa']}")
                        print(f"    Expected pitches: ~{expected_pitches}")
                        print(f"    Date range: {info['games'][0]['date']} to {info['games'][-1]['date']}")

                        # Show first 3 game_pks
                        print(f"    Sample game_pks: {', '.join(str(g['game_pk']) for g in info['games'][:3])}")

            except Exception as e:
                print(f"  Error: {e}")

def check_database():
    """Check what we have in the database"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    print("\n" + "="*80)
    print("DATABASE - GAME LOGS")
    print("="*80)

    cursor.execute("""
        SELECT season, level, COUNT(*) as games, SUM(plate_appearances) as total_pa,
               MIN(game_date) as first_date, MAX(game_date) as last_date,
               STRING_AGG(DISTINCT game_pk::text, ', ') as sample_game_pks
        FROM milb_game_logs
        WHERE mlb_player_id = 805811
        GROUP BY season, level
        ORDER BY season DESC, level
    """)

    for row in cursor.fetchall():
        season, level, games, pa, first, last, game_pks = row
        print(f"\n{season} - {level}:")
        print(f"  Games: {games}, PAs: {pa}")
        print(f"  Dates: {first} to {last}")
        print(f"  Sample game_pks: {game_pks[:100]}...")

    print("\n" + "="*80)
    print("DATABASE - PITCH DATA")
    print("="*80)

    cursor.execute("""
        SELECT season, level, COUNT(DISTINCT game_pk) as games, COUNT(*) as pitches,
               MIN(game_date) as first_date, MAX(game_date) as last_date
        FROM milb_batter_pitches
        WHERE mlb_batter_id = 805811
        GROUP BY season, level
        ORDER BY season DESC, level
    """)

    rows = cursor.fetchall()
    if rows:
        for row in rows:
            season, level, games, pitches, first, last = row
            print(f"\n{season} - {level}:")
            print(f"  Games: {games}, Pitches: {pitches}")
            print(f"  Dates: {first} to {last}")
    else:
        print("\n  No pitch data found")

    conn.close()

async def main():
    print("\n" + "="*80)
    print("COMPREHENSIVE BRYCE ELDRIDGE INVESTIGATION")
    print("="*80)
    print("\nExpected (per user):")
    print("  CPX: 25 pitches")
    print("  AA: 556 pitches")
    print("  AAA: 1,165 pitches")
    print("  TOTAL: 1,746 pitches")

    # Check MLB API
    await check_mlb_api_all_seasons()

    # Check database
    check_database()

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
