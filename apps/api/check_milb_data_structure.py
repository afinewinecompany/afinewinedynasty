"""Check MILB data structure and availability."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

async def check_milb_data():
    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            print("\n=== CHECKING MILB TABLES ===")

            # List all tables with 'milb' in the name
            result = await conn.execute(text("""
                SELECT table_name,
                       (SELECT COUNT(*) FROM information_schema.columns
                        WHERE table_name = t.table_name) as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                AND (table_name LIKE '%milb%' OR table_name LIKE '%game%' OR table_name LIKE '%pitch%')
                ORDER BY table_name
            """))

            tables = result.fetchall()
            print(f"\nFound {len(tables)} relevant tables:")
            for table in tables:
                print(f"  - {table[0]} ({table[1]} columns)")

            # Check milb_batter_pitches structure
            print("\n=== CHECKING milb_batter_pitches COLUMNS ===")
            result = await conn.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'milb_batter_pitches'
                ORDER BY ordinal_position
                LIMIT 20
            """))

            columns = result.fetchall()
            if columns:
                print(f"\nFirst 20 columns of milb_batter_pitches:")
                for col in columns:
                    print(f"  {col[0]:<25} {col[1]:<20} {col[2]}")

                # Check if mlb_batter_name exists
                result = await conn.execute(text("""
                    SELECT COUNT(*)
                    FROM information_schema.columns
                    WHERE table_name = 'milb_batter_pitches'
                    AND column_name = 'mlb_batter_name'
                """))
                has_name = result.scalar()
                print(f"\nHas mlb_batter_name column: {'YES' if has_name else 'NO'}")

            # Check for 2025 data
            print("\n=== CHECKING 2025 DATA AVAILABILITY ===")

            # Check milb_batter_pitches
            result = await conn.execute(text("""
                SELECT COUNT(*) as total_rows,
                       COUNT(DISTINCT mlb_batter_id) as unique_batters,
                       COUNT(DISTINCT season) as seasons,
                       MIN(season) as min_season,
                       MAX(season) as max_season
                FROM milb_batter_pitches
                WHERE season = 2025
            """))
            stats = result.fetchone()
            print(f"\nmilb_batter_pitches 2025 data:")
            print(f"  Total rows: {stats[0]:,}")
            print(f"  Unique batters: {stats[1]:,}")
            print(f"  Seasons present: {stats[2]}")
            print(f"  Season range: {stats[3]} to {stats[4]}")

            # Check prospect_stats
            result = await conn.execute(text("""
                SELECT COUNT(*) as total_rows,
                       COUNT(DISTINCT prospect_id) as unique_prospects,
                       MIN(date_recorded) as oldest_date,
                       MAX(date_recorded) as newest_date
                FROM prospect_stats
            """))
            stats = result.fetchone()
            print(f"\nprospect_stats data:")
            print(f"  Total rows: {stats[0]:,}")
            print(f"  Unique prospects: {stats[1]:,}")
            print(f"  Date range: {stats[2]} to {stats[3]}")

            # Check for game logs
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name LIKE '%game%log%'
            """))
            game_tables = result.fetchall()
            print(f"\nGame log tables found:")
            for table in game_tables:
                print(f"  - {table[0]}")

            # Sample data from milb_batter_pitches
            print("\n=== SAMPLE DATA FROM milb_batter_pitches (2025) ===")
            result = await conn.execute(text("""
                SELECT mlb_batter_id, level, COUNT(*) as pitch_count
                FROM milb_batter_pitches
                WHERE season = 2025
                GROUP BY mlb_batter_id, level
                ORDER BY pitch_count DESC
                LIMIT 5
            """))
            samples = result.fetchall()
            if samples:
                print("\nTop 5 batters by pitch count:")
                for sample in samples:
                    print(f"  Batter ID: {sample[0]}, Level: {sample[1]}, Pitches: {sample[2]}")
            else:
                print("  No 2025 data found!")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_milb_data())