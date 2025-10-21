import asyncio
import asyncpg

async def check_tables():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    # Check for FanGraphs tables
    tables = await conn.fetch("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename LIKE '%fangraphs%'
        ORDER BY tablename
    """)

    print("FanGraphs tables in production:")
    if tables:
        for row in tables:
            print(f"  [OK] {row['tablename']}")
    else:
        print("  [ERROR] NO FANGRAPHS TABLES FOUND!")

    print("\nAll tables in production:")
    all_tables = await conn.fetch("""
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    for row in all_tables:
        print(f"  - {row['tablename']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tables())
