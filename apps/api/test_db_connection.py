"""Test database connection and check PBP data"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check_pbp_data():
    """Check PBP data in the database"""
    async with engine.begin() as conn:
        print("="*80)
        print("PITCH-BY-PITCH DATA REVIEW (2021-2025)")
        print("="*80)

        # Check milb_plate_appearances table
        print("\n1. MiLB Plate Appearances Table:")
        try:
            result = await conn.execute(text("""
                SELECT
                    season,
                    COUNT(*) as total_pas,
                    COUNT(DISTINCT mlb_player_id) as unique_players,
                    COUNT(CASE WHEN launch_speed IS NOT NULL THEN 1 END) as with_statcast
                FROM milb_plate_appearances
                WHERE season BETWEEN 2021 AND 2025
                GROUP BY season
                ORDER BY season
            """))

            rows = result.fetchall()
            if rows:
                print(f"   {'Season':<10} {'Total PAs':<15} {'Players':<15} {'With Statcast':<15}")
                print(f"   {'-'*60}")
                for row in rows:
                    print(f"   {row[0]:<10} {row[1]:<15,} {row[2]:<15,} {row[3]:<15,}")
            else:
                print("   [X] NO DATA FOUND")
        except Exception as e:
            print(f"   [X] ERROR: {e}")

        # Check if pitcher data is included
        print("\n2. Pitcher Involvement in PBP Data:")
        try:
            # Check if we have pitcher information in the plays
            result = await conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_name = 'milb_plate_appearances'
                AND column_name LIKE '%pitcher%'
            """))
            pitcher_cols = result.scalar()

            if pitcher_cols > 0:
                print(f"   [OK] Found {pitcher_cols} pitcher-related columns")

                # Get column names
                result = await conn.execute(text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'milb_plate_appearances'
                    AND column_name LIKE '%pitcher%'
                """))
                cols = [r[0] for r in result.fetchall()]
                print(f"   Columns: {', '.join(cols)}")
            else:
                print("   [X] NO pitcher columns found in milb_plate_appearances")
                print("   [!] This means pitcher PBP data was NOT collected")
        except Exception as e:
            print(f"   [X] ERROR: {e}")

        # Check for MLB Statcast pitching data
        print("\n3. MLB Statcast Pitching Table:")
        try:
            result = await conn.execute(text("""
                SELECT
                    season,
                    COUNT(*) as total_pitches,
                    COUNT(DISTINCT mlb_player_id) as unique_pitchers
                FROM mlb_statcast_pitching
                WHERE season BETWEEN 2021 AND 2025
                GROUP BY season
                ORDER BY season
            """))

            rows = result.fetchall()
            if rows:
                print(f"   {'Season':<10} {'Total Pitches':<15} {'Pitchers':<15}")
                print(f"   {'-'*45}")
                for row in rows:
                    print(f"   {row[0]:<10} {row[1]:<15,} {row[2]:<15,}")
            else:
                print("   [X] NO DATA FOUND")
        except Exception as e:
            print(f"   [X] Table does not exist or error: {e}")

        # Check all tables with pitcher data
        print("\n4. All Tables with Pitcher PBP Data:")
        try:
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND (
                    table_name LIKE '%pitch%'
                    OR table_name LIKE '%pitcher%'
                    OR table_name LIKE '%pbp%'
                    OR table_name LIKE '%statcast%'
                )
                ORDER BY table_name
            """))

            tables = [r[0] for r in result.fetchall()]
            if tables:
                print(f"   Found {len(tables)} related tables:")
                for table in tables:
                    # Get row count
                    count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    print(f"   - {table}: {count:,} rows")
            else:
                print("   [X] NO TABLES FOUND")
        except Exception as e:
            print(f"   [X] ERROR: {e}")

        # SUMMARY
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print("\nBased on the collection scripts analyzed:")
        print("1. collect_pbp_2025.py - Collects BATTER plate appearances only")
        print("   - Filters: batter_id == player_id (line 228)")
        print("   - Does NOT collect pitcher matchup data")
        print("")
        print("2. collect_pbp_2021.py - Checks both batter AND pitcher (line 89)")
        print("   - Filters: batter_id == player_id OR pitcher_id == player_id")
        print("   - However, only counts plays, doesn't save pitcher data")
        print("")
        print("CONCLUSION:")
        print("  [X] Pitcher PBP data was NOT SAVED to database")
        print("  [!] Collections focused on hitter plate appearances only")
        print("  [!] Pitcher matchup data exists in API but was not persisted")


if __name__ == "__main__":
    asyncio.run(check_pbp_data())
