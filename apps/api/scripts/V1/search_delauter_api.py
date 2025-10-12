"""
Search for Chase DeLauter's data directly via MLB Stats API
"""
import statsapi
import json

def search_delauter():
    """Search for DeLauter's stats in MLB Stats API."""

    print("=" * 80)
    print("SEARCHING MLB STATS API FOR CHASE DELAUTER")
    print("=" * 80)

    # First, use the lookup function
    print("\n1. Looking up player...")
    players = statsapi.lookup_player('delauter, chase')

    if players:
        for player in players:
            print(f"\nFound: {player.get('fullName')}")
            print(f"  ID: {player.get('id')}")
            print(f"  Position: {player.get('primaryPosition', {}).get('name')}")
            print(f"  Current Team: {player.get('currentTeam', {}).get('name', 'N/A')}")

            player_id = player.get('id')

            # Try to get player stats for different seasons
            print(f"\n2. Checking stats for player ID {player_id}...")

            for season in [2023, 2024, 2025]:
                print(f"\n  {season} Season:")
                print("  " + "-" * 60)

                # Try season stats
                try:
                    stats_url = f'people/{player_id}/stats'
                    params = {
                        'stats': 'season',
                        'season': season,
                        'group': 'hitting'
                    }

                    # Using statsapi.get directly
                    season_stats = statsapi.get('people', {
                        'personId': player_id,
                        'season': season,
                        'hydrate': 'stats(group=[hitting],type=[season])'
                    })

                    if season_stats.get('people'):
                        person = season_stats['people'][0]
                        stats_list = person.get('stats', [])

                        for stat_group in stats_list:
                            splits = stat_group.get('splits', [])
                            for split in splits:
                                team = split.get('team', {}).get('name', 'Unknown')
                                league = split.get('league', {}).get('name', 'Unknown')
                                stat = split.get('stat', {})

                                games = stat.get('gamesPlayed', 0)
                                ab = stat.get('atBats', 0)
                                h = stat.get('hits', 0)
                                hr = stat.get('homeRuns', 0)
                                avg = stat.get('avg', '.000')

                                print(f"    {team} ({league}): {games} G, {ab} AB, {h} H, {hr} HR, {avg} AVG")

                except Exception as e:
                    print(f"    Error getting season stats: {e}")

                # Try game logs using the statsapi wrapper functions
                try:
                    # Use player_stat_data function
                    game_data = statsapi.player_stat_data(
                        player_id,
                        group='hitting',
                        type='gameLog',
                        season=season
                    )

                    if game_data:
                        # Parse the game data
                        lines = game_data.split('\n')
                        game_count = len([l for l in lines if l.strip() and not l.startswith('Date')])

                        if game_count > 0:
                            print(f"\n    Game Log Data ({game_count} games found):")

                            # Show first few lines
                            for i, line in enumerate(lines[:5]):
                                if line.strip():
                                    print(f"    {line}")

                except Exception as e:
                    print(f"    Error getting game logs: {e}")

    else:
        print("Player not found")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    search_delauter()