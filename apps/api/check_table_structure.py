"""Check milb_game_logs table structure and constraints"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check():
    async with engine.begin() as conn:
        # Check if mlb_player_id column exists
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'milb_game_logs'
            AND column_name LIKE '%player%'
            ORDER BY column_name
        """))

        print("Player ID Columns in milb_game_logs:")
        print("-" * 50)
        for row in result:
            print(f"  {row[0]:<20} {row[1]:<15} nullable={row[2]}")
        print()

        # Check indexes/constraints
        result = await conn.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'milb_game_logs'
        """))

        print("Indexes:")
        print("-" * 50)
        for row in result:
            print(f"  {row[0]}")
            print(f"    {row[1]}")
        print()

        # Check for duplicate detection mechanism
        result = await conn.execute(text("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'milb_game_logs'::regclass
        """))

        print("Constraints:")
        print("-" * 50)
        for row in result:
            print(f"  {row[0]} ({row[1]}): {row[2]}")
        print()


if __name__ == "__main__":
    asyncio.run(check())
