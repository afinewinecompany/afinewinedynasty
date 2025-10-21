import psycopg2
import logging
from datetime import datetime
import asyncio
import aiohttp
from aiohttp import ClientTimeout, ClientError

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0
API_TIMEOUT = 30

async def fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count=0):
    """Fetch pitcher's game log for a specific sport level with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'sportId': sport_id,
        'group': 'pitching'  # PITCHING stats!
    }

    try:
        async with session.get(url, params=params, timeout=ClientTimeout(total=API_TIMEOUT)) as response:
            if response.status == 200:
                data = await response.json()
                if 'stats' in data and data['stats']:
                    for stat in data['stats']:
                        if 'splits' in stat:
                            return stat['splits']
                return []
            elif response.status == 429:  # Rate limited
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    logging.warning(f"Rate limited for pitcher {player_id}, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    return await fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
                else:
                    logging.error(f"Max retries reached for pitcher {player_id}, sport {sport_id}")
                    return []
            else:
                logging.error(f"HTTP {response.status} for pitcher {player_id}, sport {sport_id}")
                return []
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            logging.warning(f"Timeout for pitcher {player_id} sport {sport_id}, retry {retry_count + 1}/{MAX_RETRIES}")
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_pitching_game_log_for_level(session, player_id, season, sport_id, retry_count + 1)
        else:
            logging.error(f"Timeout after {MAX_RETRIES} retries for pitcher {player_id}")
            return []
    except ClientError as e:
        logging.error(f"Client error fetching pitching log for {player_id} sportId {sport_id}: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error fetching pitching log for {player_id} sportId {sport_id}: {e}")
        return []

async def fetch_pbp_data(session, game_pk, retry_count=0):
    """Fetch play-by-play data with retry logic"""
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

    try:
        async with session.get(url, timeout=ClientTimeout(total=API_TIMEOUT)) as response:
            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                if retry_count < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retry_count)
                    await asyncio.sleep(wait_time)
                    return await fetch_pbp_data(session, game_pk, retry_count + 1)
            return None
    except asyncio.TimeoutError:
        if retry_count < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY)
            return await fetch_pbp_data(session, game_pk, retry_count + 1)
        return None
    except Exception as e:
        logging.error(f"Error fetching PBP for game {game_pk}: {e}")
        return None

def extract_pitcher_appearances(game_log_splits, player_id):
    """Extract pitcher appearance stats from game log"""
    appearances = []

    for split in game_log_splits:
        game = split.get('game', {})
        stat = split.get('stat', {})

        appearance = {
            'mlb_player_id': player_id,
            'game_pk': game.get('gamePk'),
            'game_date': split.get('date'),
            'season': split.get('season'),
            'level': game.get('gameType', ''),
            'innings_pitched': stat.get('inningsPitched'),
            'hits': stat.get('hits'),
            'runs': stat.get('runs'),
            'earned_runs': stat.get('earnedRuns'),
            'walks': stat.get('walks'),
            'strikeouts': stat.get('strikeOuts'),
            'home_runs': stat.get('homeRuns'),
            'pitches_thrown': stat.get('numberOfPitches'),
            'strikes': stat.get('strikes'),
            'balls': None,
            'batters_faced': stat.get('battersFaced'),
            'team_id': split.get('team', {}).get('id'),
            'opponent_id': split.get('opponent', {}).get('id'),
            'is_home': split.get('isHome'),
            'game_type': game.get('type'),
            'decision': stat.get('decision'),
            'created_at': datetime.now()
        }

        appearances.append(appearance)

    return appearances

def extract_pitcher_pitches(pbp_data, pitcher_id):
    """Extract pitch data when this player was pitching"""
    pitches = []

    if not pbp_data or 'liveData' not in pbp_data:
        return pitches

    plays = pbp_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
    game_pk = pbp_data.get('gamePk')
    game_date = pbp_data.get('gameData', {}).get('datetime', {}).get('officialDate')
    season = pbp_data.get('gameData', {}).get('game', {}).get('season')

    for play in plays:
        if 'matchup' not in play or 'pitcher' not in play['matchup']:
            continue

        if play['matchup']['pitcher'].get('id') != pitcher_id:
            continue

        about = play.get('about', {})
        batter_id = play['matchup'].get('batter', {}).get('id')
        play_events = play.get('playEvents', [])

        for event in play_events:
            if event.get('isPitch'):
                details = event.get('details', {})
                pitch_data = event.get('pitchData', {})

                pitch = {
                    'mlb_pitcher_id': pitcher_id,
                    'mlb_batter_id': batter_id,
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
                    'balls': details.get('count', {}).get('balls', 0),
                    'strikes': details.get('count', {}).get('strikes', 0),
                    'created_at': datetime.now()
                }

                pitches.append(pitch)

    return pitches

async def collect_pitcher_data(session, player_id, name, position, rank, conn):
    """Collect complete pitching data for a pitcher prospect"""

    cur = conn.cursor()

    # Check if already has complete data
    cur.execute("""
        SELECT
            EXISTS(SELECT 1 FROM milb_pitcher_appearances WHERE mlb_player_id = %s AND season = 2025) as has_appearances,
            EXISTS(SELECT 1 FROM milb_pitcher_pitches WHERE mlb_pitcher_id = %s AND season = 2025) as has_pitches,
            (SELECT COUNT(*) FROM milb_pitcher_appearances WHERE mlb_player_id = %s AND season = 2025) as appearance_count,
            (SELECT COUNT(*) FROM milb_pitcher_pitches WHERE mlb_pitcher_id = %s AND season = 2025) as pitch_count
    """, (player_id, player_id, player_id, player_id))

    has_appearances, has_pitches, appearance_count, pitch_count = cur.fetchone()

    rank_str = f"#{rank}" if rank else "Unranked"

    if has_appearances and has_pitches and appearance_count > 0 and pitch_count > 0:
        logging.info(f"  {name} ({position}) - Already complete ({appearance_count} games, {pitch_count} pitches)")
        return True, 0, 0

    logging.info(f"\nCollecting: {name} ({position}, {rank_str}, ID: {player_id})")

    # Query each MiLB level separately with retry logic
    sport_ids = [11, 12, 13, 14]  # AAA, AA, High-A, Single-A
    sport_names = {11: 'AAA', 12: 'AA', 13: 'High-A', 14: 'Single-A'}

    all_games = []
    api_call_success = False

    for sport_id in sport_ids:
        games = await fetch_pitching_game_log_for_level(session, player_id, 2025, sport_id)
        if games is not None:
            api_call_success = True
            if games:
                logging.info(f"  -> Found {len(games)} games at {sport_names[sport_id]}")
                all_games.extend(games)
        await asyncio.sleep(0.3)

    if not api_call_success:
        logging.error(f"  -> ALL API CALLS FAILED for {name}!")
        return False, 0, 0

    if not all_games:
        logging.info(f"  -> No 2025 MiLB pitching games found")
        return True, 0, 0

    logging.info(f"  -> Total games: {len(all_games)}")

    # Extract and store pitcher appearances
    appearances = extract_pitcher_appearances(all_games, player_id)

    if appearances:
        for app in appearances:
            try:
                cur.execute("""
                    INSERT INTO milb_pitcher_appearances (
                        mlb_player_id, game_pk, game_date, season, level,
                        innings_pitched, hits, runs, earned_runs, walks, strikeouts,
                        home_runs, pitches_thrown, strikes, batters_faced,
                        team_id, opponent_id, is_home, game_type, decision, created_at
                    ) VALUES (
                        %(mlb_player_id)s, %(game_pk)s, %(game_date)s, %(season)s, %(level)s,
                        %(innings_pitched)s, %(hits)s, %(runs)s, %(earned_runs)s, %(walks)s,
                        %(strikeouts)s, %(home_runs)s, %(pitches_thrown)s, %(strikes)s,
                        %(batters_faced)s, %(team_id)s, %(opponent_id)s, %(is_home)s,
                        %(game_type)s, %(decision)s, %(created_at)s
                    )
                    ON CONFLICT (mlb_player_id, game_pk, season) DO NOTHING
                """, app)
            except Exception as e:
                logging.error(f"Error inserting pitcher appearance: {e}")

        conn.commit()

    # Collect pitch-by-pitch data
    total_pitches = 0
    game_pks = [app['game_pk'] for app in appearances]

    for idx, game_pk in enumerate(game_pks, 1):
        pbp_data = await fetch_pbp_data(session, game_pk)

        if pbp_data:
            pitches = extract_pitcher_pitches(pbp_data, player_id)

            if pitches:
                for pitch in pitches:
                    try:
                        cur.execute("""
                            INSERT INTO milb_pitcher_pitches (
                                mlb_pitcher_id, mlb_batter_id, game_pk, game_date, season, level,
                                at_bat_index, pitch_number, inning, pitch_type, start_speed,
                                spin_rate, zone, pitch_call, pitch_result, is_strike,
                                balls, strikes, created_at
                            ) VALUES (
                                %(mlb_pitcher_id)s, %(mlb_batter_id)s, %(game_pk)s, %(game_date)s,
                                %(season)s, %(level)s, %(at_bat_index)s, %(pitch_number)s,
                                %(inning)s, %(pitch_type)s, %(start_speed)s, %(spin_rate)s,
                                %(zone)s, %(pitch_call)s, %(pitch_result)s, %(is_strike)s,
                                %(balls)s, %(strikes)s, %(created_at)s
                            )
                            ON CONFLICT DO NOTHING
                        """, pitch)
                        total_pitches += 1
                    except Exception as e:
                        logging.error(f"Error inserting pitcher pitch: {e}")

        conn.commit()

        if idx % 10 == 0:
            logging.info(f"  -> Processed {idx}/{len(game_pks)} games ({total_pitches} pitches so far)")

        await asyncio.sleep(0.5)

    logging.info(f"  -> COMPLETE: {len(appearances)} games, {total_pitches} pitches")

    return True, len(appearances), total_pitches

async def main():
    """Main collection function"""

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("ROBUST PITCHER DATA COLLECTION - WITH RETRY LOGIC")
    logging.info("="*80)

    # Get all pitcher prospects missing 2025 data
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.position,
            pr.v7_rank,
            p.organization,
            EXISTS(SELECT 1 FROM milb_pitcher_appearances mpa WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025) as has_appearances,
            EXISTS(SELECT 1 FROM milb_pitcher_pitches mpp WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2025) as has_pitches
        FROM prospects p
        LEFT JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id
        WHERE p.position IN ('P', 'RHP', 'LHP', 'SP', 'RP', 'PITCHER')
        AND p.mlb_player_id IS NOT NULL
        AND (
            NOT EXISTS(SELECT 1 FROM milb_pitcher_appearances mpa WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025)
            OR NOT EXISTS(SELECT 1 FROM milb_pitcher_pitches mpp WHERE mpp.mlb_pitcher_id = p.mlb_player_id::INTEGER AND mpp.season = 2025)
        )
        ORDER BY COALESCE(pr.v7_rank, 9999), p.name
    """)

    pitchers = cur.fetchall()
    cur.close()

    logging.info(f"\nFound {len(pitchers)} pitchers needing 2025 data collection")

    missing_both = sum(1 for p in pitchers if not p[5] and not p[6])
    missing_appearances_only = sum(1 for p in pitchers if not p[5] and p[6])
    missing_pitches_only = sum(1 for p in pitchers if p[5] and not p[6])

    logging.info(f"\nBreakdown:")
    logging.info(f"  Missing BOTH appearances and pitches: {missing_both}")
    logging.info(f"  Missing appearances only: {missing_appearances_only}")
    logging.info(f"  Missing pitches only: {missing_pitches_only}")

    logging.info("\n" + "="*80)
    logging.info("STARTING COLLECTION")
    logging.info("="*80)

    successful = 0
    no_data = 0
    failed = 0
    total_appearances = 0
    total_pitches = 0

    # Create session with connection pooling
    connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
    timeout = ClientTimeout(total=60, connect=10, sock_read=30)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        for idx, (mlb_id, name, pos, rank, org, has_app, has_pitch) in enumerate(pitchers, 1):
            try:
                success, game_count, pitch_count = await collect_pitcher_data(
                    session, int(mlb_id), name, pos, rank, conn
                )

                if success:
                    if game_count > 0 or pitch_count > 0:
                        successful += 1
                        total_appearances += game_count
                        total_pitches += pitch_count
                    else:
                        no_data += 1
                else:
                    failed += 1

            except Exception as e:
                logging.error(f"ERROR collecting data for {name}: {e}")
                failed += 1

            # Progress update every 25 pitchers
            if idx % 25 == 0:
                logging.info("\n" + "="*70)
                logging.info(f"PROGRESS: {idx}/{len(pitchers)} pitchers")
                logging.info(f"Successful: {successful} | No Data: {no_data} | Failed: {failed}")
                logging.info(f"Total: {total_appearances} games, {total_pitches:,} pitches")
                logging.info("="*70 + "\n")

    # Final summary
    logging.info("\n" + "="*80)
    logging.info("COLLECTION COMPLETE")
    logging.info("="*80)
    logging.info(f"Pitchers processed:    {len(pitchers)}")
    logging.info(f"Successful:            {successful}")
    logging.info(f"No data available:     {no_data}")
    logging.info(f"Failed:                {failed}")
    logging.info(f"Total games collected: {total_appearances}")
    logging.info(f"Total pitches:         {total_pitches:,}")
    logging.info("="*80)

    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
