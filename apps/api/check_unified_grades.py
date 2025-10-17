"""Check fangraphs_unified_grades schema"""
import asyncio
from sqlalchemy import text
from app.db.database import engine


async def check():
    async with engine.begin() as conn:
        # Get all columns
        result = await conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'fangraphs_unified_grades'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()

        print("=" * 80)
        print("FANGRAPHS_UNIFIED_GRADES SCHEMA")
        print("=" * 80)

        print(f"\n{'Column Name':<35} {'Data Type':<20}")
        print("-" * 80)
        for col in columns:
            print(f"{col[0]:<35} {col[1]:<20}")

        # Sample data
        result2 = await conn.execute(text("""
            SELECT
                player_name,
                position,
                year,
                fv,
                hit_future,
                game_power_future,
                speed_future,
                field_future,
                arm_future
            FROM fangraphs_unified_grades
            WHERE hit_future IS NOT NULL
            ORDER BY fv DESC NULLS LAST
            LIMIT 10
        """))

        print("\n" + "=" * 80)
        print("SAMPLE HITTER GRADES (Top 10 by FV)")
        print("=" * 80)
        print(f"\n{'Player':<25} {'Pos':<5} {'Year':<6} {'FV':<4} {'Hit':<4} {'Pwr':<4} {'Spd':<4} {'Fld':<4} {'Arm':<4}")
        print("-" * 80)

        for row in result2.fetchall():
            name, pos, year, fv, hit, pwr, spd, fld, arm = row
            print(f"{name:<25} {pos:<5} {year:<6} {fv or '-':<4} {hit or '-':<4} {pwr or '-':<4} {spd or '-':<4} {fld or '-':<4} {arm or '-':<4}")

if __name__ == "__main__":
    asyncio.run(check())
