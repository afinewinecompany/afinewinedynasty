"""Collect pitch data ONLY for prospects missing data"""
import asyncio
import aiohttp
import psycopg2
import time
from datetime import datetime

DB_URL = 'postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway'
SEASON = 2025

def get_missing_prospects():
    """Get prospects that have game logs but no pitch data"""
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    # Get batters missing pitch data
    cursor.execute("""
        SELECT
            p.mlb_player_id::integer,
            p.name,
            p.position
        FROM prospects p
        INNER JOIN milb_game_logs gl
            ON p.mlb_player_id::integer = gl.mlb_player_id
            AND gl.season = %s
        LEFT JOIN milb_batter_pitches bp
            ON p.mlb_player_id::integer = bp.mlb_batter_id
            AND bp.season = %s
        WHERE p.position NOT IN ('SP', 'RP')
            AND bp.mlb_batter_id IS NULL
        GROUP BY p.mlb_player_id, p.name, p.position
        ORDER BY p.mlb_player_id
    """, (SEASON, SEASON))

    batters = cursor.fetchall()

    # Get pitchers missing pitch data
    cursor.execute("""
        SELECT
            p.mlb_player_id::integer,
            p.name,
            p.position
        FROM prospects p
        INNER JOIN milb_game_logs gl
            ON p.mlb_player_id::integer = gl.mlb_player_id
            AND gl.season = %s
        LEFT JOIN milb_pitcher_pitches pp
            ON p.mlb_player_id::integer = pp.mlb_pitcher_id
            AND pp.season = %s
        WHERE p.position IN ('SP', 'RP')
            AND pp.mlb_pitcher_id IS NULL
        GROUP BY p.mlb_player_id, p.name, p.position
        ORDER BY p.mlb_player_id
    """, (SEASON, SEASON))

    pitchers = cursor.fetchall()

    conn.close()

    return batters, pitchers

async def fetch_game_pitches(session, game_pk, player_id, player_role='batter'):
    """Fetch pitch data for a single game"""
    try:
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                return []

            data = await response.json()

            if 'liveData' not in data or 'plays' not in data['liveData']:
                return []

            all_plays = data['liveData']['plays'].get('allPlays', [])
            pitches_data = []

            for play in all_plays:
                matchup = play.get('matchup', {})

                # Check if this prospect is involved in this play
                if player_role == 'batter':
                    if matchup.get('batter', {}).get('id') != player_id:
                        continue
                    pitcher_id = matchup.get('pitcher', {}).get('id')
                    batter_id = player_id
                else:  # pitcher
                    if matchup.get('pitcher', {}).get('id') != player_id:
                        continue
                    batter_id = matchup.get('batter', {}).get('id')
                    pitcher_id = player_id

                at_bat_index = play.get('atBatIndex', 0)
                pitch_events = play.get('playEvents', [])

                for pitch in pitch_events:
                    if not pitch.get('isPitch'):
                        continue

                    pitch_data = pitch.get('pitchData', {})
                    details = pitch.get('details', {})

                    pitch_record = (
                        game_pk,
                        at_bat_index,
                        pitch.get('pitchNumber', 0),
                        batter_id if player_role == 'batter' else None,
                        pitcher_id if player_role == 'pitcher' else None,
                        details.get('type', {}).get('code'),
                        details.get('call', {}).get('code'),
                        pitch_data.get('startSpeed'),
                        pitch_data.get('endSpeed'),
                        pitch_data.get('zone'),
                        pitch_data.get('coordinates', {}).get('pX'),
                        pitch_data.get('coordinates', {}).get('pZ'),
                        SEASON
                    )

                    pitches_data.append(pitch_record)

            return pitches_data

    except Exception as e:
        print(f"      Error fetching game {game_pk}: {str(e)[:100]}")
        return []

