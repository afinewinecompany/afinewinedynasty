"""Check for play-by-play tables"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check():
    async with engine.begin() as conn:
        # Check for PBP tables
        result = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND (table_name LIKE '%pbp%' OR table_name LIKE '%play_by_play%' OR table_name LIKE '%statcast%')
        """))
        tables = [row[0] for row in result.fetchall()]

        if not tables:
            print("No play-by-play or Statcast tables found")
            return

        print("Found tables:")
        for table in tables:
            print(f"  - {table}")

            # Get row count
            count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = count_result.scalar()
            print(f"    Rows: {count:,}")

            # Get column names
            cols_result = await conn.execute(text(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table}'
                ORDER BY ordinal_position
                LIMIT 10
            """))
            cols = [row[0] for row in cols_result.fetchall()]
            print(f"    Columns (first 10): {', '.join(cols)}")
            print()

if __name__ == "__main__":
    asyncio.run(check())
