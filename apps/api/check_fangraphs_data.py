import asyncio
import asyncpg

async def check_data():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    hitter_count = await conn.fetchval("SELECT COUNT(*) FROM fangraphs_hitter_grades")
    pitcher_count = await conn.fetchval("SELECT COUNT(*) FROM fangraphs_pitcher_grades")

    print(f"Hitter grades: {hitter_count}")
    print(f"Pitcher grades: {pitcher_count}")

    if hitter_count > 0:
        sample = await conn.fetch("SELECT name, position, fv FROM fangraphs_hitter_grades LIMIT 5")
        print("\nSample hitters:")
        for row in sample:
            print(f"  {row['name']} ({row['position']}) - FV: {row['fv']}")

    if pitcher_count > 0:
        sample = await conn.fetch("SELECT name, position, fv FROM fangraphs_pitcher_grades LIMIT 5")
        print("\nSample pitchers:")
        for row in sample:
            print(f"  {row['name']} ({row['position']}) - FV: {row['fv']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_data())
