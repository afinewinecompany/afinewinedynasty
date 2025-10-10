"""
Check MLB Stats API directly (not using the Python wrapper) for DeLauter's data
"""
import requests
import json

def check_delauter_api_direct():
    """Check DeLauter's stats using direct API calls."""

    player_id = 800050  # Chase DeLauter
    base_url = "https://statsapi.mlb.com/api/v1"

    print("=" * 80)
    print("CHECKING MLB STATS API DIRECTLY FOR CHASE DELAUTER")
    print("=" * 80)

    # Check each season
    for season in [2023, 2024, 2025]:
        print(f"\n{season} SEASON:")
        print("-" * 80)

        # Get hitting game logs
        url = f"{base_url}/people/{player_id}/stats"
        params = {
            'stats': 'gameLog',
            'season': season,
            'group': 'hitting'
        }

        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()

                # Parse stats
                stats_list = data.get('stats', [])
                total_games = 0

                for stat_group in stats_list:
                    if stat_group.get('type', {}).get('displayName') == 'gameLog':
                        splits = stat_group.get('splits', [])
                        total_games = len(splits)

                        if splits:
                            # Group by team/level
                            teams = {}
                            for split in splits:
                                team_name = split.get('team', {}).get('name', 'Unknown')
                                if team_name not in teams:
                                    teams[team_name] = []
                                teams[team_name].append(split)

                            print(f"Total games in API: {total_games}")
                            print("\nBreakdown by team:")
                            for team_name, games in teams.items():
                                print(f"  {team_name}: {len(games)} games")

                                # Show first game details
                                if games:
                                    first_game = games[0]
                                    stat = first_game.get('stat', {})
                                    date = first_game.get('date', 'N/A')
                                    print(f"    First game: {date}")
                                    print(f"    Stats: {stat.get('atBats', 0)} AB, {stat.get('hits', 0)} H, {stat.get('homeRuns', 0)} HR")
                        else:
                            print(f"No game logs found")

            else:
                print(f"API Error: {response.status_code}")

        except Exception as e:
            print(f"Error: {e}")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_delauter_api_direct()