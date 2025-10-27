"""
Fixed game log collection for Bryce Eldridge
Properly queries each sport level separately using sportId parameter
"""

import asyncio
import aiohttp
import psycopg2
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

BRYCE_ID = 805811
SEASONS = [2024, 2025]

SPORT_MAP = {
    11: 'AAA',
    12: 'AA',
    13: 'A+',
    14: 'A',
    15: 'Rk',
    16: 'FRk',
    586: 'FCL',
    5442: 'Complex'
}

async def collect_gamelogs_for_sport(session, season, sport_id, level_name):
    """Collect game logs for a specific sport level"""
    url = f"https://statsapi.mlb.com/api/v1/people/{BRYCE_ID}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'hitting',
        'season': season,
        'sportId': sport_id,
        'gameType': 'R'  # Regular season
    }

    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return []

            data = await resp.json()

            if not data.get('stats') or not data['stats'][0].get('splits'):
                return []

            splits = data['stats'][0]['splits']
            return splits

    except Exception as e:
        print(f"Error fetching {season} {level_name}: {e}")
        return []

def save_gamelog(cursor, game_split, season, level):
    """Save a single game log to database"""
    try:
        # Extract game info
        game_info = game_split.get('game', {})
        game_pk = game_info.get('gamePk')
        game_date = game_split.get('date')
        is_home = game_split.get('isHome')

        if not game_pk or not game_date:
            return False

        # Extract team info
        team = game_split.get('team', {})
        team_id = team.get('id')
        team_name = team.get('name')

        opponent = game_split.get('opponent', {})
        opponent_id = opponent.get('id')
        opponent_name = opponent.get('name')

        # Extract stats
        stat = game_split.get('stat', {})
        pa = stat.get('plateAppearances', 0)
        ab = stat.get('atBats', 0)
        hits = stat.get('hits', 0)
        runs = stat.get('runs', 0)
        doubles = stat.get('doubles', 0)
        triples = stat.get('triples', 0)
        hrs = stat.get('homeRuns', 0)
        rbi = stat.get('rbi', 0)
        bb = stat.get('baseOnBalls', 0)
        so = stat.get('strikeOuts', 0)
        sb = stat.get('stolenBases', 0)
        avg = stat.get('avg', '0.000')
        obp = stat.get('obp', '0.000')
        slg = stat.get('slg', '0.000')
        ops = stat.get('ops', '0.000')

        # Convert avg/obp/slg/ops to float
        def safe_float(val):
            if isinstance(val, str):
                if val.startswith('.') or val.startswith('-'):
                    return None
                try:
                    return float(val)
                except:
                    return None
            return val

        avg_num = safe_float(avg)
        obp_num = safe_float(obp)
        slg_num = safe_float(slg)
        ops_num = safe_float(ops)

        # Insert into database
        cursor.execute("""
            INSERT INTO milb_game_logs (
                mlb_player_id, season, game_pk, game_date, level,
                team_id, team, opponent_id, opponent, is_home,
                plate_appearances, at_bats, hits, runs, doubles,
                triples, home_runs, rbi, walks, strikeouts,
                stolen_bases, batting_avg, on_base_pct, slugging_pct, ops,
                data_source, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (game_pk, mlb_player_id)
            DO UPDATE SET
                updated_at = now(),
                batting_avg = EXCLUDED.batting_avg,
                ops = EXCLUDED.ops,
                level = EXCLUDED.level
        """, (
            BRYCE_ID, season, game_pk, game_date, level,
            team_id, team_name, opponent_id, opponent_name, is_home,
            pa, ab, hits, runs, doubles,
            triples, hrs, rbi, bb, so,
            sb, avg_num, obp_num, slg_num, ops_num,
            'mlb_stats_api', datetime.now()
        ))

        return True

    except Exception as e:
        print(f"    Error saving game {game_pk}: {e}")
        return False

async def main():
    print("="*80)
    print("COLLECTING ALL MILB GAME LOGS FOR BRYCE ELDRIDGE")
    print("="*80)
    print(f"\nPlayer: Bryce Eldridge (ID: {BRYCE_ID})")
    print(f"Seasons: {SEASONS}")
    print(f"\nUsing sportId parameter to query each level separately...")

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    total_saved = 0

    async with aiohttp.ClientSession() as session:
        for season in SEASONS:
            print(f"\n{'='*80}")
            print(f"SEASON {season}")
            print(f"{'='*80}")

            season_total = 0

            for sport_id, level_name in sorted(SPORT_MAP.items(), key=lambda x: x[0]):
                print(f"\n  Checking {level_name} (sportId={sport_id})...")

                splits = await collect_gamelogs_for_sport(session, season, sport_id, level_name)

                if splits:
                    print(f"    Found {len(splits)} games")

                    saved = 0
                    for split in splits:
                        if save_gamelog(cursor, split, season, level_name):
                            saved += 1

                    conn.commit()

                    print(f"    Saved {saved}/{len(splits)} games to database")
                    season_total += saved
                    total_saved += saved
                else:
                    print(f"    No games found")

                await asyncio.sleep(0.2)

            print(f"\n  Season {season} total: {season_total} games saved")

    # Print summary
    print("\n" + "="*80)
    print("COLLECTION COMPLETE")
    print("="*80)
    print(f"\nTotal games saved: {total_saved}")

    # Verify database
    print("\n" + "="*80)
    print("DATABASE VERIFICATION")
    print("="*80)

    cursor.execute("""
        SELECT season, level, COUNT(*) as games, SUM(plate_appearances) as total_pa
        FROM milb_game_logs
        WHERE mlb_player_id = %s
        GROUP BY season, level
        ORDER BY season DESC, level
    """, (BRYCE_ID,))

    results = cursor.fetchall()
    if results:
        print("\nBryce Eldridge game logs in database:")
        for row in results:
            season, level, games, pa = row
            print(f"  {season} {level:10} {games:3} games, {pa:4} PAs, ~{int(pa * 4.5):4} pitches expected")
    else:
        print("\nNo game logs found")

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
