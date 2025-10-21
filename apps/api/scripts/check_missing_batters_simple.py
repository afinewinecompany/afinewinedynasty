import asyncio
import aiohttp
import psycopg2

# Database connection
conn = psycopg2.connect(
    host="nozomi.proxy.rlwy.net",
    port=39235,
    database="railway",
    user="postgres",
    password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp"
)

async def check_api_for_player(session, player_id, name):
    """Check all possible places where 2025 data might exist"""
    found_data = False
    milb_levels = []
    
    # Check game log for each level
    sport_ids = [11, 12, 13, 14]  # AAA, AA, High-A, Single-A
    sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}
    
    for sport_id in sport_ids:
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'gameLog',
            'season': 2025,
            'sportId': sport_id,
            'group': 'hitting'
        }
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'stats' in data and data['stats']:
                        for stat in data['stats']:
                            if 'splits' in stat and stat['splits']:
                                found_data = True
                                game_count = len(stat['splits'])
                                milb_levels.append(f"{sport_names[sport_id]}: {game_count} games")
                                print(f"  -> Found {game_count} games at {sport_names[sport_id]}")
        except Exception as e:
            continue
    
    return found_data, milb_levels

async def main():
    # Get batters with no 2025 data
    cur = conn.cursor()
    cur.execute("""
        SELECT p.mlb_player_id, p.name, p.position, p.organization
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position != 'P'
        AND NOT EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
        )
        ORDER BY p.name
        LIMIT 50
    """)
    
    missing = cur.fetchall()
    print(f"\nChecking {len(missing)} batters with 'no data' in database...\n")
    
    found_count = 0
    truly_missing_count = 0
    found_examples = []
    
    async with aiohttp.ClientSession() as session:
        for player_id, name, position, org in missing:
            print(f"\n{name} (ID: {player_id}, {position}, {org})")
            
            has_data, levels = await check_api_for_player(session, player_id, name)
            
            if has_data:
                found_count += 1
                found_examples.append(f"{name} ({player_id}): {', '.join(levels)}")
                print(f"  *** HAS DATA IN API BUT NOT IN DATABASE!")
            else:
                truly_missing_count += 1
                print(f"  -> Confirmed: No 2025 MiLB data in API")
            
            await asyncio.sleep(0.2)
    
    print(f"\n{'='*80}")
    print(f"SUMMARY OF {len(missing)} BATTERS:")
    print(f"  - Found in API (but not in DB): {found_count}")
    print(f"  - Truly missing from API: {truly_missing_count}")
    print(f"{'='*80}")
    
    if found_examples:
        print(f"\nEXAMPLES OF BATTERS WITH DATA IN API BUT NOT IN DB:")
        for example in found_examples[:10]:
            print(f"  - {example}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
