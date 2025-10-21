"""
Fixed pitch-by-pitch collection with correct table structure
"""

import requests
import time
from datetime import datetime
from sqlalchemy import create_engine, text
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
engine = create_engine(DB_URL)

# Top prospects to collect
PRIORITY_PROSPECTS = [
    {'rank': 1, 'name': 'Konnor Griffin', 'mlb_id': 804606},
    {'rank': 2, 'name': 'Kevin McGonigle', 'mlb_id': 805808},
    {'rank': 3, 'name': 'Jesus Made', 'mlb_id': 815908},
    {'rank': 6, 'name': 'Samuel Basallo', 'mlb_id': 694212},
    {'rank': 7, 'name': 'Bryce Eldridge', 'mlb_id': 805811},
]

def get_recent_games(conn, player_id):
    """Get recent games for a player"""

    result = conn.execute(text("""
        SELECT DISTINCT game_pk, game_date, level
        FROM milb_plate_appearances
        WHERE mlb_player_id = :player_id
        AND season IN (2024, 2025)
        ORDER BY game_date DESC
        LIMIT 10
    """), {'player_id': player_id})

    return [(row[0], row[1], row[2]) for row in result]

def fetch_game_data(game_pk):
    """Fetch game data with pitches"""

    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error fetching game {game_pk}: {e}")
        return None

def process_pitches(game_data, player_id, game_pk, game_date, level):
    """Extract and save pitch data"""

    pitches_saved = 0

    if not game_data:
        return 0

    plays = game_data.get('liveData', {}).get('plays', {}).get('allPlays', [])

    with engine.begin() as conn:  # Use transaction
        for play in plays:
            matchup = play.get('matchup', {})
            batter_id = matchup.get('batter', {}).get('id')
            pitcher_id = matchup.get('pitcher', {}).get('id')

            # Only process if our player is the batter
            if batter_id != player_id:
                continue

            at_bat_index = play.get('atBatIndex', 0)
            about = play.get('about', {})
            inning = about.get('inning', 0)
            half_inning = about.get('halfInning', '')

            play_events = play.get('playEvents', [])

            for pitch_idx, event in enumerate(play_events):
                if not event.get('isPitch', False):
                    continue

                details = event.get('details', {})
                pitch_data = event.get('pitchData', {})

                # Map to correct column names
                try:
                    conn.execute(text("""
                        INSERT INTO milb_batter_pitches (
                            mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season, level,
                            at_bat_index, pitch_number, inning, half_inning,
                            pitch_type, pitch_type_description,
                            start_speed, spin_rate, zone,
                            pitch_call, pitch_result,
                            is_strike, balls, strikes,
                            created_at
                        ) VALUES (
                            :batter_id, :pitcher_id, :game_pk, :game_date, :season, :level,
                            :at_bat_index, :pitch_number, :inning, :half_inning,
                            :pitch_type, :pitch_type_desc,
                            :start_speed, :spin_rate, :zone,
                            :pitch_call, :pitch_result,
                            :is_strike, :balls, :strikes,
                            NOW()
                        )
                        ON CONFLICT (mlb_batter_id, game_pk, at_bat_index, pitch_number)
                        DO NOTHING
                    """), {
                        'batter_id': batter_id,
                        'pitcher_id': pitcher_id,
                        'game_pk': game_pk,
                        'game_date': game_date,
                        'season': int(str(game_date)[:4]),
                        'level': level or 'AA',
                        'at_bat_index': at_bat_index,
                        'pitch_number': pitch_idx + 1,
                        'inning': inning,
                        'half_inning': half_inning[:10] if half_inning else '',
                        'pitch_type': details.get('type', {}).get('code', '')[:10],
                        'pitch_type_desc': details.get('type', {}).get('description', '')[:100],
                        'start_speed': pitch_data.get('startSpeed'),
                        'spin_rate': pitch_data.get('breaks', {}).get('spinRate'),
                        'zone': pitch_data.get('zone'),
                        'pitch_call': details.get('call', {}).get('code', '')[:10],
                        'pitch_result': details.get('call', {}).get('description', '')[:100],
                        'is_strike': details.get('isStrike', False),
                        'balls': details.get('count', {}).get('balls', 0),
                        'strikes': details.get('count', {}).get('strikes', 0)
                    })

                    pitches_saved += 1

                except Exception as e:
                    logger.error(f"Error saving pitch: {e}")

    return pitches_saved

def collect_for_player(player_id, player_name, rank):
    """Collect pitch data for a player"""

    logger.info(f"Collecting for Rank #{rank}: {player_name}")

    total_games = 0
    total_pitches = 0

    with engine.connect() as conn:
        games = get_recent_games(conn, player_id)

        if not games:
            logger.info(f"  No games found")
            return 0, 0

        logger.info(f"  Found {len(games)} recent games")

        for game_pk, game_date, level in games:
            game_data = fetch_game_data(game_pk)

            if game_data:
                pitches = process_pitches(game_data, player_id, game_pk, game_date, level)

                if pitches > 0:
                    total_pitches += pitches
                    total_games += 1
                    logger.info(f"    Game {game_pk}: {pitches} pitches saved")

            time.sleep(0.5)  # Rate limiting

    logger.info(f"  Total: {total_games} games, {total_pitches} pitches")

    return total_games, total_pitches

def main():
    print("=" * 70)
    print("PITCH COLLECTION (FIXED)")
    print(f"Started: {datetime.now()}")
    print("=" * 70)

    start_time = time.time()
    stats = {'players': 0, 'games': 0, 'pitches': 0}

    for prospect in PRIORITY_PROSPECTS:
        try:
            games, pitches = collect_for_player(
                prospect['mlb_id'],
                prospect['name'],
                prospect['rank']
            )

            stats['players'] += 1
            stats['games'] += games
            stats['pitches'] += pitches

            time.sleep(2)  # Delay between players

        except Exception as e:
            logger.error(f"Error with {prospect['name']}: {e}")

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("COLLECTION COMPLETE")
    print("=" * 70)
    print(f"Players: {stats['players']}")
    print(f"Games: {stats['games']}")
    print(f"Pitches: {stats['pitches']}")
    print(f"Time: {elapsed/60:.1f} minutes")

    # Verify
    print("\n=== VERIFYING ===")

    with engine.connect() as conn:
        for prospect in PRIORITY_PROSPECTS:
            result = conn.execute(text("""
                SELECT COUNT(DISTINCT game_pk) as games, COUNT(*) as pitches
                FROM milb_batter_pitches
                WHERE mlb_batter_id = :player_id
                AND season IN (2024, 2025)
            """), {'player_id': prospect['mlb_id']})

            row = result.fetchone()
            if row and row[1] > 0:
                print(f"[SUCCESS] Rank #{prospect['rank']}: {prospect['name']}")
                print(f"  {row[0]} games, {row[1]} pitches")
            else:
                print(f"[NO DATA] Rank #{prospect['rank']}: {prospect['name']}")

if __name__ == "__main__":
    main()