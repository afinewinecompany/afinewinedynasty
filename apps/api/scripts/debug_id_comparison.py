import asyncio
import aiohttp

async def debug_id_comparison():
    """Debug why ID comparison is failing"""

    pitcher_id = 663795  # This is what we pass to the function (INTEGER)
    game_pk = 646839

    print("=" * 80)
    print("DEBUGGING ID COMPARISON LOGIC")
    print("=" * 80)

    # Fetch play-by-play data
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

    plays = data['liveData']['plays']['allPlays']

    print(f"\nLooking for pitcher_id: {pitcher_id} (type: {type(pitcher_id)})")

    matches = 0
    first_pitcher_id_found = None

    for i, play in enumerate(plays):
        if 'matchup' not in play or 'pitcher' not in play['matchup']:
            continue

        pitcher_in_play = play['matchup']['pitcher']
        pitcher_id_in_play = pitcher_in_play.get('id')

        if first_pitcher_id_found is None:
            first_pitcher_id_found = pitcher_id_in_play
            print(f"\nFirst pitcher ID in play data: {pitcher_id_in_play} (type: {type(pitcher_id_in_play)})")

        # Check the comparison
        if pitcher_id_in_play == pitcher_id:
            matches += 1
            if matches == 1:  # Log first match
                print(f"\nMATCH FOUND at play {i}!")
                print(f"  pitcher_id_in_play: {pitcher_id_in_play}")
                print(f"  pitcher_id (param):  {pitcher_id}")
                print(f"  Equality test: {pitcher_id_in_play == pitcher_id}")
                print(f"  Pitcher name: {pitcher_in_play.get('fullName')}")

    print(f"\nTotal matches found: {matches}")

    if matches == 0:
        print("\nNO MATCHES FOUND!")
        print("This is the actual problem - the comparison is failing")
        print(f"\nComparison details:")
        print(f"  pitcher_id (param): {pitcher_id}, type: {type(pitcher_id)}")
        print(f"  Example from play:  {first_pitcher_id_found}, type: {type(first_pitcher_id_found)}")
        print(f"  Are they equal? {first_pitcher_id_found == pitcher_id}")

    print("\n" + "=" * 80)
    print("DEBUG COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(debug_id_comparison())
