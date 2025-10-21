import asyncio
import aiohttp
import psycopg2

conn = psycopg2.connect(
    host="nozomi.proxy.rlwy.net",
    port=39235,
    database="railway",
    user="postgres",
    password="BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp"
)

async def check_player(session, player_id, name):
    """Check if player has 2025 data"""
    sport_ids = [11, 12, 13, 14]
    
    for sport_id in sport_ids:
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {'stats': 'gameLog', 'season': 2025, 'sportId': sport_id, 'group': 'hitting'}
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'stats' in data and data['stats']:
                        for stat in data['stats']:
                            if 'splits' in stat and stat['splits']:
                                return True, len(stat['splits'])
        except:
            continue
    return False, 0

async def main():
    cur = conn.cursor()
    
    # Get DH prospects with no data
    cur.execute("""
        SELECT p.mlb_player_id, p.name
        FROM prospects p
        WHERE p.position = 'DH'
        AND p.mlb_player_id IS NOT NULL
        AND NOT EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
        )
        LIMIT 30
    """)
    
    dh_prospects = cur.fetchall()
    print(f"\nChecking {len(dh_prospects)} DH prospects...\n")
    
    has_data = 0
    no_data = 0
    
    async with aiohttp.ClientSession() as session:
        for player_id, name in dh_prospects:
            found, games = await check_player(session, player_id, name)
            if found:
                has_data += 1
                print(f"  HAS DATA: {name} ({player_id}) - {games} games")
            else:
                no_data += 1
            await asyncio.sleep(0.1)
    
    print(f"\n{'='*60}")
    print(f"DH PROSPECTS SAMPLE:")
    print(f"  Has data in API: {has_data}")
    print(f"  No data in API: {no_data}")
    print(f"{'='*60}")
    
    cur.close()
    conn.close()

asyncio.run(main())
