"""
Deep dive into DeLauter's data to find ALL games including any potential rookie ball
"""
import asyncio
import asyncpg
from pathlib import Path
import sys
import os

sys.path.append(str(Path(__file__).parent.parent.parent))
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

async def deep_dive():
    """Deep dive into all DeLauter data."""

    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    try:
        mlb_id = 800050

        print("=" * 80)
        print("CHASE DELAUTER - DEEP DIVE INTO ALL DATABASE RECORDS")
        print("=" * 80)

        # Get ALL records for DeLauter, grouped by every possible field combination
        print("\n1. ALL UNIQUE COMBINATIONS:")
        combinations = await conn.fetch(
            """
            SELECT
                season,
                level,
                team,
                data_source,
                game_type,
                COUNT(*) as games,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game
            FROM milb_game_logs
            WHERE mlb_player_id = $1
            GROUP BY season, level, team, data_source, game_type
            ORDER BY season DESC, first_game DESC
            """,
            mlb_id
        )

        print(f"\n{'Season':<8} {'Level':<12} {'Team':<25} {'Source':<25} {'Type':<10} {'Games':>5} {'First':<12} {'Last':<12}")
        print("-" * 130)

        for row in combinations:
            print(f"{row['season']:<8} {(row['level'] or 'NULL'):<12} {(row['team'] or 'NULL'):<25} "
                  f"{(row['data_source'] or 'NULL'):<25} {(row['game_type'] or 'NULL'):<10} "
                  f"{row['games']:>5} {str(row['first_game']):<12} {str(row['last_game']):<12}")

        # Check for 2024 specifically - look for any games that might be "rehab" or special
        print("\n\n2. ALL 2024 GAMES IN DETAIL (showing team info):")
        print("-" * 80)
        games_2024 = await conn.fetch(
            """
            SELECT
                game_date,
                level,
                team,
                opponent,
                data_source,
                game_type,
                at_bats,
                hits,
                home_runs
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2024
            ORDER BY game_date
            """,
            mlb_id
        )

        print(f"{'Date':<12} {'Level':<10} {'Team':<20} {'Opponent':<20} {'Source':<20} {'Type':<8} {'AB':>3} {'H':>3} {'HR':>3}")
        print("-" * 120)
        for game in games_2024:
            print(f"{str(game['game_date']):<12} {(game['level'] or 'N/A'):<10} {(game['team'] or 'N/A'):<20} "
                  f"{(game['opponent'] or 'N/A'):<20} {(game['data_source'] or 'N/A'):<20} "
                  f"{(game['game_type'] or 'N/A'):<8} {game['at_bats']:>3} {game['hits']:>3} {game['home_runs']:>3}")

        #Check total 2024 count
        total_2024 = len(games_2024)
        print(f"\nTotal 2024 games in database: {total_2024}")

        # Check if there are duplicates
        print("\n\n3. CHECKING FOR DUPLICATE GAMES:")
        duplicates = await conn.fetch(
            """
            SELECT
                game_pk,
                game_date,
                COUNT(*) as count
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2024
            GROUP BY game_pk, game_date
            HAVING COUNT(*) > 1
            ORDER BY game_date
            """,
            mlb_id
        )

        if duplicates:
            print(f"Found {len(duplicates)} duplicate games:")
            for dup in duplicates:
                print(f"  {dup['game_date']}: game_pk {dup['game_pk']} appears {dup['count']} times")
        else:
            print("No duplicates found")

        # Count unique game_dates
        unique_dates = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT game_date)
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2024
                AND game_date IS NOT NULL
            """,
            mlb_id
        )

        print(f"\nUnique game dates in 2024: {unique_dates}")

        print("\n" + "=" * 80)
        print("ANALYSIS:")
        print("-" * 80)
        print(f"According to our earlier check, DeLauter has:")
        print(f"  - 72 total game logs for 2024 in database")
        print(f"  - {unique_dates} unique game dates")
        print(f"  - This suggests some duplicate entries (same game, different source)")
        print(f"\nIf he truly played 8 rookie ball games, they may:")
        print(f"  1. Be in the database but not labeled as 'Rookie'")
        print(f"  2. Not be available via MLB Stats API")
        print(f"  3. Be spring training or other special games")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(deep_dive())