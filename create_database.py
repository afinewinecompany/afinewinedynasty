"""Create database if it doesn't exist."""
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

load_dotenv('apps/api/.env')

async def create_db():
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_SERVER', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        database='postgres'
    )

    db_name = os.getenv('POSTGRES_DB', 'afinewinedynasty')
    result = await conn.fetchval('SELECT 1 FROM pg_database WHERE datname = $1', db_name)

    if result:
        print(f'Database "{db_name}" already exists')
    else:
        await conn.execute(f'CREATE DATABASE {db_name}')
        print(f'Database "{db_name}" created successfully')

    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_db())
