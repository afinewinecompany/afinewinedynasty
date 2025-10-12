import asyncio
from sqlalchemy import text
from app.db.database import engine

async def check():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'prospects' ORDER BY ordinal_position"))
        cols = [r[0] for r in result]
        print('\n'.join(cols))

asyncio.run(check())
