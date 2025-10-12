import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT DISTINCT season
            FROM milb_game_logs
            ORDER BY season DESC
        """))

        print('\nAvailable MiLB seasons:')
        for row in result:
            print(f'  {row[0]}')

        # Check player counts by recent season
        result2 = await conn.execute(text("""
            SELECT season, COUNT(DISTINCT mlb_player_id) as players
            FROM milb_game_logs
            WHERE season >= 2023
            GROUP BY season
            ORDER BY season DESC
        """))

        print('\nPlayers by recent season:')
        for row in result2:
            print(f'  {row[0]}: {row[1]:,} players')

asyncio.run(check())
