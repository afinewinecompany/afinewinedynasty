import asyncio
import aiohttp
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

async def fetch_game_log_for_level(session, player_id, season, sport_id):
    """Fetch player's game log for a specific sport level"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'sportId': sport_id,
        'group': 'hitting'
    }

    logging.info(f"  Fetching {player_id} season {season} sport {sport_id}...")

    try:
        async with session.get(url, params=params) as response:
            logging.info(f"    Response status: {response.status}")
            if response.status == 200:
                data = await response.json()
                if 'stats' in data and data['stats']:
                    for stat in data['stats']:
                        if 'splits' in stat:
                            logging.info(f"    Found {len(stat['splits'])} games")
                            return stat['splits']
            return []
    except Exception as e:
        logging.error(f"Error fetching game log for {player_id} sportId {sport_id}: {e}")
        return []

async def test_boston_baro():
    """Test collection for Boston Baro"""
    player_id = 805951
    logging.info(f"\nTesting async collection for Boston Baro (ID: {player_id})")

    async with aiohttp.ClientSession() as session:
        sport_ids = [11, 12, 13, 14]
        sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}

        all_games = []
        for sport_id in sport_ids:
            games = await fetch_game_log_for_level(session, player_id, 2025, sport_id)
            if games:
                logging.info(f"  -> Found {len(games)} games at {sport_names[sport_id]}")
                all_games.extend(games)
            await asyncio.sleep(0.2)

        logging.info(f"\nTotal games found: {len(all_games)}")

        if all_games:
            logging.info("\nFirst game details:")
            first = all_games[0]
            logging.info(f"  Date: {first.get('date')}")
            logging.info(f"  Game PK: {first.get('game', {}).get('gamePk')}")
            logging.info(f"  Team: {first.get('team', {}).get('name')}")

if __name__ == "__main__":
    asyncio.run(test_boston_baro())
