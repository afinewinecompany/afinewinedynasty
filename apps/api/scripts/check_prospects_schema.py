#!/usr/bin/env python3
"""Quick check of prospects table schema"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def check_schema():
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway")
    conn = await asyncpg.connect(DATABASE_URL)

    # Get columns
    columns = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'prospects'
        ORDER BY ordinal_position
    """)

    print("Prospects table columns:")
    print("="*60)
    for col in columns:
        print(f"{col['column_name']:30s} {col['data_type']}")

    # Check for birth_date
    has_birth_date = any(col['column_name'] == 'birth_date' for col in columns)
    print("\n" + "="*60)
    if has_birth_date:
        print("[OK] birth_date column EXISTS in prospects table")

        # Check how many have birth dates
        count = await conn.fetchrow("""
            SELECT
                COUNT(*) as total,
                COUNT(birth_date) as with_birth_date
            FROM prospects
        """)
        print(f"Total prospects: {count['total']:,}")
        print(f"With birth_date: {count['with_birth_date']:,}")
        print(f"Coverage: {count['with_birth_date']/count['total']*100:.1f}%")
    else:
        print("[INFO] birth_date column DOES NOT exist in prospects table")
        print("[ACTION] We should add birth_date column or use a separate table")

    await conn.close()

asyncio.run(check_schema())
