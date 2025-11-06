#!/usr/bin/env python3
"""
Test the new statline query to see if it returns data from MILB pitch tables.
"""

import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

# Add app to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_statline_query():
    """Test the new statline query using milb_batter_pitches."""

    # Use Railway production database
    database_url = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

    print("=" * 80)
    print("TESTING NEW STATLINE QUERY WITH MILB PITCH DATA")
    print("=" * 80)

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True, pool_size=1)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # First, check if milb_batter_pitches table exists
            print("\n1. CHECK TABLE EXISTS:")
            result = await session.execute(text("""
                SELECT COUNT(*) as count
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'milb_batter_pitches'
            """))
            exists = result.scalar()
            print(f"   milb_batter_pitches exists: {exists > 0}")

            if exists == 0:
                print("\n   ERROR: milb_batter_pitches table does not exist!")
                print("   Will test fallback query instead...")

                # Test fallback query
                result = await session.execute(text("""
                    SELECT COUNT(*) as player_count
                    FROM prospect_stats ps
                    JOIN prospects p ON p.id = ps.prospect_id
                    WHERE ps.at_bats > 0
                        AND GREATEST(ps.at_bats + ps.walks, CAST(ps.at_bats * 1.15 AS INT)) >= 100
                """))
                count = result.scalar()
                print(f"\n   Fallback query found {count} players with 100+ PA")

            else:
                # Check data availability
                print("\n2. CHECK DATA AVAILABILITY:")
                result = await session.execute(text("""
                    SELECT
                        COUNT(DISTINCT mlb_batter_id) as unique_batters,
                        COUNT(*) as total_pitches,
                        COUNT(DISTINCT season) as seasons,
                        MIN(season) as min_season,
                        MAX(season) as max_season
                    FROM milb_batter_pitches
                """))
                row = result.fetchone()
                print(f"   Unique batters: {row.unique_batters}")
                print(f"   Total pitches: {row.total_pitches:,}")
                print(f"   Seasons: {row.min_season} to {row.max_season}")

                # Test simplified version of the main query
                print("\n3. TEST SIMPLIFIED QUERY (min_pa=50):")
                result = await session.execute(text("""
                    WITH player_stats AS (
                        SELECT
                            bp.mlb_batter_id,
                            bp.mlb_batter_name as name,
                            bp.level,
                            COUNT(DISTINCT bp.game_id) as games,
                            COUNT(*) as total_pitches,
                            COUNT(DISTINCT CASE
                                WHEN bp.event_result IS NOT NULL
                                THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                            END) as total_pa
                        FROM milb_batter_pitches bp
                        WHERE bp.season = 2025
                        GROUP BY bp.mlb_batter_id, bp.mlb_batter_name, bp.level
                        HAVING COUNT(DISTINCT CASE
                            WHEN bp.event_result IS NOT NULL
                            THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                        END) >= 50
                    )
                    SELECT COUNT(*) as player_count
                    FROM player_stats
                """))
                count = result.scalar()
                print(f"   Found {count} players with 50+ PA in 2025 season")

                # If no 2025 data, check 2024
                if count == 0:
                    print("\n4. NO 2025 DATA - CHECKING 2024:")
                    result = await session.execute(text("""
                        WITH player_stats AS (
                            SELECT
                                bp.mlb_batter_id,
                                bp.mlb_batter_name as name,
                                COUNT(DISTINCT CASE
                                    WHEN bp.event_result IS NOT NULL
                                    THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                                END) as total_pa
                            FROM milb_batter_pitches bp
                            WHERE bp.season = 2024
                            GROUP BY bp.mlb_batter_id, bp.mlb_batter_name
                            HAVING COUNT(DISTINCT CASE
                                WHEN bp.event_result IS NOT NULL
                                THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                            END) >= 50
                        )
                        SELECT COUNT(*) as player_count
                        FROM player_stats
                    """))
                    count = result.scalar()
                    print(f"   Found {count} players with 50+ PA in 2024 season")

                # Get sample players with advanced metrics
                print("\n5. SAMPLE PLAYERS WITH ADVANCED METRICS:")
                result = await session.execute(text("""
                    WITH player_stats AS (
                        SELECT
                            bp.mlb_batter_id,
                            bp.mlb_batter_name as name,
                            bp.level,
                            COUNT(*) as total_pitches,
                            COUNT(DISTINCT CASE
                                WHEN bp.event_result IS NOT NULL
                                THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                            END) as total_pa,
                            AVG(CASE WHEN bp.contact = TRUE AND bp.swing = TRUE THEN 1.0 ELSE 0.0 END) * 100 as contact_rate,
                            AVG(CASE WHEN bp.swing_and_miss = TRUE THEN 1.0 ELSE 0.0 END) * 100 as whiff_rate,
                            COUNT(*) FILTER (WHERE bp.hardness = 'hard') * 100.0 /
                                NULLIF(COUNT(*) FILTER (WHERE bp.hardness IS NOT NULL), 0) as hard_hit_rate,
                            AVG(bp.exit_velocity) FILTER (WHERE bp.exit_velocity IS NOT NULL) as avg_exit_velo
                        FROM milb_batter_pitches bp
                        WHERE bp.season IN (2024, 2025)
                        GROUP BY bp.mlb_batter_id, bp.mlb_batter_name, bp.level
                        HAVING COUNT(DISTINCT CASE
                            WHEN bp.event_result IS NOT NULL
                            THEN CONCAT(bp.game_id, '_', bp.pa_of_inning)
                        END) >= 100
                    )
                    SELECT *
                    FROM player_stats
                    ORDER BY total_pa DESC
                    LIMIT 5
                """))

                for row in result:
                    print(f"\n   {row.name} ({row.level}):")
                    print(f"      PA: {row.total_pa}, Pitches: {row.total_pitches}")
                    print(f"      Contact: {row.contact_rate:.1f}%, Whiff: {row.whiff_rate:.1f}%")
                    if row.hard_hit_rate:
                        print(f"      Hard Hit: {row.hard_hit_rate:.1f}%")
                    else:
                        print("      Hard Hit: N/A")
                    if row.avg_exit_velo:
                        print(f"      Exit Velo: {row.avg_exit_velo:.1f} mph")
                    else:
                        print("      Exit Velo: N/A")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await engine.dispose()

    print("\n" + "=" * 80)
    print("TEST COMPLETE")

if __name__ == "__main__":
    asyncio.run(test_statline_query())