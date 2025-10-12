"""
Check Chase DeLauter's stats across ALL levels and seasons
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


async def check_delauter_all_levels():
    """Check Chase DeLauter's stats across all levels and seasons."""

    # Parse the connection string
    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Connect to database
    conn = await asyncpg.connect(db_url)

    try:
        print("=" * 80)
        print("CHASE DELAUTER - COMPLETE CAREER STATS CHECK")
        print("=" * 80)

        # Find Chase DeLauter
        prospect = await conn.fetchrow(
            """
            SELECT id, mlb_id, name, position, organization, level, age
            FROM prospects
            WHERE LOWER(name) LIKE LOWER('%delauter%')
            LIMIT 1
            """
        )

        if not prospect:
            print("No prospect found with name 'DeLauter'")
            return

        print(f"\nPlayer: {prospect['name']}")
        print(f"MLB ID: {prospect['mlb_id']}")
        print(f"Position: {prospect['position']}")
        print(f"Organization: {prospect['organization']}")
        print("-" * 80)

        mlb_player_id = int(prospect['mlb_id'])

        # Get breakdown by season and level
        print("\n1. CAREER BREAKDOWN BY SEASON AND LEVEL:")
        print("-" * 80)

        season_level_breakdown = await conn.fetch(
            """
            SELECT
                season,
                level,
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
                SUM(stolen_bases) as sb
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND at_bats > 0
            GROUP BY season, level
            ORDER BY season DESC, level
            """,
            mlb_player_id
        )

        if season_level_breakdown:
            print(f"\n{'Season':<8} {'Level':<15} {'G':>4} {'AB':>5} {'H':>4} {'2B':>3} {'3B':>3} {'HR':>3} {'RBI':>4} {'R':>4} {'BB':>3} {'SO':>3} {'SB':>3}")
            print("-" * 80)

            total_games = 0
            total_ab = 0
            total_h = 0

            for row in season_level_breakdown:
                season = row['season']
                level = row['level'] or 'Unknown'
                games = row['games']
                ab = row['ab'] or 0
                h = row['h'] or 0
                doubles = row['doubles'] or 0
                triples = row['triples'] or 0
                hr = row['hr'] or 0
                rbi = row['rbi'] or 0
                r = row['r'] or 0
                bb = row['bb'] or 0
                so = row['so'] or 0
                sb = row['sb'] or 0

                avg = h / ab if ab > 0 else 0

                print(f"{season:<8} {level:<15} {games:>4} {ab:>5} {h:>4} {doubles:>3} {triples:>3} {hr:>3} {rbi:>4} {r:>4} {bb:>3} {so:>3} {sb:>3}  .{int(avg*1000):03d}")

                total_games += games
                total_ab += ab
                total_h += h

            print("-" * 80)
            total_avg = total_h / total_ab if total_ab > 0 else 0
            print(f"TOTAL: {total_games} games, {total_ab} AB, {total_h} H, .{int(total_avg*1000):03d} AVG")

        else:
            print("No stats found in database")
            return

        # Check what we might be missing
        print("\n2. DATA COMPLETENESS CHECK:")
        print("-" * 80)

        # Check for any level = NULL entries
        null_level_count = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND level IS NULL
            """,
            mlb_player_id
        )

        print(f"Records with NULL level: {null_level_count}")

        # Check date ranges
        date_ranges = await conn.fetch(
            """
            SELECT
                season,
                level,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game,
                COUNT(DISTINCT game_date) as unique_dates
            FROM milb_game_logs
            WHERE mlb_player_id = $1
            GROUP BY season, level
            ORDER BY season DESC, level
            """,
            mlb_player_id
        )

        print("\nDate Ranges by Season/Level:")
        for row in date_ranges:
            print(f"  {row['season']} {row['level'] or 'Unknown':15} {row['first_game']} to {row['last_game']} ({row['unique_dates']} unique dates)")

        # Check for data source
        data_sources = await conn.fetch(
            """
            SELECT
                data_source,
                COUNT(*) as count
            FROM milb_game_logs
            WHERE mlb_player_id = $1
            GROUP BY data_source
            """,
            mlb_player_id
        )

        print("\nData Sources:")
        for row in data_sources:
            print(f"  {row['data_source']}: {row['count']} records")

        # Check total records
        total_records = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM milb_game_logs
            WHERE mlb_player_id = $1
            """,
            mlb_player_id
        )

        print(f"\nTotal database records: {total_records}")

        # Now use MLB StatsAPI to check what SHOULD exist
        print("\n3. CHECKING MLB STATS API FOR MISSING DATA:")
        print("-" * 80)

        import statsapi

        print(f"\nQuerying MLB Stats API for player {mlb_player_id}...")

        # Check 2024 and 2025 seasons
        for season in [2024, 2025]:
            try:
                # Try to get game logs
                stats = statsapi.get(
                    f'people/{mlb_player_id}/stats',
                    {
                        'stats': 'gameLog',
                        'season': season,
                        'group': 'hitting',
                        'gameType': 'R'
                    }
                )

                game_count = 0
                for stat_group in stats.get('stats', []):
                    if stat_group.get('type', {}).get('displayName') == 'gameLog':
                        splits = stat_group.get('splits', [])
                        game_count = len(splits)

                        if splits:
                            print(f"\n{season} Season - {game_count} games found in API:")

                            # Check what levels are represented
                            levels_in_api = {}
                            for split in splits:
                                team = split.get('team', {}).get('name', 'Unknown')
                                if team not in levels_in_api:
                                    levels_in_api[team] = 0
                                levels_in_api[team] += 1

                            for team, count in levels_in_api.items():
                                print(f"  {team}: {count} games")

                            # Compare with database
                            db_count = await conn.fetchval(
                                """
                                SELECT COUNT(*)
                                FROM milb_game_logs
                                WHERE mlb_player_id = $1
                                    AND season = $2
                                """,
                                mlb_player_id,
                                season
                            )

                            print(f"\n  API has {game_count} games, Database has {db_count} games")
                            if game_count > db_count:
                                print(f"  MISSING {game_count - db_count} games in database!")
                        else:
                            print(f"\n{season} Season - No games found in API")

            except Exception as e:
                print(f"Error checking {season}: {e}")

        print("\n" + "=" * 80)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_delauter_all_levels())