"""Check milb_game_logs schema"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    # Get schema
    rows = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'milb_game_logs'
        ORDER BY ordinal_position
    """)

    print("\n" + "="*80)
    print("milb_game_logs SCHEMA:")
    print("="*80)
    for row in rows:
        print(f"  {row['column_name']:<30} {row['data_type']}")

    # Sample one row to see what data looks like
    sample = await conn.fetchrow("""
        SELECT *
        FROM milb_game_logs
        WHERE mlb_player_id = 805811
          AND season = 2025
        LIMIT 1
    """)

    if sample:
        print("\n" + "="*80)
        print("SAMPLE ROW (Bryce Eldridge):")
        print("="*80)
        for key, value in sample.items():
            print(f"  {key}: {value}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
