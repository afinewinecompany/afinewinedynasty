import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                p.name,
                p.mlb_player_id,
                SUM(m.at_bats) as mlb_ab,
                SUM(m.plate_appearances) as mlb_pa
            FROM prospects p
            LEFT JOIN mlb_game_logs m ON p.mlb_player_id = m.mlb_player_id
            WHERE p.name IN ('John Hicks', 'Manuel Margot', 'Jesse Winker', 'Luke Maile', 'Derek Dietrich')
            GROUP BY p.name, p.mlb_player_id
            ORDER BY p.name
        """))

        print('\n=== MLB Service Time for Top-Ranked "Prospects" ===')
        for row in result:
            print(f'{row[0]}: {row[2] if row[2] else 0} AB, {row[3] if row[3] else 0} PA')

asyncio.run(check())
