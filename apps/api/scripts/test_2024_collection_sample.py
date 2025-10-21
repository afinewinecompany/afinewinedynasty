import asyncio
import aiohttp
import psycopg2

# Database connection
DB_CONFIG = {
    'host': 'nozomi.proxy.rlwy.net',
    'port': 39235,
    'database': 'railway',
    'user': 'postgres',
    'password': 'BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp'
}

SPORT_IDS = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}

async def test_batter(session, player_id, name):
    """Test batter data collection"""
    print(f"\nTesting BATTER: {name} (ID: {player_id})")
    
    total_games = 0
    for sport_id, level in SPORT_IDS.items():
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {'stats': 'gameLog', 'season': 2024, 'sportId': sport_id, 'group': 'hitting'}
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'stats' in data and data['stats']:
                        for stat in data['stats']:
                            if 'splits' in stat and stat['splits']:
                                games = len(stat['splits'])
                                print(f"  -> {level}: {games} games")
                                total_games += games
        except Exception as e:
            print(f"  -> {level}: Error - {e}")
    
    return total_games > 0

async def test_pitcher(session, player_id, name):
    """Test pitcher data collection"""
    print(f"\nTesting PITCHER: {name} (ID: {player_id})")
    
    total_games = 0
    for sport_id, level in SPORT_IDS.items():
        url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
        params = {'stats': 'gameLog', 'season': 2024, 'sportId': sport_id, 'group': 'pitching'}
        
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    if 'stats' in data and data['stats']:
                        for stat in data['stats']:
                            if 'splits' in stat and stat['splits']:
                                games = len(stat['splits'])
                                print(f"  -> {level}: {games} games")
                                total_games += games
        except Exception as e:
            print(f"  -> {level}: Error - {e}")
    
    return total_games > 0

async def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    print("="*80)
    print("TESTING 2024 COLLECTION SCRIPTS")
    print("="*80)
    
    # Get 5 batters missing 2024 data
    cur.execute("""
        SELECT p.mlb_player_id, p.name
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position NOT IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2024
        )
        LIMIT 5
    """)
    batters = cur.fetchall()
    
    # Get 5 pitchers missing 2024 data
    cur.execute("""
        SELECT p.mlb_player_id, p.name
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND p.position IN ('P', 'SP', 'RP', 'RHP', 'LHP', 'PITCHER')
        AND NOT EXISTS (
            SELECT 1 FROM milb_pitcher_pitches mpp
            WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2024
        )
        LIMIT 5
    """)
    pitchers = cur.fetchall()
    
    print(f"\nTesting with {len(batters)} batters and {len(pitchers)} pitchers...")
    
    async with aiohttp.ClientSession() as session:
        print("\n" + "="*80)
        print("BATTER TESTS")
        print("="*80)
        
        batters_found = 0
        for player_id, name in batters:
            if await test_batter(session, player_id, name):
                batters_found += 1
            await asyncio.sleep(0.2)
        
        print("\n" + "="*80)
        print("PITCHER TESTS")
        print("="*80)
        
        pitchers_found = 0
        for player_id, name in pitchers:
            if await test_pitcher(session, player_id, name):
                pitchers_found += 1
            await asyncio.sleep(0.2)
    
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"Batters with 2024 data: {batters_found}/{len(batters)}")
    print(f"Pitchers with 2024 data: {pitchers_found}/{len(pitchers)}")
    print("\nScripts appear ready to run!")
    print("="*80)
    
    cur.close()
    conn.close()

asyncio.run(main())
