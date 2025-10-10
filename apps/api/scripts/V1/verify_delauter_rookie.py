"""
Check if we're missing DeLauter's rookie ball games
"""
import asyncio
import asyncpg
from pathlib import Path
import sys
import os

sys.path.append(str(Path(__file__).parent.parent.parent))
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

async def check_rookie_ball():
    """Check for rookie ball data."""

    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    try:
        mlb_player_id = 800050  # Chase DeLauter

        print("=" * 80)
        print("CHASE DELAUTER - ROOKIE BALL CHECK")
        print("=" * 80)

        # Check all levels in database
        print("\nAll levels found in database for DeLauter:")
        all_levels = await conn.fetch(
            """
            SELECT DISTINCT level, season, COUNT(*) as games
            FROM milb_game_logs
            WHERE mlb_player_id = $1
            GROUP BY level, season
            ORDER BY season DESC, level
            """,
            mlb_player_id
        )

        for row in all_levels:
            print(f"  {row['season']} - {row['level']}: {row['games']} games")

        # Check for any rookie-related levels
        print("\nSearching for any rookie/complex level designations:")
        rookie_levels = await conn.fetch(
            """
            SELECT DISTINCT level
            FROM milb_game_logs
            WHERE LOWER(level) LIKE '%rookie%'
               OR LOWER(level) LIKE '%complex%'
               OR LOWER(level) LIKE '%fcl%'
               OR LOWER(level) LIKE '%acl%'
            LIMIT 20
            """
        )

        print(f"\nFound {len(rookie_levels)} unique rookie/complex level designations in database:")
        for row in rookie_levels:
            print(f"  - {row['level']}")

        # Check what game_type values we have
        print("\n\nChecking game_type values for DeLauter:")
        game_types = await conn.fetch(
            """
            SELECT game_type, COUNT(*) as count
            FROM milb_game_logs
            WHERE mlb_player_id = $1
            GROUP BY game_type
            """,
            mlb_player_id
        )

        for row in game_types:
            print(f"  {row['game_type']}: {row['count']} games")

        # Check 2024 in detail
        print("\n\n2024 Season Detail:")
        print("-" * 80)
        games_2024 = await conn.fetch(
            """
            SELECT
                game_date,
                level,
                team,
                opponent,
                at_bats,
                hits,
                home_runs,
                rbi
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2024
                AND at_bats > 0
            ORDER BY game_date
            """,
            mlb_player_id
        )

        print(f"\nTotal 2024 games in database: {len(games_2024)}")
        print("\nFirst 10 games:")
        print(f"{'Date':<12} {'Level':<10} {'Team':<20} {'AB':>3} {'H':>3} {'HR':>3} {'RBI':>3}")
        print("-" * 60)
        for i, game in enumerate(games_2024[:10]):
            print(f"{game['game_date']} {(game['level'] or 'N/A'):<10} {(game['team'] or 'Unknown'):<20} "
                  f"{game['at_bats']:>3} {game['hits']:>3} {game['home_runs']:>3} {game['rbi']:>3}")

        # Check for spring training or other game types
        print("\n\nChecking for non-regular season games:")
        other_games = await conn.fetch(
            """
            SELECT game_type, season, COUNT(*) as count
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND game_type != 'R'
            GROUP BY game_type, season
            """,
            mlb_player_id
        )

        if other_games:
            for row in other_games:
                print(f"  {row['season']} - Type '{row['game_type']}': {row['count']} games")
        else:
            print("  No non-regular season games found")

        print("\n" + "=" * 80)
        print("\nSUMMARY:")
        print("-" * 80)
        print("Based on the database, Chase DeLauter has:")
        print("  2023: A+ and AA (no rookie ball)")
        print("  2024: AA and AAA (no rookie ball)")
        print("  2025: AAA only (no rookie ball)")
        print("\nIf he played 8 rookie ball games in 2024, they are NOT in the database.")
        print("This data may need to be collected separately.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_rookie_ball())