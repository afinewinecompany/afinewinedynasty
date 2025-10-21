"""Check Bryce Eldridge across all seasons"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    print("\n" + "="*80)
    print("BRYCE ELDRIDGE - ALL SEASONS (MiLB Game Logs)")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            season,
            level,
            COUNT(*) as games,
            SUM(plate_appearances) as total_pa,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_game_logs
        WHERE mlb_player_id = 805811
        GROUP BY season, level
        ORDER BY season, level
    """)

    for row in rows:
        print(f"\n{row['season']} - {row['level']}:")
        print(f"  Games: {row['games']}, PAs: {row['total_pa']}")
        print(f"  Dates: {row['first_date']} to {row['last_date']}")

    # Calculate expected total
    total_pa = sum(row['total_pa'] or 0 for row in rows)
    print(f"\nTOTAL PAs: {total_pa}")
    print(f"Expected pitches (at 4.5 per PA): ~{int(total_pa * 4.5)}")

    # Check actual pitch data
    print("\n" + "="*80)
    print("BRYCE ELDRIDGE - ACTUAL PITCH DATA")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            season,
            level,
            COUNT(DISTINCT game_pk) as games,
            COUNT(*) as pitches
        FROM milb_batter_pitches
        WHERE mlb_batter_id = 805811
        GROUP BY season, level
        ORDER BY season, level
    """)

    total_pitches = 0
    for row in rows:
        total_pitches += row['pitches']
        print(f"\n{row['season']} - {row['level']}:")
        print(f"  Games: {row['games']}, Pitches: {row['pitches']:,}")

    print(f"\nTOTAL PITCHES: {total_pitches:,}")

    # Check prospects table for FV
    print("\n" + "="*80)
    print("PROSPECT INFO")
    print("="*80)

    prospect = await conn.fetchrow("""
        SELECT name, position, level, age, fangraphs_fv_latest
        FROM prospects
        WHERE mlb_player_id = 805811
    """)

    if prospect:
        print(f"Name: {prospect['name']}")
        print(f"Position: {prospect['position']}")
        print(f"Level: {prospect['level']}")
        print(f"Age: {prospect['age']}")
        print(f"FV: {prospect['fangraphs_fv_latest']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
