import asyncio
import aiohttp
import psycopg2
import json

# Database connection
DB_CONFIG = {
    'host': 'nozomi.proxy.rlwy.net',
    'port': 39235,
    'database': 'railway',
    'user': 'postgres',
    'password': 'BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp'
}

async def investigate_pitcher_id_mismatch():
    """Investigate why pitcher IDs don't match in play-by-play data"""

    # Test pitcher from previous run
    pitcher_id = 663795
    pitcher_name = "Justin Hagenman"
    game_pk = 646839

    print("=" * 80)
    print(f"INVESTIGATING PITCHER ID MISMATCH")
    print(f"Pitcher: {pitcher_name} (ID from prospects table: {pitcher_id})")
    print(f"Game PK: {game_pk}")
    print("=" * 80)

    # Fetch play-by-play data
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()

    # Extract all unique pitcher IDs from this game
    plays = data['liveData']['plays']['allPlays']
    pitcher_ids_in_game = set()

    print(f"\nFound {len(plays)} plays in game")

    for play in plays:
        if 'matchup' in play and 'pitcher' in play['matchup']:
            pitcher_info = play['matchup']['pitcher']
            pitcher_id_in_play = pitcher_info.get('id')
            pitcher_name_in_play = pitcher_info.get('fullName')
            pitcher_ids_in_game.add((pitcher_id_in_play, pitcher_name_in_play))

    print(f"\nUnique pitchers in this game:")
    for pid, pname in sorted(pitcher_ids_in_game):
        print(f"  ID: {pid}, Name: {pname}")
        if "Hagenman" in pname:
            print(f"    ^^^ FOUND OUR PITCHER! But ID is {pid}, not {pitcher_id}")

    # Now check if our pitcher ID exists in the game at all
    if pitcher_id in [pid for pid, _ in pitcher_ids_in_game]:
        print(f"\n✓ Pitcher ID {pitcher_id} found in game")
    else:
        print(f"\n✗ Pitcher ID {pitcher_id} NOT found in game")
        print(f"  This means the mlb_player_id in prospects table doesn't match game data!")

    # Check the database to see what ID we have stored
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("""
        SELECT mlb_player_id, name, position
        FROM prospects
        WHERE mlb_player_id = %s
    """, (str(pitcher_id),))

    result = cur.fetchone()
    if result:
        db_id, db_name, db_pos = result
        print(f"\n" + "="*80)
        print("DATABASE RECORD:")
        print(f"  mlb_player_id: {db_id} (type: {type(db_id)})")
        print(f"  name: {db_name}")
        print(f"  position: {db_pos}")

    # Try to find if there's a different ID for this player
    print(f"\n" + "="*80)
    print("CHECKING FOR NAME MATCH IN GAME DATA VS DATABASE")
    print("="*80)

    for pid, pname in sorted(pitcher_ids_in_game):
        if "Hagenman" in pname:
            print(f"\nGame says: ID={pid}, Name='{pname}'")
            print(f"DB says:   ID={db_id}, Name='{db_name}'")

            if str(pid) != str(db_id):
                print(f"\n❌ MISMATCH! The IDs don't match!")
                print(f"   Game uses: {pid}")
                print(f"   DB has:    {db_id}")
            else:
                print(f"\n✓ IDs match")

    cur.close()
    conn.close()

    print("\n" + "="*80)
    print("INVESTIGATION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(investigate_pitcher_id_mismatch())