async def collect_prospect_pitches(session, conn, cursor, player_id, name, position, player_role='batter'):
    """Collect all pitches for one prospect"""

    # Get game logs for this prospect
    cursor.execute("""
        SELECT DISTINCT game_pk, level
        FROM milb_game_logs
        WHERE mlb_player_id = %s AND season = %s
        ORDER BY game_pk
    """, (player_id, SEASON))

    games = cursor.fetchall()

    if not games:
        return 0

    print(f"  {name} ({player_id}): {len(games)} games")

    # Fetch pitches for all games
    all_pitches = []
    for game_pk, level in games:
        pitches = await fetch_game_pitches(session, game_pk, player_id, player_role)
        all_pitches.extend(pitches)

        if len(all_pitches) >= 100:  # Insert in batches
            try:
                if player_role == 'batter':
                    cursor.executemany("""
                        INSERT INTO milb_batter_pitches (
                            game_pk, at_bat_index, pitch_number, mlb_batter_id, mlb_pitcher_id,
                            pitch_type, pitch_call, start_speed, end_speed, zone, px, pz, season
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_batter_id) DO NOTHING
                    """, all_pitches)
                else:
                    cursor.executemany("""
                        INSERT INTO milb_pitcher_pitches (
                            game_pk, at_bat_index, pitch_number, mlb_batter_id, mlb_pitcher_id,
                            pitch_type, pitch_call, start_speed, end_speed, zone, px, pz, season
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_pitcher_id) DO NOTHING
                    """, [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12]) for p in all_pitches])

                conn.commit()
                all_pitches = []
            except Exception as e:
                print(f"    Error inserting: {str(e)[:100]}")
                conn.rollback()
                all_pitches = []

    # Insert remaining pitches
    if all_pitches:
        try:
            if player_role == 'batter':
                cursor.executemany("""
                    INSERT INTO milb_batter_pitches (
                        game_pk, at_bat_index, pitch_number, mlb_batter_id, mlb_pitcher_id,
                        pitch_type, pitch_call, start_speed, end_speed, zone, px, pz, season
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_batter_id) DO NOTHING
                """, all_pitches)
            else:
                cursor.executemany("""
                    INSERT INTO milb_pitcher_pitches (
                        game_pk, at_bat_index, pitch_number, mlb_batter_id, mlb_pitcher_id,
                        pitch_type, pitch_call, start_speed, end_speed, zone, px, pz, season
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (game_pk, at_bat_index, pitch_number, mlb_pitcher_id) DO NOTHING
                """, [(p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7], p[8], p[9], p[10], p[11], p[12]) for p in all_pitches])

            conn.commit()
            total_pitches = len(all_pitches)
            print(f"    -> Collected {total_pitches} pitches")
            return total_pitches
        except Exception as e:
            print(f"    Error inserting: {str(e)[:100]}")
            conn.rollback()
            return 0

    return 0

async def main():
    print("="*80)
    print("COLLECTING PITCH DATA FOR MISSING PROSPECTS ONLY")
    print("="*80)
    print(f"Season: {SEASON}")
    print()

    batters, pitchers = get_missing_prospects()

    print(f"Found {len(batters)} batters and {len(pitchers)} pitchers missing pitch data")
    print()

    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()

    async with aiohttp.ClientSession() as session:
        # Collect batters
        if batters:
            print("="*80)
            print("COLLECTING BATTER PITCH DATA")
            print("="*80)

            for i, (player_id, name, position) in enumerate(batters, 1):
                print(f"[{i}/{len(batters)}]")
                try:
                    await collect_prospect_pitches(session, conn, cursor, player_id, name, position, 'batter')
                except Exception as e:
                    print(f"  ERROR for {name}: {str(e)[:200]}")

                if i % 10 == 0:
                    print(f"\nProgress: {i}/{len(batters)} batters\n")
                    await asyncio.sleep(2)  # Rate limiting

        # Collect pitchers
        if pitchers:
            print("\n" + "="*80)
            print("COLLECTING PITCHER PITCH DATA")
            print("="*80)

            for i, (player_id, name, position) in enumerate(pitchers, 1):
                print(f"[{i}/{len(pitchers)}]")
                try:
                    await collect_prospect_pitches(session, conn, cursor, player_id, name, position, 'pitcher')
                except Exception as e:
                    print(f"  ERROR for {name}: {str(e)[:200]}")

    conn.close()

    print("\n" + "="*80)
    print("COLLECTION COMPLETE")
    print("="*80)

if __name__ == '__main__':
    asyncio.run(main())
