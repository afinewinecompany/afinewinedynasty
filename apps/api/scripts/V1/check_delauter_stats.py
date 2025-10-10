"""
Check Chase DeLauter's 2025 stats from the database
"""
import asyncio
import asyncpg
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

# Make sure we're loading the env from the right place
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings


async def check_delauter_stats():
    """Check Chase DeLauter's stats in the database."""

    # Parse the connection string
    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Connect to database
    conn = await asyncpg.connect(db_url)

    try:
        print("=" * 80)
        print("CHASE DELAUTER - 2025 STATS CHECK")
        print("=" * 80)

        # First, find Chase DeLauter in prospects table
        print("\n1. Searching for Chase DeLauter in prospects table...")
        prospect = await conn.fetchrow(
            """
            SELECT id, mlb_id, name, position, organization, level, age
            FROM prospects
            WHERE LOWER(name) LIKE LOWER('%delauter%')
            LIMIT 1
            """
        )

        if not prospect:
            print("   No prospect found with name 'DeLauter'")
            print("\n   Searching by partial match...")
            all_delauters = await conn.fetch(
                """
                SELECT id, mlb_id, name, position, organization, level
                FROM prospects
                WHERE LOWER(name) LIKE '%dela%'
                OR LOWER(name) LIKE '%lauter%'
                """
            )
            if all_delauters:
                print(f"\n   Found {len(all_delauters)} similar names:")
                for p in all_delauters:
                    print(f"   - {p['name']} (ID: {p['mlb_id']}, Org: {p['organization']})")
            else:
                print("   No similar names found")

            # Try to search directly in game logs by name pattern
            print("\n2. Searching game logs for DeLauter...")
            logs_by_name = await conn.fetch(
                """
                SELECT DISTINCT gl.mlb_player_id, COUNT(*) as game_count
                FROM milb_game_logs gl
                WHERE gl.season = 2025
                GROUP BY gl.mlb_player_id
                LIMIT 20
                """
            )
            print(f"   Found {len(logs_by_name)} players with 2025 game logs")
            return

        print(f"\n   Found: {prospect['name']}")
        print(f"     MLB ID: {prospect['mlb_id']}")
        print(f"     Position: {prospect['position']}")
        print(f"     Organization: {prospect['organization']}")
        print(f"     Level: {prospect['level']}")

        mlb_player_id = int(prospect['mlb_id'])

        # Check for 2025 game logs
        print("\n2. Checking 2025 game logs...")
        logs_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM milb_game_logs
            WHERE mlb_player_id = $1 AND season = 2025
            """,
            mlb_player_id
        )

        print(f"   Found {logs_count} game logs for 2025 season")

        if logs_count == 0:
            # Check other seasons
            print("\n3. Checking other seasons...")
            all_seasons = await conn.fetch(
                """
                SELECT season, COUNT(*) as game_count
                FROM milb_game_logs
                WHERE mlb_player_id = $1
                GROUP BY season
                ORDER BY season DESC
                """,
                mlb_player_id
            )

            if all_seasons:
                print(f"   Found data in {len(all_seasons)} other seasons:")
                for row in all_seasons:
                    print(f"   - {row['season']}: {row['game_count']} games")
            else:
                print("   No game logs found in any season")
            return

        # Get 2025 season totals
        print("\n3. 2025 Season Totals:")
        print("-" * 80)

        # Hitting stats
        hitting_totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as games,
                SUM(at_bats) as ab,
                SUM(hits) as h,
                SUM(doubles) as doubles,
                SUM(triples) as triples,
                SUM(home_runs) as hr,
                SUM(rbi) as rbi,
                SUM(runs) as r,
                SUM(walks) as bb,
                SUM(strikeouts) as so,
                SUM(stolen_bases) as sb,
                SUM(caught_stealing) as cs,
                ROUND(AVG(batting_avg)::numeric, 3) as avg,
                ROUND(AVG(on_base_pct)::numeric, 3) as obp,
                ROUND(AVG(slugging_pct)::numeric, 3) as slg,
                ROUND(AVG(ops)::numeric, 3) as ops
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
                AND at_bats > 0
            """,
            mlb_player_id
        )

        if hitting_totals and hitting_totals['games']:
            print("\n   HITTING STATS:")
            print(f"   Games:     {hitting_totals['games']}")
            print(f"   AB:        {hitting_totals['ab']}")
            print(f"   H:         {hitting_totals['h']}")
            print(f"   2B:        {hitting_totals['doubles']}")
            print(f"   3B:        {hitting_totals['triples']}")
            print(f"   HR:        {hitting_totals['hr']}")
            print(f"   RBI:       {hitting_totals['rbi']}")
            print(f"   R:         {hitting_totals['r']}")
            print(f"   BB:        {hitting_totals['bb']}")
            print(f"   SO:        {hitting_totals['so']}")
            print(f"   SB:        {hitting_totals['sb']}")
            print(f"   CS:        {hitting_totals['cs']}")
            # Calculate actual averages from totals
            avg = hitting_totals['h'] / hitting_totals['ab'] if hitting_totals['ab'] > 0 else 0
            obp = (hitting_totals['h'] + hitting_totals['bb'] + hitting_totals.get('hbp', 0)) / \
                  (hitting_totals['ab'] + hitting_totals['bb'] + hitting_totals.get('hbp', 0)) \
                  if (hitting_totals['ab'] + hitting_totals['bb']) > 0 else 0
            total_bases = hitting_totals['h'] + hitting_totals['doubles'] + \
                         (hitting_totals['triples'] * 2) + (hitting_totals['hr'] * 3)
            slg = total_bases / hitting_totals['ab'] if hitting_totals['ab'] > 0 else 0
            ops_calc = obp + slg

            print(f"   AVG:       {avg:.3f}")
            print(f"   OBP:       {obp:.3f}")
            print(f"   SLG:       {slg:.3f}")
            print(f"   OPS:       {ops_calc:.3f}")

        # Pitching stats (in case he pitched)
        pitching_totals = await conn.fetchrow(
            """
            SELECT
                COUNT(*) as games,
                SUM(innings_pitched) as ip,
                SUM(wins) as w,
                SUM(losses) as l,
                SUM(saves) as sv,
                SUM(hits_allowed) as h,
                SUM(runs_allowed) as r,
                SUM(earned_runs) as er,
                SUM(walks_allowed) as bb,
                SUM(strikeouts_pitched) as so,
                SUM(home_runs_allowed) as hr,
                ROUND(AVG(era)::numeric, 2) as era,
                ROUND(AVG(whip)::numeric, 2) as whip
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
                AND innings_pitched > 0
            """,
            mlb_player_id
        )

        if pitching_totals and pitching_totals['games']:
            print("\n   PITCHING STATS:")
            print(f"   Games:     {pitching_totals['games']}")
            print(f"   IP:        {pitching_totals['ip']}")
            print(f"   W-L:       {pitching_totals['w']}-{pitching_totals['l']}")
            print(f"   SV:        {pitching_totals['sv']}")
            print(f"   H:         {pitching_totals['h']}")
            print(f"   R:         {pitching_totals['r']}")
            print(f"   ER:        {pitching_totals['er']}")
            print(f"   BB:        {pitching_totals['bb']}")
            print(f"   SO:        {pitching_totals['so']}")
            print(f"   HR:        {pitching_totals['hr']}")
            print(f"   ERA:       {pitching_totals['era']}")
            print(f"   WHIP:      {pitching_totals['whip']}")

        # Show sample of recent games
        print("\n4. Most Recent Games (Last 10):")
        print("-" * 80)

        recent_games = await conn.fetch(
            """
            SELECT
                game_date,
                at_bats,
                hits,
                doubles,
                triples,
                home_runs,
                rbi,
                walks,
                strikeouts,
                stolen_bases,
                batting_avg
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
                AND at_bats > 0
            ORDER BY game_date DESC
            LIMIT 10
            """,
            mlb_player_id
        )

        if recent_games:
            print("\n   Date       | AB | H | 2B | 3B | HR | RBI | BB | SO | SB | AVG")
            print("   " + "-" * 70)
            for game in recent_games:
                avg_val = game['batting_avg'] if game['batting_avg'] is not None else 0.0
                print(f"   {game['game_date']} | {game['at_bats']:2} | {game['hits']:2} | "
                          f"{game['doubles']:2} | {game['triples']:2} | {game['home_runs']:2} | "
                          f"{game['rbi']:3} | {game['walks']:2} | {game['strikeouts']:2} | "
                          f"{game['stolen_bases']:2} | {avg_val:.3f}")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_delauter_stats())