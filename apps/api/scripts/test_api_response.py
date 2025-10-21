import requests
import json

# Test with Boston Baro who we KNOW has 103 High-A games
player_id = 805951
sport_id = 13  # High-A

url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
params = {
    'stats': 'gameLog',
    'season': 2025,
    'sportId': sport_id,
    'group': 'hitting'
}

print(f"Testing API call for Boston Baro (ID: {player_id})")
print(f"URL: {url}")
print(f"Params: {params}")
print("\n" + "="*80)

response = requests.get(url, params=params)
print(f"Status Code: {response.status_code}")
print("\n" + "="*80)

if response.status_code == 200:
    data = response.json()
    print("Response structure:")
    print(json.dumps(data, indent=2)[:2000])  # First 2000 chars

    print("\n" + "="*80)
    print("Checking for stats...")
    if 'stats' in data:
        print(f"'stats' key found: {len(data['stats'])} entries")
        for i, stat in enumerate(data['stats']):
            print(f"\nStat #{i}:")
            print(f"  Type: {stat.get('type', {}).get('displayName')}")
            print(f"  Group: {stat.get('group', {}).get('displayName')}")
            if 'splits' in stat:
                print(f"  Splits: {len(stat['splits'])} games")
                if stat['splits']:
                    first_game = stat['splits'][0]
                    print(f"  First game date: {first_game.get('date')}")
                    print(f"  First game PK: {first_game.get('game', {}).get('gamePk')}")
    else:
        print("No 'stats' key in response!")
else:
    print(f"Error response: {response.text}")
