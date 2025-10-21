import psycopg2
import requests
import logging
from datetime import datetime
import time
import asyncio
import aiohttp
from typing import List, Dict, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Direct database connection
DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'

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

async def collect_pitch_data_for_player(session, player_id, name, rank, conn):
    """Collect pitch data for a player using their existing PBP game data"""
    cur = conn.cursor()

    logging.info(f"\n[Rank #{rank}] Collecting pitch data for {name} (ID: {player_id})")

    # Check if player already has pitch data
    cur.execute("""
        SELECT COUNT(*) FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
    """, (player_id,))

    existing_pitch_count = cur.fetchone()[0]
    if existing_pitch_count > 0:
        logging.info(f"  -> Already has {existing_pitch_count} pitches")
        cur.close()
        return 0

    # Get game PKs from existing PBP data
    cur.execute("""
        SELECT DISTINCT game_pk
        FROM milb_plate_appearances
        WHERE mlb_player_id = %s AND season = 2025
        ORDER BY game_pk
    """, (player_id,))

    game_pks = [row[0] for row in cur.fetchall()]

    if not game_pks:
        logging.info(f"  -> No PBP data found (needs PBP collection first)")
        cur.close()
        return 0

    logging.info(f"  -> Found {len(game_pks)} games with PBP data")

    total_pitches = 0
    games_processed = 0

    for i, game_pk in enumerate(game_pks, 1):
        # Fetch PBP data
        pbp_data = await fetch_pbp_data(session, game_pk)
        if not pbp_data:
            continue

        # Extract pitches
        pitches = extract_pitches(pbp_data, player_id)

        if pitches:
            # Insert into database
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

        games_processed += 1
        conn.commit()

        if (i % 10 == 0):
            logging.info(f"  -> Processed {i}/{len(game_pks)} games ({total_pitches} pitches so far)")

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    logging.info(f"  -> COMPLETE: {total_pitches} pitches from {games_processed} games")
    cur.close()

    return total_pitches

async def main():
    """Main collection process"""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    logging.info("\n" + "="*80)
    logging.info("TOP 200 PROSPECTS - PITCH DATA COLLECTION")
    logging.info("="*80)

    # Get top 200 prospects missing ONLY pitch data (have PBP already)
    cur.execute("""
        SELECT
            p.mlb_player_id,
            p.name,
            p.organization,
            pr.v7_rank as prospect_rank
        FROM prospects p
        INNER JOIN prospect_rankings_v7 pr ON pr.mlb_player_id = p.mlb_player_id AND pr.report_year = 2025
        WHERE p.mlb_player_id IS NOT NULL
        AND pr.v7_rank <= 200
        AND EXISTS (
            SELECT 1 FROM milb_plate_appearances mpa
            WHERE mpa.mlb_player_id = p.mlb_player_id::INTEGER AND mpa.season = 2025
        )
        AND NOT EXISTS (
            SELECT 1 FROM milb_batter_pitches mbp
            WHERE mbp.mlb_batter_id = p.mlb_player_id::INTEGER AND mbp.season = 2025
        )
        ORDER BY pr.v7_rank ASC
    """)

    missing_prospects = cur.fetchall()
    cur.close()

    logging.info(f"\nFound {len(missing_prospects)} top-200 prospects needing pitch data")

    if not missing_prospects:
        logging.info("\n>>> All top 200 prospects with PBP have pitch data!")
        conn.close()
        return

    # Display list
    logging.info(f"\n{'Rank':<6} {'Name':<30} {'Org':<5}")
    logging.info("-" * 45)
    for mlb_id, name, org, rank in missing_prospects:
        logging.info(f"{rank:<6} {name:<30} {org:<5}")

    logging.info("\n" + "="*80)
    logging.info("STARTING PITCH DATA COLLECTION")
    logging.info("="*80)

    total_pitches = 0
    successful = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        for i, (mlb_id, name, org, rank) in enumerate(missing_prospects, 1):
            try:
                pitches = await collect_pitch_data_for_player(session, int(mlb_id), name, rank, conn)
                total_pitches += pitches
                successful += 1

            except Exception as e:
                logging.error(f"ERROR processing {name}: {e}")
                failed += 1

            # Progress update every 5
            if i % 5 == 0 or i == len(missing_prospects):
                logging.info(f"\n{'='*60}")
                logging.info(f"PROGRESS: {i}/{len(missing_prospects)} prospects")
                logging.info(f"Successful: {successful} | Failed: {failed}")
                logging.info(f"Total pitches collected: {total_pitches:,}")
                logging.info(f"{'='*60}\n")

    conn.close()

    # Final summary
    logging.info("\n" + "="*80)
    logging.info("PITCH DATA COLLECTION COMPLETE")
    logging.info("="*80)
    logging.info(f"Prospects processed:   {len(missing_prospects)}")
    logging.info(f"Successful:            {successful}")
    logging.info(f"Failed:                {failed}")
    logging.info(f"Total pitches:         {total_pitches:,}")
    logging.info("="*80)

if __name__ == "__main__":
    asyncio.run(main())
