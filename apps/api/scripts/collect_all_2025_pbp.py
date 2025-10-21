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

async def fetch_game_log(session, player_id, season):
    """Fetch player's game log for a season"""
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'sportId': '11,12,13,14',  # All MiLB levels
        'hydrate': 'gameType'
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
        logging.error(f"Error fetching game log for {player_id}: {e}")
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
                    'venue_name': pbp_data.get('gameData', {}).get('venue', {}).get('name', ''),
                    'team': pbp_data.get('gameData', {}).get('teams', {}).get('home' if about.get('halfInning') == 'top' else 'away', {}).get('name', ''),
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

async def collect_player_pbp(session, player_id, name, conn):
    """Collect PBP data for a single player"""
    cur = conn.cursor()

    # Check if player already has 2025 data
    cur.execute("""
        SELECT COUNT(*) FROM milb_plate_appearances
        WHERE mlb_player_id = %s AND season = 2025
    """, (player_id,))

    if cur.fetchone()[0] > 0:
        logging.info(f"  {name}: Already has 2025 data, skipping")
        cur.close()
        return 0

    # Fetch game log
    games = await fetch_game_log(session, player_id, 2025)

    if not games:
        logging.info(f"  {name}: No 2025 games found")
        cur.close()
        return 0

    total_pas = 0
    game_pks = list(set([g.get('game', {}).get('gamePk') for g in games if 'game' in g]))

    for game_pk in game_pks:
        if not game_pk:
            continue

        # Fetch PBP data
        pbp_data = await fetch_pbp_data(session, game_pk)
        if not pbp_data:
            continue

        # Extract plate appearances
        pas = extract_plate_appearances(pbp_data, player_id)

        if pas:
            # Insert into database
            for pa in pas:
                try:
                    cur.execute("""
                        INSERT INTO milb_plate_appearances (
                            mlb_player_id, game_pk, game_date, season, level,
                            at_bat_index, inning, half_inning, event_type, event_type_desc,
                            description, launch_speed, launch_angle, total_distance,
                            venue_name, team, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        ) ON CONFLICT DO NOTHING
                    """, (
                        pa['mlb_player_id'], pa['game_pk'], pa['game_date'], pa['season'], pa['level'],
                        pa['at_bat_index'], pa['inning'], pa['half_inning'], pa['event_type'], pa['event_type_desc'],
                        pa['description'], pa['launch_speed'], pa['launch_angle'], pa['total_distance'],
                        pa['venue_name'], pa['team'], pa['created_at']
                    ))
                    total_pas += 1
                except Exception as e:
                    logging.error(f"Error inserting PA for {name}: {e}")

    conn.commit()
    logging.info(f"  {name}: Collected {total_pas} PAs from {len(game_pks)} games")
    cur.close()
    return total_pas

async def collect_batch(players: List[Tuple], batch_num: int, total_batches: int):
    """Collect PBP data for a batch of players"""
    conn = psycopg2.connect(DB_URL)

    logging.info(f"\n=== BATCH {batch_num}/{total_batches}: {len(players)} players ===")

    async with aiohttp.ClientSession() as session:
        tasks = []
        for player_id, name, team in players:
            tasks.append(collect_player_pbp(session, int(player_id), name, conn))

            # Limit concurrent requests
            if len(tasks) >= 5:
                results = await asyncio.gather(*tasks)
                total = sum(results)
                logging.info(f"  Batch progress: {total} PAs collected")
                tasks = []
                await asyncio.sleep(1)  # Rate limiting

        # Process remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks)
            total = sum(results)
            logging.info(f"  Batch complete: {total} PAs collected")

    conn.close()

def main():
    print("\n" + "="*70)
    print("COMPREHENSIVE 2025 PBP COLLECTION")
    print(f"Started: {datetime.now()}")
    print("="*70)

    # Load prospects needing PBP
    prospects = []
    with open('needs_2025_pbp.txt', 'r') as f:
        for line in f:
            parts = line.strip().split(',')
            if len(parts) >= 3:
                prospects.append((parts[0], parts[1], parts[2]))

    print(f"\nTotal prospects to collect: {len(prospects)}")

    # Process in batches
    batch_size = 20
    batches = [prospects[i:i+batch_size] for i in range(0, len(prospects), batch_size)]

    for i, batch in enumerate(batches, 1):
        asyncio.run(collect_batch(batch, i, len(batches)))

        # Progress report
        if i % 5 == 0:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM milb_plate_appearances WHERE season = 2025")
            total = cur.fetchone()[0]
            conn.close()
            print(f"\n[PROGRESS] Completed {i}/{len(batches)} batches. Total 2025 PBP records: {total:,}")

    # Final report
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM milb_plate_appearances WHERE season = 2025")
    final_total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT mlb_player_id) FROM milb_plate_appearances WHERE season = 2025")
    unique_players = cur.fetchone()[0]
    conn.close()

    print("\n" + "="*70)
    print("COLLECTION COMPLETE")
    print(f"Total 2025 PBP records: {final_total:,}")
    print(f"Unique players with data: {unique_players:,}")
    print(f"Ended: {datetime.now()}")
    print("="*70)

if __name__ == "__main__":
    main()