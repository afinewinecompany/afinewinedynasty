#!/usr/bin/env python3
"""Quick script to check actual column names in milb_game_logs"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_columns():
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
    conn = await asyncpg.connect(DATABASE_URL)

    # Get column names
    columns = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'milb_game_logs'
        ORDER BY ordinal_position
    """)

    print("Columns in milb_game_logs:")
    print("="*60)
    for col in columns:
        print(f"{col['column_name']:40s} {col['data_type']}")

    await conn.close()

asyncio.run(check_columns())
