"""
Collect pitch-by-pitch data for priority prospects
Focus on prospects that already have PBP data but need pitch data
"""

import requests
import time
import json
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(f'pitch_collection_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Priority prospects needing pitch data (top ranked!)
PRIORITY_PITCH_COLLECTION = [
    {'rank': 1, 'name': 'Konnor Griffin', 'mlb_id': 804606},
    {'rank': 2, 'name': 'Kevin McGonigle', 'mlb_id': 805808},
    {'rank': 3, 'name': 'Jesus Made', 'mlb_id': 815908},
    {'rank': 4, 'name': 'Leo De Vries', 'mlb_id': 815888},
    {'rank': 6, 'name': 'Samuel Basallo', 'mlb_id': 694212},
    {'rank': 7, 'name': 'Bryce Eldridge', 'mlb_id': 805811},
    {'rank': 8, 'name': 'JJ Wetherholt', 'mlb_id': 802139},
    {'rank': 10, 'name': 'Walker Jenkins', 'mlb_id': 805805},
    {'rank': 11, 'name': 'Max Clark', 'mlb_id': 703601},
    {'rank': 12, 'name': 'Aidan Miller', 'mlb_id': 805795},
]

def get_player_games(conn, player_id, season):
    """Get games for a player from existing PBP data"""

    result = conn.execute(text("""
        SELECT DISTINCT game_pk, game_date
        FROM milb_plate_appearances
        WHERE mlb_player_id = :player_id
        AND season = :season
        ORDER BY game_date DESC
        LIMIT 20
    """), {'player_id': player_id, 'season': season})

    return [(row[0], row[1]) for row in result]

def fetch_game_pitches(game_pk):
    """Fetch detailed pitch data for a game"""

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get('liveData', {}).get('plays', {}).get('allPlays', [])
        return []
    except Exception as e:
        logger.error(f"Error fetching pitches for game {game_pk}: {e}")
        return []

def extract_pitch_data(play, player_id):
    """Extract pitch data from a play"""

    pitches = []
    matchup = play.get('matchup', {})
    batter_id = matchup.get('batter', {}).get('id')
    pitcher_id = matchup.get('pitcher', {}).get('id')

    # Check if our player is involved
    is_batter = (batter_id == player_id)
    is_pitcher = (pitcher_id == player_id)

    if not (is_batter or is_pitcher):
        return pitches

    at_bat_index = play.get('atBatIndex', 0)
    play_events = play.get('playEvents', [])

    for pitch_idx, event in enumerate(play_events):
        if event.get('isPitch', False):
            pitch_data = event.get('pitchData', {})
            details = event.get('details', {})

            pitch = {
                'at_bat_index': at_bat_index,
                'pitch_number': pitch_idx + 1,
                'pitch_type': details.get('type', {}).get('code', ''),
                'pitch_speed': pitch_data.get('startSpeed'),
                'spin_rate': pitch_data.get('breaks', {}).get('spinRate'),
                'call': details.get('call', {}).get('code', ''),
                'description': details.get('description', ''),
                'zone': pitch_data.get('zone'),
                'is_batter': is_batter,
                'is_pitcher': is_pitcher,
                'batter_id': batter_id,
                'pitcher_id': pitcher_id
            }
            pitches.append(pitch)

    return pitches

def save_pitch_data(conn, player_id, game_pk, game_date, pitch_data):
    """Save pitch data to database"""

    try:
        if pitch_data['is_batter']:
            # Save as batter pitch
            conn.execute(text("""
                INSERT INTO milb_batter_pitches
                (mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                 at_bat_index, pitch_number, pitch_type, pitch_speed,
                 call_code, call_description, zone, created_at)
                VALUES
                (:batter_id, :pitcher_id, :game_pk, :game_date, :season,
                 :at_bat_index, :pitch_number, :pitch_type, :pitch_speed,
                 :call, :description, :zone, NOW())
                ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_number)
                DO NOTHING
            """), {
                'batter_id': player_id,
                'pitcher_id': pitch_data['pitcher_id'],
                'game_pk': game_pk,
                'game_date': game_date,
                'season': int(str(game_date)[:4]),
                'at_bat_index': pitch_data['at_bat_index'],
                'pitch_number': pitch_data['pitch_number'],
                'pitch_type': pitch_data['pitch_type'],
                'pitch_speed': pitch_data['pitch_speed'],
                'call': pitch_data['call'],
                'description': pitch_data['description'],
                'zone': pitch_data['zone']
            })

        if pitch_data['is_pitcher']:
            # Save as pitcher pitch
            conn.execute(text("""
                INSERT INTO milb_pitcher_pitches
                (mlb_pitcher_id, mlb_batter_id, game_pk, game_date, season,
                 at_bat_index, pitch_number, pitch_type, pitch_speed,
                 call_code, call_description, zone, created_at)
                VALUES
                (:pitcher_id, :batter_id, :game_pk, :game_date, :season,
                 :at_bat_index, :pitch_number, :pitch_type, :pitch_speed,
                 :call, :description, :zone, NOW())
                ON CONFLICT (mlb_pitcher_id, game_pk, at_bat_index, pitch_number)
                DO NOTHING
            """), {
                'pitcher_id': player_id,
                'batter_id': pitch_data['batter_id'],
                'game_pk': game_pk,
                'game_date': game_date,
                'season': int(str(game_date)[:4]),
                'at_bat_index': pitch_data['at_bat_index'],
                'pitch_number': pitch_data['pitch_number'],
                'pitch_type': pitch_data['pitch_type'],
                'pitch_speed': pitch_data['pitch_speed'],
                'call': pitch_data['call'],
                'description': pitch_data['description'],
                'zone': pitch_data['zone']
            })

        return True

    except Exception as e:
        logger.error(f"Error saving pitch: {e}")
        return False

def collect_pitches_for_player(player_id, player_name, rank):
    """Collect pitch data for a player"""

    logger.info(f"Collecting pitches for Rank #{rank}: {player_name}")

    with engine.connect() as conn:
        total_games = 0
        total_pitches = 0

        for season in [2025, 2024]:
            # Get games where player has PBP data
            games = get_player_games(conn, player_id, season)

            if not games:
                logger.info(f"  No games found for {season}")
                continue

            logger.info(f"  Processing {len(games)} games from {season}")

            for game_pk, game_date in games[:10]:  # Process first 10 games
                plays = fetch_game_pitches(game_pk)

                game_pitches = 0
                for play in plays:
                    pitches = extract_pitch_data(play, player_id)

                    for pitch in pitches:
                        if save_pitch_data(conn, player_id, game_pk, game_date, pitch):
                            game_pitches += 1

                if game_pitches > 0:
                    total_pitches += game_pitches
                    total_games += 1
                    logger.info(f"    Game {game_pk}: {game_pitches} pitches")

                # Rate limiting
                time.sleep(0.5)

            # Commit after each season
            conn.commit()

        logger.info(f"  Total: {total_games} games, {total_pitches} pitches collected")

        return total_games, total_pitches

def main():
    """Main collection function"""

    print("=" * 70)
    print("PITCH-BY-PITCH COLLECTION FOR TOP PROSPECTS")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    start_time = time.time()
    stats = {
        'players': 0,
        'games': 0,
        'pitches': 0,
        'errors': 0
    }

    # Collect for priority prospects
    for prospect in PRIORITY_PITCH_COLLECTION[:5]:  # Start with top 5
        try:
            games, pitches = collect_pitches_for_player(
                prospect['mlb_id'],
                prospect['name'],
                prospect['rank']
            )

            stats['players'] += 1
            stats['games'] += games
            stats['pitches'] += pitches

            # Delay between players
            time.sleep(2)

        except Exception as e:
            logger.error(f"Error processing {prospect['name']}: {e}")
            stats['errors'] += 1

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("COLLECTION COMPLETE")
    print("=" * 70)
    print(f"Players processed: {stats['players']}")
    print(f"Games with pitches: {stats['games']}")
    print(f"Total pitches: {stats['pitches']}")
    print(f"Errors: {stats['errors']}")
    print(f"Time: {elapsed/60:.1f} minutes")

    # Verify in database
    print("\n=== VERIFYING PITCH DATA ===")

    with engine.connect() as conn:
        for prospect in PRIORITY_PITCH_COLLECTION[:5]:
            result = conn.execute(text("""
                SELECT
                    COUNT(DISTINCT game_pk) as games,
                    COUNT(*) as pitches
                FROM milb_batter_pitches
                WHERE mlb_batter_id = :player_id
                AND season IN (2024, 2025)
            """), {'player_id': prospect['mlb_id']})

            row = result.fetchone()
            if row and row[1] > 0:
                print(f"[SUCCESS] Rank #{prospect['rank']}: {prospect['name']}")
                print(f"  {row[0]} games, {row[1]} pitches")
            else:
                # Check pitcher pitches
                result = conn.execute(text("""
                    SELECT
                        COUNT(DISTINCT game_pk) as games,
                        COUNT(*) as pitches
                    FROM milb_pitcher_pitches
                    WHERE mlb_pitcher_id = :player_id
                    AND season IN (2024, 2025)
                """), {'player_id': prospect['mlb_id']})

                row = result.fetchone()
                if row and row[1] > 0:
                    print(f"[SUCCESS] Rank #{prospect['rank']}: {prospect['name']} (as pitcher)")
                    print(f"  {row[0]} games, {row[1]} pitches")
                else:
                    print(f"[NO DATA] Rank #{prospect['rank']}: {prospect['name']}")

    print("\nPitch collection complete! Check logs for details.")

if __name__ == "__main__":
    main()