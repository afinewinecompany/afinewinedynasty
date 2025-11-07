#!/usr/bin/env python3
"""
Debug why statline rankings are not showing any players.
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
    """Debug the statline query issues."""

    # Try local database first
    database_url = os.getenv('DATABASE_URL')
    if not database_url or 'localhost' not in database_url:
        # Use Railway production if no local
        database_url = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

    print("=" * 80)
    print("DEBUGGING STATLINE RANKINGS ISSUE")
    print("=" * 80)

    engine = create_async_engine(database_url.replace('postgresql://', 'postgresql+asyncpg://'), echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # 1. Check if milb_batter_pitches exists and has data
            print("\n1. CHECK MILB_BATTER_PITCHES TABLE:")
            result = await session.execute(text("""
                SELECT
                    EXISTS(SELECT 1 FROM information_schema.tables
                           WHERE table_name = 'milb_batter_pitches') as table_exists,
                    (SELECT COUNT(*) FROM milb_batter_pitches
                     WHERE season IN (2024, 2025)) as pitch_count_2024_2025,
                    (SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches
                     WHERE season IN (2024, 2025)) as unique_batters_2024_2025
            """))
            row = result.fetchone()
            print(f"   Table exists: {row[0]}")
            print(f"   Pitches in 2024-2025: {row[1] if row[0] else 'N/A'}")
            print(f"   Unique batters in 2024-2025: {row[2] if row[0] else 'N/A'}")

            # 2. Check prospect_stats table
            print("\n2. CHECK PROSPECT_STATS TABLE:")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) as total_records,
                    COUNT(DISTINCT prospect_id) as unique_prospects,
                    MIN(date_recorded) as earliest_date,
                    MAX(date_recorded) as latest_date
                FROM prospect_stats
                WHERE at_bats > 0
            """))
            row = result.fetchone()
            print(f"   Total records: {row[0]}")
            print(f"   Unique prospects: {row[1]}")
            print(f"   Date range: {row[2]} to {row[3]}")

            # 3. Test the simplified fallback query with very low threshold
            print("\n3. TEST FALLBACK QUERY (min_pa=10):")
            result = await session.execute(text("""
                WITH latest_stats AS (
                    SELECT
                        p.id as prospect_id,
                        p.name,
                        p.level,
                        ps.at_bats,
                        ps.walks,
                        ps.hits,
                        ps.home_runs,
                        ps.strikeouts,
                        GREATEST(
                            COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0),
                            CAST(COALESCE(ps.at_bats, 0) * 1.15 AS INT)
                        ) as total_pa,
                        ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ps.date_recorded DESC) as rn
                    FROM prospect_stats ps
                    JOIN prospects p ON p.id = ps.prospect_id
                    WHERE ps.at_bats > 0
                )
                SELECT COUNT(*) as player_count
                FROM latest_stats
                WHERE rn = 1 AND total_pa >= 10
            """))
            count = result.scalar()
            print(f"   Players with 10+ PA: {count}")

            # 4. Get sample players to see actual data
            print("\n4. SAMPLE PLAYERS FROM PROSPECT_STATS:")
            result = await session.execute(text("""
                WITH latest_stats AS (
                    SELECT
                        p.name,
                        p.level,
                        ps.at_bats,
                        ps.walks,
                        ps.hits,
                        GREATEST(
                            COALESCE(ps.at_bats, 0) + COALESCE(ps.walks, 0),
                            CAST(COALESCE(ps.at_bats, 0) * 1.15 AS INT)
                        ) as total_pa,
                        ps.date_recorded,
                        ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY ps.date_recorded DESC) as rn
                    FROM prospect_stats ps
                    JOIN prospects p ON p.id = ps.prospect_id
                    WHERE ps.at_bats > 0
                )
                SELECT *
                FROM latest_stats
                WHERE rn = 1
                ORDER BY total_pa DESC
                LIMIT 5
            """))

            for row in result:
                print(f"\n   {row.name} ({row.level}):")
                print(f"      AB: {row.at_bats}, BB: {row.walks}, PA: {row.total_pa}")
                print(f"      Last update: {row.date_recorded}")

            # 5. Test if the concatenation in pitch data query works
            print("\n5. TEST PITCH DATA CONCATENATION:")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT game_id || '_' || pa_of_inning) as unique_pas,
                    COUNT(DISTINCT CONCAT(game_id, '_', pa_of_inning)) as unique_pas_concat
                FROM milb_batter_pitches
                WHERE season = 2024
                    AND event_result IS NOT NULL
                LIMIT 1
            """))
            row = result.fetchone()
            if row:
                print(f"   Total events: {row[0]}")
                print(f"   Unique PAs (||): {row[1]}")
                print(f"   Unique PAs (CONCAT): {row[2]}")

            # 6. Check if prospects table has mlb_player_id populated
            print("\n6. CHECK PROSPECTS MLB_PLAYER_ID:")
            result = await session.execute(text("""
                SELECT
                    COUNT(*) as total_prospects,
                    COUNT(mlb_player_id) as with_mlb_id,
                    COUNT(CASE WHEN mlb_player_id IS NOT NULL AND mlb_player_id != '' THEN 1 END) as valid_mlb_id
                FROM prospects
            """))
            row = result.fetchone()
            print(f"   Total prospects: {row[0]}")
            print(f"   With MLB ID: {row[1]}")
            print(f"   Valid MLB ID: {row[2]}")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await engine.dispose()

    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(debug_statline())