"""Check pitch-by-pitch data for pitchers"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check():
    async with engine.begin() as conn:
        print("=" * 80)
        print("PITCHER PITCH-BY-PITCH DATA AVAILABILITY")
        print("=" * 80)

        # Check mlb_statcast_pitching
        print("\n1. MLB Statcast Pitching (mlb_statcast_pitching):")
        result = await conn.execute(text("""
            SELECT
                COUNT(*) as total_pitches,
                COUNT(DISTINCT mlb_player_id) as unique_pitchers,
                MIN(season) as first_season,
                MAX(season) as last_season,
                COUNT(DISTINCT pitch_type) as pitch_types
            FROM mlb_statcast_pitching
        """))
        row = result.fetchone()
        print(f"   Total pitches: {row[0]:,}")
        print(f"   Unique pitchers: {row[1]:,}")
        print(f"   Seasons: {row[2]}-{row[3]}" if row[2] else "   Seasons: No data")
        print(f"   Pitch types: {row[4]}")

        if row[0] == 0:
            print("   [X] NO DATA - Table is empty")
        else:
            # Sample columns
            cols_result = await conn.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'mlb_statcast_pitching'
                ORDER BY ordinal_position
            """))
            cols = [r[0] for r in cols_result.fetchall()]
            print(f"   Columns ({len(cols)}): {', '.join(cols[:20])}")

        # Check for MiLB pitcher PBP data
        print("\n2. MiLB Pitcher Play-by-Play:")
        result2 = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND (
                table_name LIKE '%milb%pitch%'
                OR table_name LIKE '%pbp%pitch%'
                OR table_name LIKE '%minor%pitch%'
              )
        """))
        milb_tables = [r[0] for r in result2.fetchall()]

        if milb_tables:
            print(f"   Found {len(milb_tables)} MiLB pitcher tables:")
            for table in milb_tables:
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()
                print(f"   - {table}: {count:,} rows")
        else:
            print("   [X] NO MiLB pitcher PBP tables found")

        # Check if milb_game_logs has pitcher Statcast-like metrics
        print("\n3. MiLB Game Logs - Pitcher Advanced Metrics:")
        result3 = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'milb_game_logs'
              AND (
                column_name LIKE '%velo%'
                OR column_name LIKE '%spin%'
                OR column_name LIKE '%movement%'
                OR column_name LIKE '%extension%'
                OR column_name LIKE '%release%'
              )
            ORDER BY ordinal_position
        """))
        advanced_cols = [r[0] for r in result3.fetchall()]

        if advanced_cols:
            print(f"   [OK] Found {len(advanced_cols)} advanced pitcher columns:")
            for col in advanced_cols:
                print(f"   - {col}")
        else:
            print("   [X] NO advanced pitcher metrics in milb_game_logs")

        # Check for ANY pitcher Statcast metrics aggregated
        print("\n4. Pitcher Statcast Aggregated Tables:")
        result4 = await conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name LIKE '%statcast%'
        """))
        all_statcast_tables = [r[0] for r in result4.fetchall()]

        for table in all_statcast_tables:
            # Check if it has pitcher-specific columns
            cols_result = await conn.execute(text(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table}'
                  AND (
                    column_name LIKE '%fb%'
                    OR column_name LIKE '%fastball%'
                    OR column_name LIKE '%slider%'
                    OR column_name LIKE '%curve%'
                    OR column_name LIKE '%pitch%'
                    OR column_name LIKE '%spin%'
                    OR column_name LIKE '%velo%'
                  )
            """))
            pitcher_cols = [r[0] for r in cols_result.fetchall()]

            if pitcher_cols:
                count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()
                print(f"\n   Table: {table}")
                print(f"   Rows: {count:,}")
                print(f"   Pitcher columns ({len(pitcher_cols)}): {', '.join(pitcher_cols[:10])}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        if row[0] > 0:
            print("[OK] MLB pitcher pitch-by-pitch data: AVAILABLE")
        else:
            print("[X] MLB pitcher pitch-by-pitch data: NOT AVAILABLE")

        if len(milb_tables) > 0:
            print("[OK] MiLB pitcher pitch-by-pitch data: AVAILABLE")
        else:
            print("[X] MiLB pitcher pitch-by-pitch data: NOT AVAILABLE")

        print("\nRECOMMENDATION:")
        print("   - For MLB pitchers: Use pitch-by-pitch if available")
        print("   - For MiLB pitchers: Use FanGraphs grades + aggregated stats")
        print("   - Feature engineering: Combine both sources when available")

if __name__ == "__main__":
    asyncio.run(check())
