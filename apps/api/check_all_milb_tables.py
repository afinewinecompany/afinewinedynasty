#!/usr/bin/env python3
"""
Check all MILB-related tables in the database to understand what data is available.
"""

import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

async def check_all_tables():
    """Check all MILB tables and their structure."""

    # Use Railway production database
    database_url = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

    print("=" * 80)
    print("COMPREHENSIVE DATABASE SCHEMA CHECK")
    print("=" * 80)

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 1. Get all tables in the database
            print("\n1. ALL TABLES IN DATABASE:")
            result = await session.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))

            all_tables = []
            for row in result:
                all_tables.append(row.table_name)
                print(f"   - {row.table_name}")

            # 2. Check MILB-specific tables
            print("\n2. MILB-SPECIFIC TABLES:")
            milb_tables = [t for t in all_tables if 'milb' in t.lower() or 'pitch' in t.lower()]
            for table in milb_tables:
                print(f"\n   Table: {table}")

                # Get column info
                result = await session.execute(text(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = '{table}'
                    ORDER BY ordinal_position
                    LIMIT 15
                """))

                columns = []
                for col in result:
                    columns.append(f"{col.column_name} ({col.data_type})")
                print(f"      Columns: {', '.join(columns[:5])}")
                if len(columns) > 5:
                    print(f"               {', '.join(columns[5:10])}")
                if len(columns) > 10:
                    print(f"               {', '.join(columns[10:])}")

                # Get row count
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"      Row count: {count:,}")
                except Exception as e:
                    print(f"      Row count: ERROR - {str(e)[:50]}")

            # 3. Check milb_batter_pitches specifically
            if 'milb_batter_pitches' in all_tables:
                print("\n3. MILB_BATTER_PITCHES ANALYSIS:")

                # Sample data
                result = await session.execute(text("""
                    SELECT DISTINCT
                        bp.mlb_batter_id,
                        bp.mlb_batter_name,
                        bp.season,
                        COUNT(*) as pitch_count
                    FROM milb_batter_pitches bp
                    GROUP BY bp.mlb_batter_id, bp.mlb_batter_name, bp.season
                    ORDER BY pitch_count DESC
                    LIMIT 5
                """))

                print("   Top 5 batters by pitch count:")
                for row in result:
                    print(f"      {row.mlb_batter_name} (ID: {row.mlb_batter_id}): {row.pitch_count:,} pitches in {row.season}")

                # Check if we can join with prospects
                result = await session.execute(text("""
                    SELECT COUNT(DISTINCT bp.mlb_batter_id) as batter_count
                    FROM milb_batter_pitches bp
                    WHERE EXISTS (
                        SELECT 1 FROM prospects p
                        WHERE CAST(p.mlb_player_id AS INTEGER) = bp.mlb_batter_id
                    )
                """))
                count = result.scalar()
                print(f"\n   Batters that match prospects table: {count}")

                # Check available seasons
                result = await session.execute(text("""
                    SELECT DISTINCT season, COUNT(DISTINCT mlb_batter_id) as player_count
                    FROM milb_batter_pitches
                    GROUP BY season
                    ORDER BY season DESC
                """))
                print("\n   Available seasons:")
                for row in result:
                    print(f"      {row.season}: {row.player_count} players")

            # 4. Check milb_pitcher_pitches if exists
            if 'milb_pitcher_pitches' in all_tables:
                print("\n4. MILB_PITCHER_PITCHES ANALYSIS:")

                result = await session.execute(text("""
                    SELECT COUNT(DISTINCT mlb_pitcher_id) as pitcher_count,
                           COUNT(*) as total_pitches
                    FROM milb_pitcher_pitches
                """))
                row = result.fetchone()
                print(f"   Total pitchers: {row.pitcher_count}")
                print(f"   Total pitches: {row.total_pitches:,}")

            # 5. Check for aggregated stats tables
            print("\n5. AGGREGATED STATS TABLES:")
            stats_tables = [t for t in all_tables if 'stat' in t.lower() or 'agg' in t.lower()]
            for table in stats_tables:
                try:
                    result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = result.scalar()
                    print(f"   {table}: {count:,} records")
                except:
                    pass

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_all_tables())