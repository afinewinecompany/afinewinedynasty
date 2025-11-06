#!/usr/bin/env python3
"""
Debug script to understand why statline rankings return no data.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def debug_statline():
    """Debug the statline data issue."""

    # Use production database
    database_url = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

    print("=" * 60)
    print("STATLINE DEBUG ANALYSIS")
    print("=" * 60)

    try:
        engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, pool_size=1, connect_args={"timeout": 10})
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            print("\n1. CHECK IF TABLES EXIST:")

            # Check prospects table
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM prospects"))
                count = result.scalar()
                print(f"   prospects table: {count} records")
            except Exception as e:
                print(f"   prospects table ERROR: {str(e)[:50]}")

            # Check milb_game_logs table
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM milb_game_logs"))
                count = result.scalar()
                print(f"   milb_game_logs table: {count} records")
            except Exception as e:
                print(f"   milb_game_logs table ERROR: {str(e)[:50]}")
                print("\n   TABLE DOES NOT EXIST! This is the problem.")

                # Try prospect_stats instead
                print("\n2. CHECKING PROSPECT_STATS AS ALTERNATIVE:")
                result = await session.execute(text("SELECT COUNT(*) FROM prospect_stats"))
                count = result.scalar()
                print(f"   prospect_stats table: {count} records")

            # Check what seasons are available
            print("\n3. CHECK AVAILABLE SEASONS:")
            try:
                result = await session.execute(text("""
                    SELECT EXTRACT(YEAR FROM game_date) as year, COUNT(*) as count
                    FROM milb_game_logs
                    GROUP BY year
                    ORDER BY year DESC
                """))
                for row in result:
                    print(f"   Year {int(row.year)}: {row.count} game logs")
            except:
                # If milb_game_logs doesn't exist, check prospect_stats
                result = await session.execute(text("""
                    SELECT EXTRACT(YEAR FROM date_recorded) as year, COUNT(*) as count
                    FROM prospect_stats
                    GROUP BY year
                    ORDER BY year DESC
                    LIMIT 5
                """))
                print("   From prospect_stats:")
                for row in result:
                    print(f"   Year {int(row.year) if row.year else 'NULL'}: {row.count} records")

            # Test simplified query
            print("\n4. TEST SIMPLIFIED QUERY:")
            try:
                # Try milb_game_logs first
                result = await session.execute(text("""
                    SELECT COUNT(DISTINCT prospect_id)
                    FROM milb_game_logs
                    WHERE plate_appearances > 0
                """))
                count = result.scalar()
                print(f"   Players in milb_game_logs: {count}")
            except:
                # Fall back to prospect_stats
                result = await session.execute(text("""
                    SELECT COUNT(DISTINCT prospect_id)
                    FROM prospect_stats
                    WHERE at_bats > 0
                """))
                count = result.scalar()
                print(f"   Players in prospect_stats with at_bats > 0: {count}")

            # Get sample data
            print("\n5. SAMPLE PLAYERS WITH STATS:")
            try:
                result = await session.execute(text("""
                    SELECT p.name, ps.at_bats, ps.hits, ps.batting_avg
                    FROM prospect_stats ps
                    JOIN prospects p ON p.id = ps.prospect_id
                    WHERE ps.at_bats > 50
                    ORDER BY ps.at_bats DESC
                    LIMIT 5
                """))
                for row in result:
                    avg = row.batting_avg if row.batting_avg else 0.0
                    print(f"   {row.name}: {row.at_bats} AB, {row.hits} H, {avg:.3f} AVG")
            except Exception as e:
                print(f"   Error getting sample: {str(e)[:100]}")

            await engine.dispose()

    except Exception as e:
        print(f"\nCONNECTION ERROR: {str(e)[:200]}")

    print("\n" + "=" * 60)
    print("CONCLUSION: Check if milb_game_logs table exists or use prospect_stats")

if __name__ == "__main__":
    asyncio.run(debug_statline())