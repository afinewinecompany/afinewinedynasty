import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text('SELECT DISTINCT game_type FROM milb_game_logs LIMIT 10'))
        types = [row[0] for row in result]
        print(f"Existing game_type values: {types}")

asyncio.run(check())
