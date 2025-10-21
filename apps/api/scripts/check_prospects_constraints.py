"""Check constraints on prospects table"""
import asyncio
import asyncpg

async def check_constraints():
    conn = await asyncpg.connect(
        host="nozomi.proxy.rlwy.net",
        port=39235,
        user="postgres",
        password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp",
        database="railway"
    )

    # Get constraints
    constraints = await conn.fetch("""
        SELECT constraint_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_name = 'prospects'
    """)

    print("Constraints on prospects table:")
    for c in constraints:
        print(f"  {c['constraint_name']}: {c['constraint_type']}")

    # Get indexes
    indexes = await conn.fetch("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'prospects'
    """)

    print("\nIndexes on prospects table:")
    for idx in indexes:
        print(f"  {idx['indexname']}")
        print(f"    {idx['indexdef']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_constraints())
