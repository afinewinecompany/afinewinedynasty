"""
Analyze the 143 prospects without birth dates to diagnose why they're missing
"""
import asyncio
import asyncpg
import aiohttp

async def analyze_missing():
    conn = await asyncpg.connect(
        host="nozomi.proxy.rlwy.net",
        port=39235,
        user="postgres",
        password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp",
        database="railway"
    )

    print("=" * 80)
    print("ANALYZING 143 PROSPECTS WITHOUT BIRTH DATES")
    print("=" * 80)

    # Get all prospects without birth dates
    missing = await conn.fetch("""
        SELECT
            id,
            mlb_player_id,
            name,
            position,
            organization,
            level,
            age,
            eta_year,
            fg_player_id,
            mlb_id,
            created_at
        FROM prospects
        WHERE birth_date IS NULL
        ORDER BY created_at DESC
    """)

    total_missing = len(missing)
    print(f"\nTotal prospects without birth dates: {total_missing}")

    # Analysis 1: Do they have MLB player IDs?
    with_mlb_id = sum(1 for p in missing if p['mlb_player_id'])
    without_mlb_id = total_missing - with_mlb_id

    print("\n" + "=" * 80)
    print("1. MLB PLAYER ID AVAILABILITY")
    print("=" * 80)
    print(f"With mlb_player_id:    {with_mlb_id} ({with_mlb_id/total_missing*100:.1f}%)")
    print(f"Without mlb_player_id: {without_mlb_id} ({without_mlb_id/total_missing*100:.1f}%)")

    # Analysis 2: Do they have game logs?
    prospects_with_game_logs = await conn.fetch("""
        SELECT
            p.id,
            p.mlb_player_id,
            p.name,
            COUNT(DISTINCT gl.game_pk) as game_count,
            MIN(gl.season) as first_season,
            MAX(gl.season) as last_season
        FROM prospects p
        LEFT JOIN milb_game_logs gl ON p.mlb_player_id::text = gl.mlb_player_id::text
        WHERE p.birth_date IS NULL
        GROUP BY p.id, p.mlb_player_id, p.name
        ORDER BY game_count DESC
    """)

    with_game_logs = sum(1 for p in prospects_with_game_logs if p['game_count'] > 0)
    without_game_logs = total_missing - with_game_logs

    print("\n" + "=" * 80)
    print("2. GAME LOG AVAILABILITY")
    print("=" * 80)
    print(f"With game logs:    {with_game_logs} ({with_game_logs/total_missing*100:.1f}%)")
    print(f"Without game logs: {without_game_logs} ({without_game_logs/total_missing*100:.1f}%)")

    # Show top prospects with game logs but no birth date
    print("\nTop 20 prospects with most game logs but NO birth date:")
    print("-" * 80)
    for i, p in enumerate(prospects_with_game_logs[:20], 1):
        if p['game_count'] > 0:
            print(f"{i:2}. {p['name']:30} | Games: {p['game_count']:4} | Seasons: {p['first_season']}-{p['last_season']} | ID: {p['mlb_player_id']}")

    # Analysis 3: Which seasons do they appear in?
    season_breakdown = await conn.fetch("""
        SELECT
            gl.season,
            COUNT(DISTINCT p.id) as prospect_count
        FROM prospects p
        JOIN milb_game_logs gl ON p.mlb_player_id::text = gl.mlb_player_id::text
        WHERE p.birth_date IS NULL
        GROUP BY gl.season
        ORDER BY gl.season DESC
    """)

    print("\n" + "=" * 80)
    print("3. SEASON BREAKDOWN (for those with game logs)")
    print("=" * 80)
    for row in season_breakdown:
        print(f"Season {row['season']}: {row['prospect_count']} prospects")

    # Analysis 4: Sample prospects without MLB player ID
    no_mlb_id_sample = [p for p in missing if not p['mlb_player_id']][:10]

    print("\n" + "=" * 80)
    print("4. SAMPLE PROSPECTS WITHOUT MLB PLAYER ID")
    print("=" * 80)
    for i, p in enumerate(no_mlb_id_sample, 1):
        fg_id = p['fg_player_id'] or 'None'
        mlb_id = p['mlb_id'] or 'None'
        print(f"{i:2}. {p['name']:30} | Pos: {p['position']:3} | FG ID: {fg_id:10} | MLB ID: {mlb_id}")

    # Analysis 5: Check if we can find them in MLB API
    session = aiohttp.ClientSession()

    print("\n" + "=" * 80)
    print("5. API AVAILABILITY TEST (first 10 with mlb_player_id)")
    print("=" * 80)

    test_prospects = [p for p in missing if p['mlb_player_id']][:10]
    api_found = 0
    api_not_found = 0

    for i, p in enumerate(test_prospects, 1):
        try:
            url = f"https://statsapi.mlb.com/api/v1/people/{p['mlb_player_id']}"
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'people' in data and len(data['people']) > 0:
                        player = data['people'][0]
                        birth_date = player.get('birthDate', 'N/A')
                        api_found += 1
                        print(f"{i:2}. {p['name']:30} | ID: {p['mlb_player_id']:7} | FOUND | Birth: {birth_date}")
                    else:
                        api_not_found += 1
                        print(f"{i:2}. {p['name']:30} | ID: {p['mlb_player_id']:7} | NOT FOUND")
                else:
                    api_not_found += 1
                    print(f"{i:2}. {p['name']:30} | ID: {p['mlb_player_id']:7} | ERROR {response.status}")
            await asyncio.sleep(0.25)
        except Exception as e:
            api_not_found += 1
            print(f"{i:2}. {p['name']:30} | ID: {p['mlb_player_id']:7} | ERROR: {e}")

    await session.close()

    print("\n" + "=" * 80)
    print("6. DIAGNOSIS & RECOMMENDATIONS")
    print("=" * 80)

    print(f"\nTotal missing birth dates: {total_missing}")
    print(f"\nBreakdown:")
    print(f"  - Have mlb_player_id: {with_mlb_id} ({with_mlb_id/total_missing*100:.1f}%)")
    print(f"  - Have game logs: {with_game_logs} ({with_game_logs/total_missing*100:.1f}%)")
    print(f"  - Found in API (sample): {api_found}/{len(test_prospects)} ({api_found/len(test_prospects)*100:.1f}%)")

    print(f"\nRecommendations:")

    if with_mlb_id > 0:
        print(f"  1. Collect birth dates for {with_mlb_id} prospects with mlb_player_id")
        print(f"     - These should be collectible from MLB Stats API")
        print(f"     - Estimated time: ~{with_mlb_id / 250:.1f} minutes")

    if without_mlb_id > 0:
        print(f"  2. Investigate {without_mlb_id} prospects without mlb_player_id")
        print(f"     - May need to search by name or use Fangraphs ID")
        print(f"     - May be international prospects not in MLB system yet")

    if with_game_logs > 0:
        print(f"  3. Prioritize {with_game_logs} prospects with game log data")
        print(f"     - These have performance data and need age for ML features")

    # Export list for collection
    export_list = [p for p in missing if p['mlb_player_id']]

    print(f"\n\nExporting {len(export_list)} prospects with mlb_player_id to CSV...")

    import csv
    with open('missing_birth_dates_with_mlb_id.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'mlb_player_id', 'name', 'position', 'organization'])
        for p in export_list:
            writer.writerow([p['id'], p['mlb_player_id'], p['name'], p['position'], p['organization']])

    print("Exported to: missing_birth_dates_with_mlb_id.csv")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_missing())
