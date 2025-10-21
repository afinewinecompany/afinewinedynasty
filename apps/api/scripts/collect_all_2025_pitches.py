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
                    'balls': details.get('ballColor', '').count('green'),
                    'strikes': details.get('strikeColor', '').count('red'),
                    'created_at': datetime.now()
                }

                pitches.append(pitch)

    return pitches

async def collect_player_pitches(session, player_id, name, conn):
    """Collect pitch data for a single player"""
    cur = conn.cursor()

    # Check if player already has 2025 pitch data
    cur.execute("""
        SELECT COUNT(*) FROM milb_batter_pitches
        WHERE mlb_batter_id = %s AND season = 2025
    """, (player_id,))

    if cur.fetchone()[0] > 0:
        logging.info(f"  {name}: Already has 2025 pitch data, skipping")
        cur.close()
        return 0

    # Get game PKs from PBP table
    cur.execute("""
        SELECT DISTINCT game_pk, game_date
        FROM milb_plate_appearances
        WHERE mlb_player_id = %s AND season = 2025
        ORDER BY game_date
    """, (player_id,))

    game_pks = [row[0] for row in cur.fetchall()]

    if not game_pks:
        logging.info(f"  {name}: No games to process")
        cur.close()
        return 0

    total_pitches = 0

    for game_pk in game_pks:
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
                    logging.error(f"Error inserting pitch for {name}: {e}")

    conn.commit()
    logging.info(f"  {name}: Collected {total_pitches} pitches from {len(game_pks)} games")
    cur.close()
    return total_pitches

async def collect_batch(players: List[Tuple], batch_num: int, total_batches: int):
    """Collect pitch data for a batch of players"""
    conn = psycopg2.connect(DB_URL)

    logging.info(f"\n=== BATCH {batch_num}/{total_batches}: {len(players)} players ===")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for player_id, name, team, pa_count in players:
            tasks.append(collect_player_pitches(session, int(player_id), name, conn))

            # Limit concurrent requests
            if len(tasks) >= 5:
                results = await asyncio.gather(*tasks)
                total = sum(results)
                logging.info(f"  Batch progress: {total} pitches collected")
                tasks = []
                await asyncio.sleep(1)  # Rate limiting

        # Process remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks)
            total = sum(results)
            logging.info(f"  Batch complete: {total} pitches collected")

    conn.close()

def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE 2025 PITCH COLLECTION")
    print(f"Started: {datetime.now()}")
    print("="*70)

    # Load prospects needing pitch data
    prospects = []
    with open('needs_2025_pitch.txt', 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 4:
                prospects.append((parts[0], parts[1], parts[2], parts[3]))

    print(f"\nTotal prospects to collect: {len(prospects)}")

    # Sort by PA count (process larger ones first)
    prospects.sort(key=lambda x: int(x[3]), reverse=True)

    # Process in batches
    batch_size = 10  # Smaller batches for pitch data
    batches = [prospects[i:i+batch_size] for i in range(0, len(prospects), batch_size)]

    for i, batch in enumerate(batches, 1):
        asyncio.run(collect_batch(batch, i, len(batches)))

        # Progress report
        if i % 5 == 0:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2025")
            total = cur.fetchone()[0]
            conn.close()
            print(f"\n[PROGRESS] Completed {i}/{len(batches)} batches. Total 2025 pitch records: {total:,}")

    # Final report
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM milb_batter_pitches WHERE season = 2025")
    final_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT mlb_batter_id) FROM milb_batter_pitches WHERE season = 2025")
    unique_players = cur.fetchone()[0]
    conn.close()

    print("\n" + "="*70)
    print("COLLECTION COMPLETE")
    print(f"Total 2025 pitch records: {final_total:,}")
    print(f"Unique players with data: {unique_players:,}")
    print(f"Ended: {datetime.now()}")
    print("="*70)

if __name__ == "__main__":
    main()