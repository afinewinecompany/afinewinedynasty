"""
Direct collection script for priority prospects
Uses direct database connection to Railway
"""

import requests
import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(f'direct_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Priority prospects
PRIORITY_PROSPECTS = [
    {'rank': 6, 'name': 'Samuel Basallo', 'mlb_id': 694212},
    {'rank': 7, 'name': 'Bryce Eldridge', 'mlb_id': 805811},
    {'rank': 1, 'name': 'Konnor Griffin', 'mlb_id': 804606},
    {'rank': 2, 'name': 'Kevin McGonigle', 'mlb_id': 805808},
    {'rank': 3, 'name': 'Jesus Made', 'mlb_id': 815908},
]

def fetch_player_games(player_id, year):
    """Fetch games for a player in a specific year"""

    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': year,
        'group': 'hitting,pitching',
        'sportIds': '11,12,13,14,15,16'  # All MiLB levels
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            return []

        data = response.json()
        games = []

        for stat_group in data.get('stats', []):
            for split in stat_group.get('splits', []):
                game = split.get('game', {})
                if game.get('gamePk'):
                    games.append({
                        'game_pk': game['gamePk'],
                        'date': split.get('date'),
                        'team': split.get('team', {}).get('name'),
                        'stat': split.get('stat', {})
                    })

        return games

    except Exception as e:
        logger.error(f"Error fetching games: {e}")
        return []

def fetch_pbp_data(game_pk):
    """Fetch play-by-play data for a game"""

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error fetching PBP for game {game_pk}: {e}")
        return None

def save_plate_appearance(conn, player_id, game_pk, game_date, pa_data):
    """Save a plate appearance to the database"""

    try:
        conn.execute(text("""
            INSERT INTO milb_plate_appearances
            (mlb_player_id, game_pk, game_date, season, level, at_bat_index,
             event_type, description, created_at)
            VALUES
            (:player_id, :game_pk, :game_date, :season, :level, :at_bat_index,
             :event_type, :description, NOW())
            ON CONFLICT (mlb_player_id, game_pk, at_bat_index) DO NOTHING
        """), {
            'player_id': player_id,
            'game_pk': game_pk,
            'game_date': game_date,
            'season': int(game_date[:4]),
            'level': pa_data.get('level', 'AA'),
            'at_bat_index': pa_data.get('at_bat_index', 0),
            'event_type': pa_data.get('event_type', ''),
            'description': pa_data.get('description', '')
        })
        return True
    except Exception as e:
        logger.error(f"Error saving PA: {e}")
        return False

def collect_for_player(player_id, player_name, rank):
    """Collect data for a single player"""

    logger.info(f"Collecting for Rank #{rank}: {player_name} (ID: {player_id})")

    with engine.connect() as conn:
        total_games = 0
        total_pas = 0

        for year in [2024, 2025]:
            logger.info(f"  Year {year}...")

            # Get games
            games = fetch_player_games(player_id, year)
            logger.info(f"    Found {len(games)} games")

            if not games:
                continue

            # Process first 10 games as test
            for game_data in games[:10]:
                game_pk = game_data['game_pk']
                game_date = game_data['date']

                # Fetch PBP data
                pbp = fetch_pbp_data(game_pk)
                if not pbp:
                    continue

                # Extract plate appearances
                plays = pbp.get('liveData', {}).get('plays', {}).get('allPlays', [])

                game_pas = 0
                for idx, play in enumerate(plays):
                    matchup = play.get('matchup', {})
                    batter_id = matchup.get('batter', {}).get('id')

                    if batter_id == player_id:
                        result = play.get('result', {})
                        pa_data = {
                            'at_bat_index': idx,
                            'event_type': result.get('event', ''),
                            'description': result.get('description', ''),
                            'level': 'AA'  # Would need to determine actual level
                        }

                        if save_plate_appearance(conn, player_id, game_pk, game_date, pa_data):
                            game_pas += 1

                if game_pas > 0:
                    total_pas += game_pas
                    total_games += 1

                # Rate limiting
                time.sleep(0.5)

            # Commit after each year
            conn.commit()

        logger.info(f"  Total: {total_games} games, {total_pas} PAs collected")

        return total_games, total_pas

def main():
    """Main collection function"""

    print("=" * 70)
    print("DIRECT PRIORITY COLLECTION")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    start_time = time.time()
    total_stats = {'games': 0, 'pas': 0}

    # Test with first 3 prospects
    for prospect in PRIORITY_PROSPECTS[:3]:
        games, pas = collect_for_player(
            prospect['mlb_id'],
            prospect['name'],
            prospect['rank']
        )

        total_stats['games'] += games
        total_stats['pas'] += pas

        # Delay between players
        time.sleep(2)

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("COLLECTION COMPLETE")
    print("=" * 70)
    print(f"Total games: {total_stats['games']}")
    print(f"Total PAs: {total_stats['pas']}")
    print(f"Time: {elapsed/60:.1f} minutes")

    # Verify in database
    print("\n=== VERIFYING DATABASE ===")

    with engine.connect() as conn:
        for prospect in PRIORITY_PROSPECTS[:3]:
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT game_pk) as games, COUNT(*) as pas
                FROM milb_plate_appearances
                WHERE mlb_player_id = :player_id
                AND season IN (2024, 2025)
            """), {'player_id': prospect['mlb_id']})

            row = result.fetchone()
            if row and row[0] > 0:
                print(f"✓ {prospect['name']}: {row[0]} games, {row[1]} PAs")
            else:
                print(f"✗ {prospect['name']}: No data")

if __name__ == "__main__":
    main()