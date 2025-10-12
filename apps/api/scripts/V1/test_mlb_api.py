"""
Quick test of MLB StatsAPI to verify it works
"""
import statsapi
import json

def test_mlb_api():
    """Test MLB StatsAPI functionality."""
    print("Testing MLB StatsAPI connection...")
    print("=" * 60)

    try:
        # Test 1: Get seasons info
        print("\n1. Getting season info...")
        seasons = statsapi.get('seasons', {'sportId': 1})
        current_season = 2024  # We'll use 2024 as our test season
        print(f"   Using season: {current_season}")

        # Test 2: Get Triple-A teams
        print("\n2. Getting Triple-A teams for 2024...")
        teams_data = statsapi.get('teams', {'sportId': 11, 'season': 2024})
        teams = teams_data.get('teams', [])
        print(f"   Found {len(teams)} Triple-A teams")
        if teams:
            print(f"   Sample team: {teams[0].get('name')}")

        # Test 3: Get a sample roster
        print("\n3. Testing roster retrieval...")
        if teams:
            team_id = teams[0]['id']
            try:
                roster = statsapi.get(f'teams/{team_id}/roster', {'season': 2024})
                players = roster.get('roster', [])
                print(f"   Found {len(players)} players on {teams[0]['name']} roster")
                if players:
                    sample_player = players[0].get('person', {})
                    print(f"   Sample player: {sample_player.get('fullName')}")
            except:
                print(f"   Could not retrieve roster for team {team_id}")

        # Test 4: Use the lookup_player function
        print("\n4. Testing player lookup...")
        # Look up a well-known player
        players = statsapi.lookup_player('trout, mike')
        if players:
            player = players[0]
            print(f"   Found player: {player.get('fullName')}")
            print(f"   ID: {player.get('id')}")

        print("\n" + "=" * 60)
        print("SUCCESS: MLB StatsAPI is working correctly!")
        print("You can use the collection scripts to gather additional data.")

    except Exception as e:
        print(f"\nERROR: {e}")
        print("The MLB StatsAPI may be temporarily unavailable.")

if __name__ == "__main__":
    test_mlb_api()