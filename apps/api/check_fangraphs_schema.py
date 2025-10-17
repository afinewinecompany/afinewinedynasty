"""Check FanGraphs table schema"""
import asyncio
from sqlalchemy import text, inspect
from app.db.database import engine


async def check_schema():
    async with engine.begin() as conn:
        # Check if table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'fangraphs_prospect_grades'
            )
        """))
        table_exists = result.scalar()

        if not table_exists:
            print("[X] Table 'fangraphs_prospect_grades' does NOT exist")
            return

        print("[OK] Table 'fangraphs_prospect_grades' exists\n")

        # Get column information
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'fangraphs_prospect_grades'
            ORDER BY ordinal_position
        """))

        columns = result.fetchall()

        print("=" * 80)
        print("FANGRAPHS_PROSPECT_GRADES TABLE SCHEMA")
        print("=" * 80)
        print(f"\n{'Column Name':<30} {'Data Type':<20} {'Nullable':<10}")
        print("-" * 80)

        for col in columns:
            print(f"{col[0]:<30} {col[1]:<20} {col[2]:<10}")

        print(f"\nTotal columns: {len(columns)}")

        # Sample data count
        result = await conn.execute(text("SELECT COUNT(*) FROM fangraphs_prospect_grades"))
        count = result.scalar()
        print(f"Total rows: {count:,}")

if __name__ == "__main__":
    asyncio.run(check_schema())
