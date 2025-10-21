import asyncio
import aiohttp
import json

async def deep_debug():
    """Super detailed debugging of the extraction logic"""

    pitcher_id = 663795
    game_pk = 646839

    print("=" * 80)
    print("DEEP DEBUG OF EXTRACTION LOGIC")
    print("=" * 80)

    # Fetch play-by-play data
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            pbp_data = await response.json()

    plays = pbp_data['liveData']['plays']['allPlays']

    print(f"\nTotal plays in game: {len(plays)}")
    print(f"Looking for pitcher ID: {pitcher_id}")

    plays_for_pitcher = 0
    plays_with_pitch_events = 0
    plays_with_pitch_data = 0
    pitches = []

    for i, play in enumerate(plays):
        # Check structure
        if 'matchup' not in play:
            continue

        if 'pitcher' not in play['matchup']:
            continue

        # Get pitcher ID from play
        pitcher_in_play_id = play['matchup']['pitcher'].get('id')

        # Check if this is our pitcher
        if pitcher_in_play_id != pitcher_id:
            continue

        # If we get here, this play is for our pitcher
        plays_for_pitcher += 1

        if plays_for_pitcher <= 3:  # Log first 3 plays for our pitcher
            print(f"\n--- Play #{i} for our pitcher (match #{plays_for_pitcher}) ---")
            print(f"  Pitcher ID in play: {pitcher_in_play_id}")
            print(f"  Batter: {play['matchup'].get('batter', {}).get('fullName')}")

        # Get play events
        play_events = play.get('playEvents', [])
        if play_events:
            plays_with_pitch_events += 1
            if plays_for_pitcher <= 3:
                print(f"  Play Events Count: {len(play_events)}")

        # Check for pitch data
        for j, pitch_data in enumerate(play_events):
            is_pitch = pitch_data.get('isPitch')
            if is_pitch:
                pitch_details = pitch_data.get('pitchData', {})

                if plays_for_pitcher <= 3 and j == 0:  # Log first pitch of first 3 plays
                    print(f"  First pitch:")
                    print(f"    isPitch: {is_pitch}")
                    print(f"    pitchData exists: {bool(pitch_details)}")
                    if pitch_details:
                        print(f"    Pitch type: {pitch_details.get('typeDescription')}")
                        print(f"    Start speed: {pitch_details.get('startSpeed')}")

                if pitch_details:
                    plays_with_pitch_data += 1
                    pitches.append({
                        'pitch_number': pitch_data.get('pitchNumber'),
                        'pitch_type': pitch_details.get('typeDescription'),
                        'start_speed': pitch_details.get('startSpeed')
                    })

    print(f"\n" + "=" * 80)
    print("SUMMARY:")
    print(f"  Plays for pitcher: {plays_for_pitcher}")
    print(f"  Plays with pitch events: {plays_with_pitch_events}")
    print(f"  Plays with pitch data: {plays_with_pitch_data}")
    print(f"  Total pitches extracted: {len(pitches)}")
    print("=" * 80)

    if len(pitches) > 0:
        print(f"\nFirst few pitches:")
        for i, pitch in enumerate(pitches[:5]):
            print(f"  {i+1}. {pitch['pitch_type']} at {pitch['start_speed']} mph")
    else:
        print("\nNO PITCHES EXTRACTED!")
        if plays_for_pitcher > 0:
            print("  Plays found but no pitch data in playEvents!")

if __name__ == "__main__":
    asyncio.run(deep_debug())
