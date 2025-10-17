#!/usr/bin/env python3
"""
Script to fix migration state after a failed migration.
This resets the alembic_version table to allow the migration to run again.
"""

import asyncio
import sys
from sqlalchemy import text
from app.db.session import get_async_engine


async def fix_migration_state():
    """Reset migration to previous version if stuck"""
    engine = get_async_engine()

    try:
        async with engine.begin() as conn:
            # Check current version
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            current = result.scalar()
            print(f"Current migration version: {current}")

            # Check if columns already exist
            result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='fantrax_leagues'
                AND column_name IN ('my_team_id', 'my_team_name')
            """))
            existing_cols = [row[0] for row in result]
            print(f"Existing my_team columns: {existing_cols}")

            # If we're at c67ca5c732c0 but columns don't exist, reset to previous
            if current == 'c67ca5c732c0' and len(existing_cols) < 2:
                print("\nMigration c67ca5c732c0 is marked complete but columns missing!")
                print("Resetting to previous migration: 0c9d5a8edc04")
                await conn.execute(text("UPDATE alembic_version SET version_num = '0c9d5a8edc04'"))
                print("✅ Reset complete. Run 'alembic upgrade head' to apply migration again.")
            elif len(existing_cols) == 2:
                print("\n✅ Columns exist. Migration completed successfully.")
            else:
                print(f"\n⚠️  Unexpected state. Current version: {current}, Columns: {existing_cols}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix_migration_state())
