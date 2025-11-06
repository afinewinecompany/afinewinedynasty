#!/usr/bin/env python3
"""
Comprehensive test to understand the statline data issue.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_comprehensive():
    """Comprehensive test of the database and statline logic."""

    # Try production database directly
    database_url = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

    print("=" * 60)
    print("COMPREHENSIVE STATLINE DATA TEST")
    print("=" * 60)

    try:
        engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, pool_size=1)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Test 1: Basic table check
            print("\n1. CHECKING TABLES EXIST:")
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM prospects"))
                print(f"   ✓ prospects table exists: {result.scalar()} records")
            except Exception as e:
                print(f"   ✗ prospects table error: {e}")

            try:
                result = await session.execute(text("SELECT COUNT(*) FROM prospect_stats"))
                print(f"   ✓ prospect_stats table exists: {result.scalar()} records")
            except Exception as e:
                print(f"   ✗ prospect_stats table error: {e}")

            # Test 2: Check for any data with at_bats
            print("\n2. CHECKING FOR AT_BATS DATA:")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN at_bats IS NOT NULL THEN 1 END) as with_ab,
                    COUNT(CASE WHEN at_bats > 0 THEN 1 END) as positive_ab,
                    MAX(at_bats) as max_ab,
                    AVG(at_bats) as avg_ab
                FROM prospect_stats
            """))
            row = result.fetchone()
            print(f"   Total records: {row.total}")
            print(f"   With at_bats not null: {row.with_ab}")
            print(f"   With at_bats > 0: {row.positive_ab}")
            print(f"   Max at_bats: {row.max_ab}")
            print(f"   Avg at_bats: {row.avg_ab:.1f if row.avg_ab else 0}")

            # Test 3: Sample data
            print("\n3. SAMPLE DATA (Top 5 by at_bats):")
            result = await session.execute(text("""
                SELECT
                    p.id,
                    p.name,
                    p.level,
                    ps.at_bats,
                    ps.batting_avg,
                    ps.date_recorded
                FROM prospect_stats ps
                JOIN prospects p ON p.id = ps.prospect_id
                WHERE ps.at_bats IS NOT NULL
                ORDER BY ps.at_bats DESC
                LIMIT 5
            """))
            for row in result:
                print(f"   ID:{row.id} - {row.name} ({row.level}): {row.at_bats} AB, {row.batting_avg:.3f if row.batting_avg else 0} AVG - {row.date_recorded}")

            # Test 4: Test the EXACT query from StatlineRankingService
            print("\n4. TESTING EXACT STATLINE QUERY:")
            query = """
            WITH latest_stats AS (
                SELECT
                    ps.prospect_id,
                    p.mlb_player_id,
                    p.name,
                    p.level,
                    COALESCE(ps.at_bats, 0) as total_ab,
                    CAST(COALESCE(ps.at_bats, 0) * 1.1 AS INT) as total_pa,
                    ROW_NUMBER() OVER (PARTITION BY ps.prospect_id ORDER BY ps.date_recorded DESC) as rn
                FROM prospect_stats ps
                JOIN prospects p ON p.id = ps.prospect_id
                WHERE ps.at_bats IS NOT NULL AND ps.at_bats > 0
            )
            SELECT COUNT(*) as player_count
            FROM latest_stats
            WHERE rn = 1
            """
            result = await session.execute(text(query))
            count = result.scalar()
            print(f"   Players returned by statline query: {count}")

            # Test 5: Get sample from statline query
            print("\n5. SAMPLE FROM STATLINE QUERY:")
            query = """
            WITH latest_stats AS (
                SELECT
                    ps.prospect_id,
                    p.mlb_player_id,
                    p.name,
                    p.level,
                    COALESCE(ps.at_bats, 0) as total_ab,
                    CAST(COALESCE(ps.at_bats, 0) * 1.1 AS INT) as total_pa,
                    ROW_NUMBER() OVER (PARTITION BY ps.prospect_id ORDER BY ps.date_recorded DESC) as rn
                FROM prospect_stats ps
                JOIN prospects p ON p.id = ps.prospect_id
                WHERE ps.at_bats IS NOT NULL AND ps.at_bats > 0
            )
            SELECT prospect_id, name, level, total_ab, total_pa
            FROM latest_stats
            WHERE rn = 1
            ORDER BY total_ab DESC
            LIMIT 5
            """
            result = await session.execute(text(query))
            for row in result:
                print(f"   {row.name} ({row.level}): {row.total_ab} AB, {row.total_pa} PA")

            # Test 6: Check if there are pitchers vs position players
            print("\n6. CHECKING PLAYER POSITIONS:")
            result = await session.execute(text("""
                SELECT
                    position,
                    COUNT(*) as count
                FROM prospects
                WHERE id IN (
                    SELECT DISTINCT prospect_id
                    FROM prospect_stats
                    WHERE at_bats IS NOT NULL
                )
                GROUP BY position
                ORDER BY count DESC
                LIMIT 10
            """))
            for row in result:
                print(f"   {row.position}: {row.count} players")

        await engine.dispose()
        print("\n" + "=" * 60)
        print("TEST COMPLETE")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_comprehensive())