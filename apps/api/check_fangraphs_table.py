"""Check if FanGraphs data exists."""
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '.')
from app.db.database import engine

async def main():
    async with engine.connect() as conn:
        # Check for tables
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema='public'
            AND table_name LIKE '%fangraphs%'
        """))
        tables = [row[0] for row in result]
        print('FanGraphs tables:', tables if tables else 'None found')

        # If table exists, check row count
        if tables:
            for table in tables:
                result = await conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
                count = result.scalar()
                print(f'  {table}: {count} rows')

                # Sample data
                result = await conn.execute(text(f'SELECT * FROM {table} LIMIT 3'))
                print(f'  Sample columns: {result.keys()}')

asyncio.run(main())
