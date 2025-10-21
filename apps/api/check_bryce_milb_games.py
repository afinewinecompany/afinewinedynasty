"""Check Bryce Eldridge's MiLB game logs"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    print("\n" + "="*80)
    print("BRYCE ELDRIDGE - MiLB GAME LOGS (2025)")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            level,
            COUNT(*) as games,
            SUM(plate_appearances) as total_pa,
            SUM(at_bats) as total_ab,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_game_logs
        WHERE mlb_player_id = 805811
          AND season = 2025
        GROUP BY level
        ORDER BY MIN(game_date)
    """)

    total_games = 0
    total_pa = 0
    for row in rows:
        total_games += row['games']
        total_pa += row['total_pa'] or 0
        print(f"\n{row['level']}:")
        print(f"  Games: {row['games']}")
        print(f"  PAs: {row['total_pa']}")
        print(f"  ABs: {row['total_ab']}")
        print(f"  Date Range: {row['first_date']} to {row['last_date']}")

    print(f"\nTOTAL: {total_games} games, {total_pa} PAs")
    print(f"Expected pitches (at 4.5 per PA): ~{int(total_pa * 4.5)}")

    print("\n" + "="*80)
    print("CURRENT PITCH DATA:")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            level,
            COUNT(DISTINCT game_pk) as games,
            COUNT(*) as pitches,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_batter_pitches
        WHERE mlb_batter_id = 805811
          AND season = 2025
        GROUP BY level
        ORDER BY MIN(game_date)
    """)

    total_pitches = 0
    for row in rows:
        total_pitches += row['pitches']
        print(f"\n{row['level']}:")
        print(f"  Games: {row['games']}")
        print(f"  Pitches: {row['pitches']:,}")
        print(f"  Date Range: {row['first_date']} to {row['last_date']}")

    if rows:
        print(f"\nTOTAL PITCHES: {total_pitches:,}")
    else:
        print("\nNo pitch data found")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
