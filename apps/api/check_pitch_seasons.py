"""Check what seasons of pitch data exist in the database."""
import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
    )

    print("\n" + "="*80)
    print("PITCH DATA BY SEASON")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            season,
            COUNT(DISTINCT mlb_batter_id) as batters,
            COUNT(DISTINCT game_pk) as games,
            COUNT(*) as total_pitches,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_batter_pitches
        GROUP BY season
        ORDER BY season DESC
    """)

    for row in rows:
        print(f"\nSeason {row['season']}:")
        print(f"  Batters: {row['batters']}")
        print(f"  Games: {row['games']}")
        print(f"  Total Pitches: {row['total_pitches']:,}")
        print(f"  Date Range: {row['first_date']} to {row['last_date']}")

    print("\n" + "="*80)
    print("GAME LOGS BY SEASON")
    print("="*80)

    rows = await conn.fetch("""
        SELECT
            season,
            COUNT(DISTINCT mlb_player_id) as players,
            COUNT(*) as total_games,
            MIN(game_date) as first_date,
            MAX(game_date) as last_date
        FROM milb_game_logs
        GROUP BY season
        ORDER BY season DESC
    """)

    for row in rows:
        print(f"\nSeason {row['season']}:")
        print(f"  Players: {row['players']}")
        print(f"  Total Games: {row['total_games']:,}")
        print(f"  Date Range: {row['first_date']} to {row['last_date']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
