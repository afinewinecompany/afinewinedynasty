"""
Analyze unique players in pitch data vs prospects table
"""
import asyncio
import asyncpg

async def analyze_pitch_data_coverage():
    conn = await asyncpg.connect(
        host="nozomi.proxy.rlwy.net",
        port=39235,
        user="postgres",
        password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp",
        database="railway"
    )

    print("=" * 70)
    print("PITCH DATA PLAYER COVERAGE ANALYSIS")
    print("=" * 70)

    # Pitchers in pitch data
    pitcher_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_pitcher_id)
        FROM milb_pitcher_pitches
        WHERE mlb_pitcher_id IS NOT NULL
    """)

    # Batters in pitch data
    batter_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_batter_id)
        FROM milb_batter_pitches
        WHERE mlb_batter_id IS NOT NULL
    """)

    # Total unique players in pitch data (union)
    total_pitch_players = await conn.fetchval("""
        SELECT COUNT(DISTINCT player_id) FROM (
            SELECT mlb_pitcher_id as player_id FROM milb_pitcher_pitches WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id as player_id FROM milb_batter_pitches WHERE mlb_batter_id IS NOT NULL
        ) combined
    """)

    # Prospects with MLB player IDs
    prospects_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT mlb_player_id)
        FROM prospects
        WHERE mlb_player_id IS NOT NULL
    """)

    # Prospects with birth dates
    prospects_with_birth_dates = await conn.fetchval("""
        SELECT COUNT(*)
        FROM prospects
        WHERE birth_date IS NOT NULL
    """)

    # Players in pitch data who are in prospects table
    pitchers_in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT pp.mlb_pitcher_id)
        FROM milb_pitcher_pitches pp
        WHERE pp.mlb_pitcher_id IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
    """)

    batters_in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT bp.mlb_batter_id)
        FROM milb_batter_pitches bp
        WHERE bp.mlb_batter_id IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
    """)

    pitch_players_in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT player_id) FROM (
            SELECT mlb_pitcher_id as player_id FROM milb_pitcher_pitches WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id as player_id FROM milb_batter_pitches WHERE mlb_batter_id IS NOT NULL
        ) combined
        WHERE player_id IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
    """)

    # Players in pitch data NOT in prospects table
    pitchers_not_in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT pp.mlb_pitcher_id)
        FROM milb_pitcher_pitches pp
        WHERE pp.mlb_pitcher_id NOT IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
    """)

    batters_not_in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT bp.mlb_batter_id)
        FROM milb_batter_pitches bp
        WHERE bp.mlb_batter_id NOT IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
    """)

    pitch_players_not_in_prospects = await conn.fetchval("""
        SELECT COUNT(DISTINCT player_id) FROM (
            SELECT mlb_pitcher_id as player_id FROM milb_pitcher_pitches WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id as player_id FROM milb_batter_pitches WHERE mlb_batter_id IS NOT NULL
        ) combined
        WHERE player_id NOT IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
    """)

    # Get sample of players NOT in prospects
    sample_not_in_prospects = await conn.fetch("""
        SELECT player_id FROM (
            SELECT mlb_pitcher_id as player_id FROM milb_pitcher_pitches WHERE mlb_pitcher_id IS NOT NULL
            UNION
            SELECT mlb_batter_id as player_id FROM milb_batter_pitches WHERE mlb_batter_id IS NOT NULL
        ) combined
        WHERE player_id NOT IN (
            SELECT mlb_player_id FROM prospects WHERE mlb_player_id IS NOT NULL
        )
        LIMIT 10
    """)

    print("\n1. PITCH DATA OVERVIEW")
    print("-" * 70)
    print(f"Unique pitchers in milb_pitcher_pitches:  {pitcher_count:,}")
    print(f"Unique batters in milb_batter_pitches:    {batter_count:,}")
    print(f"Total unique players in pitch data:       {total_pitch_players:,}")

    print("\n2. PROSPECTS TABLE OVERVIEW")
    print("-" * 70)
    print(f"Prospects with MLB player ID:             {prospects_count:,}")
    print(f"Prospects with birth dates:               {prospects_with_birth_dates:,}")
    print(f"Birth date coverage:                      {prospects_with_birth_dates/prospects_count*100:.1f}%")

    print("\n3. OVERLAP ANALYSIS")
    print("-" * 70)
    print(f"Pitchers in BOTH pitch data & prospects:  {pitchers_in_prospects:,}")
    print(f"Batters in BOTH pitch data & prospects:   {batters_in_prospects:,}")
    print(f"Total players in BOTH:                    {pitch_players_in_prospects:,}")

    print("\n4. MISSING FROM PROSPECTS TABLE")
    print("-" * 70)
    print(f"Pitchers with pitch data NOT in prospects: {pitchers_not_in_prospects:,}")
    print(f"Batters with pitch data NOT in prospects:  {batters_not_in_prospects:,}")
    print(f"Total players NOT in prospects:            {pitch_players_not_in_prospects:,}")

    print("\n5. COVERAGE SUMMARY")
    print("-" * 70)
    pitch_in_prospects_pct = (pitch_players_in_prospects / total_pitch_players * 100) if total_pitch_players > 0 else 0
    print(f"% of pitch data players in prospects:     {pitch_in_prospects_pct:.1f}%")
    print(f"Players with pitch data missing from DB:  {pitch_players_not_in_prospects:,}")

    print("\n6. RECOMMENDATION")
    print("-" * 70)
    if pitch_players_not_in_prospects > 0:
        print(f"ACTION REQUIRED: Collect birth dates for {pitch_players_not_in_prospects:,} additional players")
        print("These players have valuable pitch-by-pitch data but no biographical info")
        print("\nEstimated effort:")
        print(f"  - API calls needed: ~{pitch_players_not_in_prospects:,}")
        print(f"  - Time estimate: ~{pitch_players_not_in_prospects / 250:.1f} minutes at 4 calls/sec")
        print(f"  - We should add these to prospects table or create separate players table")
    else:
        print("All players with pitch data are already in prospects table!")

    print("\n7. SAMPLE PLAYER IDs NOT IN PROSPECTS")
    print("-" * 70)
    for i, row in enumerate(sample_not_in_prospects, 1):
        print(f"{i}. Player ID: {row['player_id']}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_pitch_data_coverage())
