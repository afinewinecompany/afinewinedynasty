"""Test the game logs backfill approach with Konnor Griffin"""
import asyncio
import aiohttp
import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def test_konnor():
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # Get Konnor's games
    cursor.execute("""
        SELECT game_pk, game_date, level, plate_appearances
        FROM milb_game_logs
        WHERE mlb_player_id = 804606
          AND season = 2025
          AND game_pk IS NOT NULL
        ORDER BY game_date
        LIMIT 5
    """)

    games = cursor.fetchall()
    print(f"\nFound {len(games)} games for Konnor Griffin (showing first 5)")

    async with aiohttp.ClientSession() as session:
        for game_pk, game_date, level, pa in games:
            print(f"\nGame {game_pk} ({game_date}) - {level}, {pa} PAs")

            url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 404:
                        print("  [X] Game not found (404)")
                        continue

                    if resp.status != 200:
                        print(f"  [X] Status {resp.status}")
                        continue

                    data = await resp.json()

                    all_plays = data.get('liveData', {}).get('plays', {}).get('allPlays', [])
                    print(f"  Total plays in game: {len(all_plays)}")

                    # Count pitches where Konnor was batting
                    konnor_pitches = 0
                    for play in all_plays:
                        matchup = play.get('matchup', {})
                        if matchup.get('batter', {}).get('id') == 804606:
                            play_events = play.get('playEvents', [])
                            for event in play_events:
                                if event.get('isPitch'):
                                    konnor_pitches += 1

                    print(f"  [OK] Pitches for Konnor: {konnor_pitches}")

            except Exception as e:
                print(f"  [ERR] Error: {e}")

            await asyncio.sleep(0.5)

    conn.close()

if __name__ == "__main__":
    asyncio.run(test_konnor())
