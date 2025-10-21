import psycopg2
import logging
from datetime import datetime
import asyncio
import aiohttp

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

async def fetch_game_log_for_level(session, player_id, season, sport_id):
    """Fetch player's game log for a specific sport level"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'sportId': sport_id,  # Query ONE level at a time!
        'group': 'hitting'
    }

    try:
        async with session.get(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if 'stats' in data and data['stats']:
                    for stat in data['stats']:
                        if 'splits' in stat:
                            return stat['splits']
            return []
    except Exception as e:
        logging.error(f"Error fetching game log for {player_id} sportId {sport_id}: {e}")
        return []

async def fetch_pbp_data(session, game_pk):
    """Fetch play-by-play data for a game"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        logging.error(f"Error fetching PBP for game {game_pk}: {e}")
    return None

def extract_plate_appearances(pbp_data, player_id):
    """Extract plate appearances for a player from PBP data"""
    plate_appearances = []

    if not pbp_data or 'liveData' not in pbp_data:
        return plate_appearances

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')

    for play in plays:
        if 'matchup' in play and 'batter' in play['matchup']:
            if play['matchup']['batter'].get('id') == player_id:
                about = play.get('about', {})
                result = play.get('result', {})

                pa = {
                    'mlb_player_id': player_id,
                    'game_pk': game_pk,
                    'game_date': game_date,
                    'season': 2025,
                    'level': pbp_data.get('gameData', {}).get('game', {}).get('type', ''),
                    'at_bat_index': about.get('atBatIndex', 0),
                    'inning': about.get('inning', 0),
                    'half_inning': about.get('halfInning', ''),
                    'event_type': result.get('eventType', ''),
                    'event_type_desc': result.get('event', ''),
                    'description': result.get('description', ''),
                    'launch_speed': None,
                    'launch_angle': None,
                    'total_distance': None,
                    'created_at': datetime.now()
                }

                # Extract hit data if available
                if 'hitData' in play:
                    hit_data = play['hitData']
                    pa['launch_speed'] = hit_data.get('launchSpeed')
                    pa['launch_angle'] = hit_data.get('launchAngle')
                    pa['total_distance'] = hit_data.get('totalDistance')

                plate_appearances.append(pa)

    return plate_appearances

def extract_pitches(pbp_data, player_id):
    """Extract pitch data for a batter from PBP data"""
    pitches = []

    if not pbp_data or 'liveData' not in pbp_data:
        return pitches

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')
    season = 2025

    for play in plays:
        if 'matchup' not in play or 'batter' not in play['matchup']:
            continue

        if play['matchup']['batter'].get('id') != player_id:
            continue

        about = play.get('about', {})
        pitcher_id = play['matchup'].get('pitcher', {}).get('id')

        # Get pitch sequence from playEvents
        play_events = play.get('playEvents', [])

        for event in play_events:
            if event.get('isPitch'):
                details = event.get('details', {})
                pitch_data = event.get('pitchData', {})

                pitch = {
                    'mlb_batter_id': player_id,
                    'mlb_pitcher_id': pitcher_id,
                    'game_pk': game_pk,
                    'game_date': game_date,
                    'season': season,
                    'level': pbp_data.get('gameData', {}).get('game', {}).get('type', ''),
                    'at_bat_index': about.get('atBatIndex', 0),
                    'pitch_number': event.get('pitchNumber', 0),
                    'inning': about.get('inning', 0),
                    'pitch_type': details.get('type', {}).get('code', ''),
                    'start_speed': pitch_data.get('startSpeed'),
                    'spin_rate': pitch_data.get('breaks', {}).get('spinRate'),
                    'zone': pitch_data.get('zone'),
                    'pitch_call': details.get('call', {}).get('code', ''),
                    'pitch_result': details.get('description', ''),
                    'is_strike': details.get('isStrike', False),
                    'balls': details.get('ballColor', '').count('green') if details.get('ballColor') else 0,
                    'strikes': details.get('strikeColor', '').count('red') if details.get('strikeColor') else 0,
                    'created_at': datetime.now()
                }

                pitches.append(pitch)

    return pitches

