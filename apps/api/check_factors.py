import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        # Check league factors
        result = await conn.execute(text('''
            SELECT season, level, lg_ops, lg_avg_age, lg_median_age
            FROM milb_league_factors
            ORDER BY season DESC, level
        '''))
        print('\n=== LEAGUE FACTORS ===')
        for row in result:
            print(f'{row[0]} {row[1]:3s} - OPS: {row[2]:.3f}, Avg Age: {row[3]:.1f}, Med Age: {row[4]:.1f}')

        # Check position factors
        result = await conn.execute(text('''
            SELECT season, level, position_group, pos_ops, pos_avg_age, unique_players
            FROM milb_position_factors
            WHERE season = 2024
            ORDER BY level, position_group
        '''))
        print('\n=== POSITION FACTORS (2024) ===')
        for row in result:
            print(f'{row[1]:3s} {row[2]:2s} - OPS: {row[3]:.3f}, Age: {row[4]:.1f}, Players: {row[5]}')

asyncio.run(check())
