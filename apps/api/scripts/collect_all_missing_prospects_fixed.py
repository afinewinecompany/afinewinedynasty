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
        'sportId': sport_id,  # ONE level at a time - THE FIX!
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

async def collect_player_data_fixed(session, player_id, name, conn):
    """Collect both PBP and Pitch data - FIXED to query each level separately"""
    cur = conn.cursor()

    logging.info(f"\nCollecting data for {name} (ID: {player_id})")

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
        logging.info(f"  -> Already complete ({existing_pbp} PAs, {existing_pitch} pitches)")
        cur.close()
        return {'pbp': 0, 'pitches': 0}

    total_pbp = 0
    total_pitches = 0
    all_game_pks = set()

    # Query EACH MiLB level separately
    sport_ids = [11, 12, 13, 14]  # AAA, AA, High-A, Single-A
    sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}

    for sport_id in sport_ids:
        games = await fetch_game_log_for_level(session, player_id, 2025, sport_id)
        if games:
            logging.info(f"  -> Found {len(games)} games at {sport_names[sport_id]}")
            for g in games:
                if 'game' in g:
                    all_game_pks.add(g['game'].get('gamePk'))
        await asyncio.sleep(0.2)

    if not all_game_pks:
        logging.info(f"  -> No 2025 MiLB games found")
        cur.close()
        return {'pbp': 0, 'pitches': 0}

    game_pks = list(all_game_pks)
    logging.info(f"  -> Total games: {len(game_pks)}")

    for i, game_pk in enumerate(game_pks, 1):
        if not game_pk:
            continue

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

        if (i % 20 == 0):
            logging.info(f"  -> Processed {i}/{len(game_pks)} games ({total_pbp} PAs, {total_pitches} pitches)")

        await asyncio.sleep(0.3)

    logging.info(f"  -> COMPLETE: {total_pbp} PAs, {total_pitches} pitches")
    cur.close()

    return {'pbp': total_pbp, 'pitches': total_pitches}

async def main():
    """Main collection process for ALL prospects missing 2025 data"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("ALL PROSPECTS - COMPREHENSIVE 2025 DATA COLLECTION (FIXED)")
    logging.info("="*80)

    # Get ALL prospects missing EITHER PBP or Pitch data for 2025
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.organization,
            EXISTS(SELECT 1 FROM milb_plate_appearances mpa
                   WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_pbp,
            EXISTS(SELECT 1 FROM milb_batter_pitches mbp
                   WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025) as has_pitch
        FROM prospects p
        WHERE p.mlb_player_id IS NOT NULL
        AND (
            NOT EXISTS (
                SELECT 1 FROM milb_plate_appearances mpa
                WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
            )
            OR NOT EXISTS (
                SELECT 1 FROM milb_batter_pitches mbp
                WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025
            )
        )
        ORDER BY p.organization, p.name
    """)

    missing_prospects = cur.fetchall()
    cur.close()

    logging.info(f"\nFound {len(missing_prospects)} prospects missing 2025 data")

    if not missing_prospects:
        logging.info("\n>>> All prospects have complete 2025 data!")
        conn.close()
        return

    # Categorize
    missing_both = [p for p in missing_prospects if not p[3] and not p[4]]
    missing_pitch_only = [p for p in missing_prospects if p[3] and not p[4]]

    logging.info(f"\nBreakdown:")
    logging.info(f"  Missing BOTH PBP and Pitch: {len(missing_both)}")
    logging.info(f"  Missing Pitch only: {len(missing_pitch_only)}")

    logging.info("\n" + "="*80)
    logging.info("STARTING COLLECTION")
    logging.info("="*80)

    total_pbp = 0
    total_pitches = 0
    successful = 0
    no_data = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        for i, (mlb_id, name, org, has_pbp, has_pitch) in enumerate(missing_prospects, 1):
            try:
                result = await collect_player_data_fixed(session, int(mlb_id), name, conn)

                if result['pbp'] == 0 and result['pitches'] == 0:
                    no_data += 1
                else:
                    total_pbp += result['pbp']
                    total_pitches += result['pitches']
                    successful += 1

            except Exception as e:
                logging.error(f"ERROR processing {name}: {e}")
                failed += 1

            # Progress update every 10
            if i % 10 == 0 or i == len(missing_prospects):
                logging.info(f"\n{'='*70}")
                logging.info(f"PROGRESS: {i}/{len(missing_prospects)} prospects")
                logging.info(f"Successful: {successful} | No Data: {no_data} | Failed: {failed}")
                logging.info(f"Total: {total_pbp:,} PAs, {total_pitches:,} pitches")
                logging.info(f"{'='*70}\n")

    conn.close()

    # Final summary
    logging.info("\n" + "="*80)
    logging.info("COLLECTION COMPLETE")
    logging.info("="*80)
    logging.info(f"Prospects processed:   {len(missing_prospects)}")
    logging.info(f"Successful:            {successful}")
    logging.info(f"No data available:     {no_data}")
    logging.info(f"Failed:                {failed}")
    logging.info(f"Total PAs collected:   {total_pbp:,}")
    logging.info(f"Total pitches:         {total_pitches:,}")
    logging.info("="*80)

if __name__ == "__main__":
    asyncio.run(main())
