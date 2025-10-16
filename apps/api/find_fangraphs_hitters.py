"""Find FanGraphs hitter grades table"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check():
    async with engine.begin() as conn:
        # Check all FanGraphs tables
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE '%fang%'
        """))
        tables = [row[0] for row in result.fetchall()]

        print("=" * 80)
        print("FANGRAPHS TABLES")
        print("=" * 80)

        for table in tables:
            print(f"\n{table}:")

            # Get count
            count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = count_result.scalar()
            print(f"  Rows: {count:,}")

            # Get columns
            cols_result = await conn.execute(text(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
            """))
            cols = [row[0] for row in cols_result.fetchall()]
            print(f"  Columns ({len(cols)}): {', '.join(cols[:15])}")

            # Check for hitter vs pitcher indicators
            if 'hit' in ' '.join(cols).lower() or 'bat' in ' '.join(cols).lower():
                print("  Type: HITTER grades (has 'hit' or 'bat' columns)")
            elif 'fb' in ' '.join(cols).lower() or 'fastball' in ' '.join(cols).lower():
                print("  Type: PITCHER grades (has 'fb' or 'fastball' columns)")

if __name__ == "__main__":
    asyncio.run(check())
