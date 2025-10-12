"""Quick check of 2025 MiLB data collection status"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check_status():
    async with engine.begin() as conn:
        # Overall 2025 stats
        result = await conn.execute(text("""
            SELECT
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as total_games,
                COUNT(CASE WHEN games_played > 0 THEN 1 END) as hitting_games,
                COUNT(CASE WHEN games_pitched > 0 THEN 1 END) as pitching_games,
                MIN(game_date) as first_game,
                MAX(game_date) as last_game,
                MAX(created_at) as last_inserted
            FROM milb_game_logs
            WHERE season = 2025 AND mlb_player_id IS NOT NULL
        """))
        row = result.fetchone()

        print("="*70)
        print("2025 MiLB DATA COLLECTION STATUS")
        print("="*70)
        print(f"Unique Players:     {row[0]:,}")
        print(f"Total Game Records: {row[1]:,}")
        print(f"  Hitting Games:    {row[2]:,}")
        print(f"  Pitching Games:   {row[3]:,}")
        print(f"Date Range:         {row[4]} to {row[5]}")
        print(f"Last Inserted:      {row[6]}")
        print()

        # Check by level
        result = await conn.execute(text("""
            SELECT
                level,
                COUNT(DISTINCT mlb_player_id) as players,
                COUNT(*) as games
            FROM milb_game_logs
            WHERE season = 2025 AND mlb_player_id IS NOT NULL
            GROUP BY level
            ORDER BY
                CASE level
                    WHEN 'AAA' THEN 1
                    WHEN 'AA' THEN 2
                    WHEN 'A+' THEN 3
                    WHEN 'A' THEN 4
                    ELSE 5
                END
        """))

        print("By Level:")
        print("-" * 40)
        print(f"{'Level':<10} {'Players':<15} {'Games':<10}")
        print("-" * 40)
        for row in result:
            print(f"{row[0]:<10} {row[1]:<15,} {row[2]:<10,}")
        print()

        # Check data source
        result = await conn.execute(text("""
            SELECT
                data_source,
                COUNT(*) as count
            FROM milb_game_logs
            WHERE season = 2025
            GROUP BY data_source
        """))

        print("By Data Source:")
        print("-" * 40)
        for row in result:
            print(f"{row[0]}: {row[1]:,} records")
        print()

        # Check if there are any NULL player IDs (the issue)
        result = await conn.execute(text("""
            SELECT COUNT(*) as null_player_count
            FROM milb_game_logs
            WHERE season = 2025 AND mlb_player_id IS NULL
        """))
        null_count = result.fetchone()[0]

        if null_count > 0:
            print("⚠️  WARNING:")
            print(f"   {null_count:,} records have NULL mlb_player_id")
            print("   These records were likely deleted or need collection")
            print()


if __name__ == "__main__":
    asyncio.run(check_status())