async def collect_full_player_data_fixed(session, player_id, name, rank, conn):
    """Collect both PBP and Pitch data - FIXED to query each level separately"""
    cur = conn.cursor()

    logging.info(f"\n[Rank #{rank}] Collecting FULL data for {name} (ID: {player_id})")

    # Check existing data
    cur.execute("""
        SELECT COUNT(*) FROM milb_plate_appearances
        WHERE mlb_player_id = %s AND season = 2025
    """, (player_id,))
    existing_pbp = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
    """, (player_id,))
    existing_pitch = cur.fetchone()[0]

    if existing_pbp > 0 and existing_pitch > 0:
        logging.info(f"  -> Already has complete data ({existing_pbp} PAs, {existing_pitch} pitches)")
        cur.close()
        return {'pbp': 0, 'pitches': 0}

    total_pbp = 0
    total_pitches = 0
    all_game_pks = set()

    # Query EACH MiLB level separately (this is the fix!)
    sport_ids = [11, 12, 13, 14]  # AAA, AA, High-A, Single-A
    sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}

    for sport_id in sport_ids:
        games = await fetch_game_log_for_level(session, player_id, 2025, sport_id)
        if games:
            logging.info(f"  -> Found {len(games)} games at {sport_names[sport_id]}")
            for g in games:
                if 'game' in g:
                    all_game_pks.add(g['game'].get('gamePk'))
        await asyncio.sleep(0.3)  # Small delay between levels

    if not all_game_pks:
        logging.info(f"  -> No 2025 MiLB games found across all levels")
        cur.close()
        return {'pbp': 0, 'pitches': 0}

    game_pks = list(all_game_pks)
    logging.info(f"  -> Total unique games found: {len(game_pks)}")

    for i, game_pk in enumerate(game_pks, 1):
        if not game_pk:
            continue

        # Fetch PBP data
        pbp_data = await fetch_pbp_data(session, game_pk)
        if not pbp_data:
            continue

        # Extract and save plate appearances
        pas = extract_plate_appearances(pbp_data, player_id)
        for pa in pas:
            try:
                cur.execute("""
                    INSERT INTO milb_plate_appearances (
                        mlb_player_id, game_pk, game_date, season, level,
                        at_bat_index, inning, half_inning, event_type, event_type_desc,
                        description, launch_speed, launch_angle, total_distance,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    ) ON CONFLICT DO NOTHING
                """, (
                    pa['mlb_player_id'], pa['game_pk'], pa['game_date'], pa['season'],
                    pa['level'], pa['at_bat_index'], pa['inning'], pa['half_inning'],
                    pa['event_type'], pa['event_type_desc'], pa['description'],
                    pa['launch_speed'], pa['launch_angle'], pa['total_distance'],
                    pa['created_at']
                ))
                total_pbp += 1
            except Exception as e:
                logging.error(f"Error inserting PA: {e}")

        # Extract and save pitches
        pitches = extract_pitches(pbp_data, player_id)
        for pitch in pitches:
            try:
                cur.execute("""
                    INSERT INTO milb_batter_pitches (
                        mlb_batter_id, mlb_pitcher_id, game_pk, game_date, season,
                        level, at_bat_index, pitch_number, inning,
                        pitch_type, start_speed, spin_rate, zone,
                        pitch_call, pitch_result, is_strike,
                        balls, strikes, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT DO NOTHING
                """, (
                    pitch['mlb_batter_id'], pitch['mlb_pitcher_id'], pitch['game_pk'],
                    pitch['game_date'], pitch['season'], pitch['level'],
                    pitch['at_bat_index'], pitch['pitch_number'], pitch['inning'],
                    pitch['pitch_type'], pitch['start_speed'], pitch['spin_rate'],
                    pitch['zone'], pitch['pitch_call'], pitch['pitch_result'],
                    pitch['is_strike'], pitch['balls'], pitch['strikes'], pitch['created_at']
                ))
                total_pitches += 1
            except Exception as e:
                logging.error(f"Error inserting pitch: {e}")

        conn.commit()

        if (i % 10 == 0):
            logging.info(f"  -> Processed {i}/{len(game_pks)} games ({total_pbp} PAs, {total_pitches} pitches)")

        # Rate limiting
        await asyncio.sleep(0.5)

    logging.info(f"  -> COMPLETE: {total_pbp} PAs, {total_pitches} pitches from {len(game_pks)} games")
    cur.close()

    return {'pbp': total_pbp, 'pitches': total_pitches}

async def main():
    """Main collection process for the 10 prospects with the FIXED API calls"""
    conn = psycopg2.connect(DB_URL)

    logging.info("\n" + "="*80)
    logging.info("TOP 200 PROSPECTS - FIXED COLLECTION (Query each level separately)")
    logging.info("="*80)

    # The 10 prospects that were missing
    prospects = [
        (700246, 'Carson Williams', 'TBR', 31),
        (691181, 'Emmanuel Rodriguez', 'MIN', 45),
        (703197, 'Michael Arroyo', 'SEA', 48),
        (682634, 'Kevin Alcantara', 'CHC', 78),
        (695600, 'Carter Jensen', 'KCR', 118),
        (694208, 'Moises Ballesteros', 'CHC', 128),
        (702679, 'Demetrio Crisantes', 'ARI', 146),
        (690997, 'Nolan McLean', 'NYM', 162),
        (690976, 'Alex Freeland', 'LAD', 163),
        (691620, 'Jeferson Quero', 'MIL', 192),
    ]

    logging.info(f"\nCollecting data for {len(prospects)} top-200 prospects")

    logging.info(f"\n{'Rank':<6} {'Name':<30} {'Org':<5}")
    logging.info("-" * 45)
    for player_id, name, org, rank in prospects:
        logging.info(f"{rank:<6} {name:<30} {org:<5}")

    logging.info("\n" + "="*80)
    logging.info("STARTING FIXED COLLECTION")
    logging.info("="*80)

    total_pbp = 0
    total_pitches = 0
    successful = 0
    failed = 0
    no_data = 0

    async with aiohttp.ClientSession() as session:
        for i, (player_id, name, org, rank) in enumerate(prospects, 1):
            try:
                result = await collect_full_player_data_fixed(session, player_id, name, rank, conn)

                if result['pbp'] == 0 and result['pitches'] == 0:
                    no_data += 1
                else:
                    total_pbp += result['pbp']
                    total_pitches += result['pitches']
                    successful += 1

            except Exception as e:
                logging.error(f"ERROR processing {name}: {e}")
                failed += 1

            # Progress update every 3
            if i % 3 == 0 or i == len(prospects):
                logging.info(f"\n{'='*60}")
                logging.info(f"PROGRESS: {i}/{len(prospects)} prospects")
                logging.info(f"Successful: {successful} | No Data: {no_data} | Failed: {failed}")
                logging.info(f"Total collected: {total_pbp:,} PAs, {total_pitches:,} pitches")
                logging.info(f"{'='*60}\n")

    conn.close()

    # Final summary
    logging.info("\n" + "="*80)
    logging.info("FIXED COLLECTION COMPLETE")
    logging.info("="*80)
    logging.info(f"Prospects processed:   {len(prospects)}")
    logging.info(f"Successful:            {successful}")
    logging.info(f"No data available:     {no_data}")
    logging.info(f"Failed:                {failed}")
    logging.info(f"Total PAs collected:   {total_pbp:,}")
    logging.info(f"Total pitches:         {total_pitches:,}")
    logging.info("="*80)

if __name__ == "__main__":
    asyncio.run(main())
