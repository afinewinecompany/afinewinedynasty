"""
Check pitch data player coverage
"""
import asyncio
import asyncpg

async def check_coverage():
    conn = await asyncpg.connect(
        host="nozomi.proxy.rlwy.net",
        port=39235,
        user="postgres",
        password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp",
        database="railway"
    )

    print("=" * 70)
    print("PITCH DATA PLAYER COVERAGE CHECK")
    print("=" * 70)

    # Get column types
    pitcher_cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'milb_pitcher_pitches'
        AND column_name LIKE '%pitcher%'
    """)

    batter_cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'milb_batter_pitches'
        AND column_name LIKE '%batter%'
    """)

    prospect_cols = await conn.fetch("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'prospects'
        AND column_name LIKE '%player%'
    """)

    print("\nColumn types:")
    print("\nmilb_pitcher_pitches:")
    for col in pitcher_cols:
        print(f"  {col['column_name']}: {col['data_type']}")

    print("\nmilb_batter_pitches:")
    for col in batter_cols:
        print(f"  {col['column_name']}: {col['data_type']}")

    print("\nprospects:")
    for col in prospect_cols:
        print(f"  {col['column_name']}: {col['data_type']}")

    # Simple counts
    pitcher_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_pitcher_id::text)
        FROM milb_pitcher_pitches
        WHERE mlb_pitcher_id IS NOT NULL
    """)

    batter_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_batter_id::text)
        FROM milb_batter_pitches
        WHERE mlb_batter_id IS NOT NULL
    """)

    prospect_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_player_id::text)
        FROM prospects
        WHERE mlb_player_id IS NOT NULL
    """)

    print("\n" + "=" * 70)
    print("PLAYER COUNTS")
    print("=" * 70)
    print(f"Unique pitchers in pitch data:  {pitcher_count:,}")
    print(f"Unique batters in pitch data:   {batter_count:,}")
    print(f"Prospects with MLB player ID:   {prospect_count:,}")

    # Total unique in pitch data
    total_pitch = await conn.fetchval("""
        SELECT COUNT(DISTINCT player_id) FROM (
            SELECT mlb_pitcher_id::text as player_id
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id::text as player_id
            FROM milb_batter_pitches
            WHERE mlb_batter_id IS NOT NULL
        ) combined
    """)

    print(f"Total unique players with pitch data: {total_pitch:,}")

    # How many pitch data players are in prospects?
    in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT player_id) FROM (
            SELECT mlb_pitcher_id::text as player_id
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id::text as player_id
            FROM milb_batter_pitches
            WHERE mlb_batter_id IS NOT NULL
        ) pitch_players
        WHERE player_id IN (
            SELECT mlb_player_id::text
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
        )
    """)

    not_in_prospects = total_pitch - in_prospects

    print(f"\nPlayers with pitch data IN prospects table:     {in_prospects:,}")
    print(f"Players with pitch data NOT IN prospects table: {not_in_prospects:,}")
    print(f"Coverage: {in_prospects/total_pitch*100:.1f}%")

    # Get sample of missing players
    missing_sample = await conn.fetch("""
        SELECT player_id FROM (
            SELECT mlb_pitcher_id::text as player_id
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id::text as player_id
            FROM milb_batter_pitches
            WHERE mlb_batter_id IS NOT NULL
        ) pitch_players
        WHERE player_id NOT IN (
            SELECT mlb_player_id::text
            FROM prospects
            WHERE mlb_player_id IS NOT NULL
        )
        LIMIT 10
    """)

    print("\n" + "=" * 70)
    print("SAMPLE PLAYERS WITH PITCH DATA NOT IN PROSPECTS TABLE:")
    print("=" * 70)
    for row in missing_sample:
        print(f"  Player ID: {row['player_id']}")

    # Recommendation
    print("\n" + "=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    if not_in_prospects > 0:
        print(f"ACTION: Collect birth dates for {not_in_prospects:,} additional players")
        print(f"        These have pitch-by-pitch data but no biographical info")
        print(f"        Estimated time: ~{not_in_prospects / 250:.1f} minutes")
    else:
        print("All players with pitch data are in prospects table!")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_coverage())
