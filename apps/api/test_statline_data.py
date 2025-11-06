#!/usr/bin/env python3
"""
Test script to check what data exists and why statline rankings return empty.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_data():
    """Check prospect_stats data directly."""

    # Use .env file
    from dotenv import load_dotenv
    load_dotenv('.env')

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("No DATABASE_URL found in environment")
        return

    # Convert to asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Connecting to database...")
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 1. Check total prospects
            result = await session.execute(text("SELECT COUNT(*) FROM prospects"))
            count = result.scalar()
            print(f"\nTotal prospects: {count}")

            # 2. Check total prospect_stats records
            result = await session.execute(text("SELECT COUNT(*) FROM prospect_stats"))
            count = result.scalar()
            print(f"Total prospect_stats records: {count}")

            # 3. Check prospects with stats
            result = await session.execute(text("""
                SELECT COUNT(DISTINCT prospect_id)
                FROM prospect_stats
                WHERE at_bats IS NOT NULL
            """))
            count = result.scalar()
            print(f"Prospects with at_bats data: {count}")

            # 4. Check distribution of at_bats
            result = await session.execute(text("""
                SELECT
                    CASE
                        WHEN at_bats >= 100 THEN '100+'
                        WHEN at_bats >= 50 THEN '50-99'
                        WHEN at_bats >= 25 THEN '25-49'
                        WHEN at_bats > 0 THEN '1-24'
                        ELSE '0 or NULL'
                    END as ab_range,
                    COUNT(DISTINCT prospect_id) as player_count
                FROM prospect_stats
                GROUP BY ab_range
                ORDER BY ab_range DESC
            """))
            print("\nAt-bats distribution:")
            for row in result:
                print(f"  {row.ab_range}: {row.player_count} players")

            # 5. Sample top players by at_bats
            result = await session.execute(text("""
                SELECT
                    p.name,
                    ps.at_bats,
                    ps.hits,
                    ps.batting_avg,
                    p.level,
                    ps.date_recorded
                FROM prospect_stats ps
                JOIN prospects p ON p.id = ps.prospect_id
                WHERE ps.at_bats IS NOT NULL
                ORDER BY ps.at_bats DESC
                LIMIT 10
            """))
            print("\nTop 10 players by at_bats:")
            for row in result:
                print(f"  {row.name}: {row.at_bats} AB, {row.hits} H, {row.batting_avg:.3f} AVG ({row.level}) - {row.date_recorded}")

            # 6. Test the actual query being used (simplified)
            print("\nTesting statline query with min_pa=50...")
            min_pa = 50
            result = await session.execute(text("""
                WITH latest_stats AS (
                    SELECT
                        ps.prospect_id,
                        p.name,
                        p.level,
                        COALESCE(ps.at_bats, 0) as at_bats,
                        CAST(COALESCE(ps.at_bats, 0) * 1.1 AS INT) as estimated_pa,
                        ROW_NUMBER() OVER (PARTITION BY ps.prospect_id ORDER BY ps.date_recorded DESC) as rn
                    FROM prospect_stats ps
                    JOIN prospects p ON p.id = ps.prospect_id
                    WHERE ps.at_bats IS NOT NULL
                        AND COALESCE(ps.at_bats, 0) >= CAST(:min_pa / 1.1 AS INT)
                )
                SELECT COUNT(*)
                FROM latest_stats
                WHERE rn = 1
            """), {"min_pa": min_pa})
            count = result.scalar()
            print(f"Players matching criteria (min_pa={min_pa}): {count}")

            # 7. Check levels available
            result = await session.execute(text("""
                SELECT DISTINCT p.level, COUNT(DISTINCT p.id) as count
                FROM prospects p
                JOIN prospect_stats ps ON ps.prospect_id = p.id
                WHERE ps.at_bats IS NOT NULL
                GROUP BY p.level
                ORDER BY count DESC
            """))
            print("\nLevels with data:")
            for row in result:
                print(f"  {row.level}: {row.count} players")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_data())