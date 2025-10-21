import asyncio
import aiohttp
import psycopg2
from datetime import datetime

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
    results = {
        'player_id': player_id,
        'name': name,
        'game_log_2025': False,
        'stats_2025': False,
        'milb_levels': []
    }
    
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
                                results['game_log_2025'] = True
                                results['milb_levels'].append({
                                    'level': sport_names[sport_id],
                                    'games': len(stat['splits'])
                                })
                                print(f"  ✓ Found {len(stat['splits'])} games at {sport_names[sport_id]}")
        except Exception as e:
            print(f"  ✗ Error checking {sport_names[sport_id]}: {e}")
            continue
    
    # Check season stats (aggregated)
    try:
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {
            'stats': 'season',
            'season': 2025,
            'group': 'hitting'
        }
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                if 'stats' in data and data['stats']:
                    for stat in data['stats']:
                        if 'splits' in stat and stat['splits']:
                            results['stats_2025'] = True
                            print(f"  ✓ Found 2025 season stats")
    except Exception as e:
        print(f"  ✗ Error checking season stats: {e}")
    
    return results

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
    
    async with aiohttp.ClientSession() as session:
        for player_id, name, position, org in missing:
            print(f"\nChecking {name} (ID: {player_id}, {position}, {org})")
            
            result = await check_api_for_player(session, player_id, name)
            
            if result['game_log_2025']:
                found_count += 1
                print(f"  ⚠️  HAS DATA IN API BUT NOT IN DATABASE!")
            else:
                truly_missing_count += 1
                print(f"  ℹ️  Confirmed: No 2025 MiLB data in API")
            
            await asyncio.sleep(0.2)  # Rate limiting
    
    print(f"\n" + "="*80)
    print(f"SUMMARY OF {len(missing)} BATTERS:")
    print(f"  - Found in API (but not in DB): {found_count}")
    print(f"  - Truly missing from API: {truly_missing_count}")
    print(f"="*80)
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
