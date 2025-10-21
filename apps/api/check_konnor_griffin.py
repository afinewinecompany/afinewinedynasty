"""Check Konnor Griffin's MiLB data"""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    # Find Konnor Griffin's ID
    prospect = await conn.fetchrow("""
        SELECT id, name, mlb_player_id, position
        FROM prospects
        WHERE name ILIKE '%konnor%griffin%'
        LIMIT 1
    """)

    if not prospect:
        print("Konnor Griffin not found")
        return

    player_id = int(prospect['mlb_player_id'])
    print(f"\nFound: {prospect['name']} (MLB ID: {player_id}, Position: {prospect['position']})")

    # Check game logs
    print("\n" + "="*80)
    print("GAME LOGS BY SEASON")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            season,
            level,
            COUNT(*) as games,
            SUM(plate_appearances) as total_pa
        FROM milb_game_logs
        WHERE mlb_player_id = $1
        GROUP BY season, level
        ORDER BY season DESC, level
    """, player_id)

    total_pa = 0
    for row in rows:
        pa = row['total_pa'] or 0
        total_pa += pa
        expected_pitches = int(pa * 4.5)
        print(f"\n{row['season']} - {row['level']}:")
        print(f"  Games: {row['games']}, PAs: {pa}")
        print(f"  Expected pitches: ~{expected_pitches}")

    print(f"\nTOTAL PAs: {total_pa}, Expected pitches: ~{int(total_pa * 4.5)}")

    # Check actual pitch data
    print("\n" + "="*80)
    print("ACTUAL PITCH DATA")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            season,
            level,
            COUNT(DISTINCT game_pk) as games,
            COUNT(*) as pitches
        FROM milb_batter_pitches
        WHERE mlb_batter_id = $1
        GROUP BY season, level
        ORDER BY season DESC, level
    """, player_id)

    total_pitches = 0
    for row in rows:
        total_pitches += row['pitches']
        print(f"\n{row['season']} - {row['level']}:")
        print(f"  Games: {row['games']}, Pitches: {row['pitches']:,}")

    if total_pitches > 0:
        print(f"\nTOTAL PITCHES: {total_pitches:,}")
        print(f"Coverage: {total_pitches} / {int(total_pa * 4.5)} = {(total_pitches / (total_pa * 4.5) * 100):.1f}%")
    else:
        print("\nNo pitch data found")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
