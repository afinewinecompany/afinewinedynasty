"""Test if 2025 MILB data exists and is queryable."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

DATABASE_URL = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"

async def test_2025_data():
    engine = create_async_engine(DATABASE_URL, echo=False)

    try:
        async with engine.connect() as conn:
            print("\n=== Testing 2025 MILB Data Availability ===\n")

            # 1. Check basic count of 2025 data
            result = await conn.execute(text("""
                SELECT
                    COUNT(*) as total_pitches,
                    COUNT(DISTINCT mlb_batter_id) as unique_batters,
                    COUNT(DISTINCT game_pk) as unique_games,
                    COUNT(DISTINCT level) as unique_levels
                FROM milb_batter_pitches
                WHERE season = 2025
            """))
            row = result.fetchone()
            print(f"2025 MILB Data Summary:")
            print(f"  Total pitches: {row[0]:,}")
            print(f"  Unique batters: {row[1]:,}")
            print(f"  Unique games: {row[2]:,}")
            print(f"  Unique levels: {row[3]:,}")

            if row[0] == 0:
                print("\nERROR: No 2025 data found!")
                return

            # 2. Test simplified aggregation query
            print("\n=== Testing Simplified Aggregation Query ===\n")
            result = await conn.execute(text("""
                SELECT
                    mlb_batter_id,
                    level,
                    COUNT(DISTINCT game_pk) as games,
                    COUNT(*) as total_pitches,
                    COUNT(DISTINCT CASE
                        WHEN is_final_pitch = true
                        THEN game_pk || '_' || at_bat_index
                    END) as plate_appearances,
                    SUM(CASE WHEN is_final_pitch = true AND LOWER(pa_result) LIKE '%single%' THEN 1 ELSE 0 END) as singles,
                    SUM(CASE WHEN is_final_pitch = true AND LOWER(pa_result) LIKE '%double%' THEN 1 ELSE 0 END) as doubles,
                    SUM(CASE WHEN is_final_pitch = true AND LOWER(pa_result) LIKE '%triple%' THEN 1 ELSE 0 END) as triples,
                    SUM(CASE WHEN is_final_pitch = true AND LOWER(pa_result) LIKE '%home%run%' THEN 1 ELSE 0 END) as home_runs,
                    SUM(CASE WHEN is_final_pitch = true AND LOWER(pa_result) LIKE '%walk%' THEN 1 ELSE 0 END) as walks,
                    SUM(CASE WHEN is_final_pitch = true AND LOWER(pa_result) LIKE '%strikeout%' THEN 1 ELSE 0 END) as strikeouts
                FROM milb_batter_pitches
                WHERE season = 2025
                GROUP BY mlb_batter_id, level
                HAVING COUNT(DISTINCT CASE
                    WHEN is_final_pitch = true
                    THEN game_pk || '_' || at_bat_index
                END) >= 10
                ORDER BY plate_appearances DESC
                LIMIT 5
            """))

            players = result.fetchall()
            if players:
                print(f"Found {len(players)} players with 10+ PAs. Top 5:")
                print(f"\n{'Batter ID':<10} {'Level':<6} {'Games':<6} {'PAs':<5} {'Hits':<5} {'HRs':<4} {'BBs':<4} {'Ks':<4}")
                print("-" * 60)
                for p in players:
                    hits = p[5] + p[6] + p[7] + p[8]  # singles + doubles + triples + homers
                    print(f"{p[0]:<10} {p[1]:<6} {p[2]:<6} {p[4]:<5} {hits:<5} {p[8]:<4} {p[9]:<4} {p[10]:<4}")
            else:
                print("No players found with 10+ PAs")

            # 3. Test discipline metrics
            print("\n=== Testing Discipline Metrics Query ===\n")
            result = await conn.execute(text("""
                SELECT
                    mlb_batter_id,
                    COUNT(*) as total_pitches,
                    AVG(CASE WHEN zone <= 9 THEN 100.0 ELSE 0.0 END) as zone_rate,
                    AVG(CASE WHEN swing = true THEN 100.0 ELSE 0.0 END) as swing_rate,
                    AVG(CASE WHEN zone > 9 AND swing = true THEN 100.0
                            WHEN zone > 9 THEN 0.0
                            ELSE NULL END) as chase_rate,
                    AVG(CASE WHEN swing = true AND contact = true THEN 100.0
                            WHEN swing = true THEN 0.0
                            ELSE NULL END) as contact_rate
                FROM milb_batter_pitches
                WHERE season = 2025
                GROUP BY mlb_batter_id
                HAVING COUNT(*) >= 100
                ORDER BY contact_rate DESC NULLS LAST
                LIMIT 3
            """))

            players = result.fetchall()
            if players:
                print(f"Top 3 players by contact rate (100+ pitches):")
                for p in players:
                    print(f"  ID {p[0]}: {p[1]} pitches, Contact: {p[5]:.1f}%, Chase: {p[4]:.1f}%")

            print("\n=== All Tests Completed Successfully ===")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_2025_data())