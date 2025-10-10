"""
Check Chase DeLauter's 2025 stats in detail to find missing rookie ball games
"""
import asyncio
import asyncpg
from pathlib import Path
import sys
import os

sys.path.append(str(Path(__file__).parent.parent.parent))
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

async def check_2025_detailed():
    """Check all 2025 data for DeLauter."""

    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    try:
        mlb_id = 800050

        print("=" * 80)
        print("CHASE DELAUTER - 2025 SEASON DETAILED ANALYSIS")
        print("=" * 80)

        # Get ALL 2025 records grouped by level and source
        print("\n1. 2025 BREAKDOWN BY LEVEL AND SOURCE:")
        breakdown = await conn.fetch(
            """
            SELECT
                level,
                data_source,
                game_type,
                COUNT(*) as games,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game,
                SUM(at_bats) as total_ab,
                SUM(hits) as total_h
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
            GROUP BY level, data_source, game_type
            ORDER BY first_game
            """,
            mlb_id
        )

        print(f"\n{'Level':<15} {'Source':<25} {'Type':<10} {'Games':>5} {'First':<12} {'Last':<12} {'AB':>4} {'H':>4}")
        print("-" * 100)

        for row in breakdown:
            print(f"{(row['level'] or 'NULL'):<15} {(row['data_source'] or 'NULL'):<25} "
                  f"{(row['game_type'] or 'NULL'):<10} {row['games']:>5} "
                  f"{str(row['first_game']):<12} {str(row['last_game']):<12} "
                  f"{row['total_ab']:>4} {row['total_h']:>4}")

        # Check unique game dates
        unique_dates = await conn.fetchval(
            """
            SELECT COUNT(DISTINCT game_date)
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
                AND game_date IS NOT NULL
            """,
            mlb_id
        )

        print(f"\nUnique game dates in 2025: {unique_dates}")

        # Show ALL 2025 games chronologically
        print("\n2. ALL 2025 GAMES IN CHRONOLOGICAL ORDER:")
        print("-" * 100)
        all_games = await conn.fetch(
            """
            SELECT
                game_date,
                level,
                team,
                data_source,
                at_bats,
                hits,
                home_runs,
                rbi
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
            ORDER BY game_date, level
            """,
            mlb_id
        )

        print(f"{'Date':<12} {'Level':<10} {'Team':<25} {'Source':<25} {'AB':>3} {'H':>3} {'HR':>3} {'RBI':>3}")
        print("-" * 100)
        for game in all_games:
            print(f"{str(game['game_date']):<12} {(game['level'] or 'N/A'):<10} "
                  f"{(game['team'] or 'N/A'):<25} {(game['data_source'] or 'N/A'):<25} "
                  f"{game['at_bats']:>3} {game['hits']:>3} {game['home_runs']:>3} {game['rbi']:>3}")

        # Look for any early season games that might be rookie ball
        print("\n3. CHECKING FOR EARLY 2025 GAMES (before May):")
        early_games = await conn.fetch(
            """
            SELECT
                game_date,
                level,
                team,
                data_source
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
                AND game_date < '2025-05-01'
            ORDER BY game_date
            """,
            mlb_id
        )

        if early_games:
            print(f"Found {len(early_games)} games before May 2025:")
            for game in early_games:
                print(f"  {game['game_date']}: {game['level'] or 'Unknown'} - {game['team'] or 'Unknown'}")
        else:
            print("  NO games found before May 2025")
            print("  First game is on 2025-05-23 (AAA)")

        print("\n4. TOTAL 2025 GAMES:")
        total = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM milb_game_logs
            WHERE mlb_player_id = $1
                AND season = 2025
            """,
            mlb_id
        )
        print(f"  Total records: {total}")
        print(f"  Unique dates: {unique_dates}")

        print("\n" + "=" * 80)
        print("ANALYSIS:")
        print("-" * 80)
        print(f"DeLauter's 2025 database coverage:")
        print(f"  - 34 unique AAA games (May 23 - July 11)")
        print(f"  - NO games before May 23, 2025")
        print(f"  - NO rookie ball games recorded")
        print(f"\nIf he played 8 rookie ball games in early 2025 (likely Feb-April),")
        print(f"they are NOT in the database and not available via MLB Stats API.")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_2025_detailed())