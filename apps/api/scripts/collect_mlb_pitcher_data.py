"""
Collect MLB Pitcher Game Logs (2021-2025)
=========================================

This script collects MLB pitcher game-by-game stats from the MLB Stats API
to enable training pitcher stat projection models.

Strategy:
1. Get all MLB pitchers from prospects table
2. For each pitcher, fetch game logs from MLB Stats API
3. Insert into mlb_pitcher_appearances table
4. Track progress and handle errors gracefully

Usage:
    python scripts/collect_mlb_pitcher_data.py
"""

import asyncio
import asyncpg
import aiohttp
from datetime import datetime
import sys
import codecs
from typing import Optional, Dict, Any, List
import time

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"
MLB_API_BASE = "https://statsapi.mlb.com/api/v1"


async def create_mlb_pitcher_table(conn):
    """Create mlb_pitcher_appearances table if it doesn't exist."""

    create_query = """
        CREATE TABLE IF NOT EXISTS mlb_pitcher_appearances (
            id SERIAL PRIMARY KEY,
            mlb_player_id INTEGER NOT NULL,
            game_pk BIGINT NOT NULL,
            game_date DATE,
            season INTEGER,
            game_type VARCHAR(10),
            team_id INTEGER,
            opponent_id INTEGER,
            is_home BOOLEAN,
            innings_pitched NUMERIC,
            hits INTEGER,
            runs INTEGER,
            earned_runs INTEGER,
            walks INTEGER,
            strikeouts INTEGER,
            home_runs INTEGER,
            hit_by_pitch INTEGER,
            wild_pitches INTEGER,
            balks INTEGER,
            pitches_thrown INTEGER,
            strikes INTEGER,
            balls INTEGER,
            batters_faced INTEGER,
            decision VARCHAR(10),
            saves INTEGER,
            blown_saves INTEGER,
            holds INTEGER,
            era NUMERIC,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(mlb_player_id, game_pk, season)
        );

        CREATE INDEX IF NOT EXISTS idx_mlb_pitcher_player_id ON mlb_pitcher_appearances(mlb_player_id);
        CREATE INDEX IF NOT EXISTS idx_mlb_pitcher_season ON mlb_pitcher_appearances(season);
        CREATE INDEX IF NOT EXISTS idx_mlb_pitcher_game_pk ON mlb_pitcher_appearances(game_pk);
    """

    await conn.execute(create_query)
    print("✅ Table mlb_pitcher_appearances ready")


async def get_pitchers_to_collect(conn):
    """Get list of pitchers who need MLB data collected."""

    query = """
        SELECT DISTINCT
            p.id as prospect_id,
            p.mlb_player_id::integer as mlb_player_id,
            p.name,
            p.position
        FROM prospects p
        WHERE p.position IN ('SP', 'RP', 'LHP', 'RHP')
        AND p.mlb_player_id IS NOT NULL
        AND p.mlb_player_id ~ '^[0-9]+$'
        ORDER BY p.id
    """

    rows = await conn.fetch(query)
    return [dict(r) for r in rows]


async def fetch_pitcher_game_logs(session: aiohttp.ClientSession, mlb_player_id: int, season: int) -> List[Dict[str, Any]]:
    """Fetch pitcher game logs for a specific season from MLB Stats API."""

    url = f"{MLB_API_BASE}/people/{mlb_player_id}/stats"
    params = {
        'stats': 'gameLog',
        'group': 'pitching',
        'season': season,
        'gameType': 'R',  # Regular season
    }

    try:
        await asyncio.sleep(0.15)  # Rate limiting - slower to be safe

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as response:
            if response.status == 200:
                data = await response.json()

                if 'stats' not in data or len(data['stats']) == 0:
                    return []

                if 'splits' not in data['stats'][0]:
                    return []

                games = []
                for split in data['stats'][0]['splits']:
                    game = split.get('stat', {})
                    game_info = split.get('game', {})
                    team_info = split.get('team', {})
                    opponent_info = split.get('opponent', {})

                    # Extract pitching stats
                    games.append({
                        'mlb_player_id': mlb_player_id,
                        'game_pk': game_info.get('gamePk'),
                        'game_date': split.get('date'),
                        'season': season,
                        'game_type': game_info.get('gameType', 'R'),
                        'team_id': team_info.get('id'),
                        'opponent_id': opponent_info.get('id'),
                        'is_home': split.get('isHome'),
                        'innings_pitched': game.get('inningsPitched'),
                        'hits': game.get('hits'),
                        'runs': game.get('runs'),
                        'earned_runs': game.get('earnedRuns'),
                        'walks': game.get('baseOnBalls'),
                        'strikeouts': game.get('strikeOuts'),
                        'home_runs': game.get('homeRuns'),
                        'hit_by_pitch': game.get('hitByPitch'),
                        'wild_pitches': game.get('wildPitches'),
                        'balks': game.get('balks'),
                        'pitches_thrown': game.get('numberOfPitches'),
                        'strikes': game.get('strikes'),
                        'balls': None,  # Not directly provided
                        'batters_faced': game.get('battersFaced'),
                        'decision': game.get('decision'),
                        'saves': game.get('saves'),
                        'blown_saves': game.get('blownSaves'),
                        'holds': game.get('holds'),
                        'era': game.get('era'),
                    })

                return games

            elif response.status == 404:
                return []  # No data for this player/season

            else:
                print(f"    ⚠️  API error {response.status} for player {mlb_player_id} season {season}")
                return []

    except asyncio.TimeoutError:
        print(f"    ⚠️  Timeout for player {mlb_player_id} season {season}")
        return []

    except Exception as e:
        print(f"    ⚠️  Error fetching player {mlb_player_id} season {season}: {e}")
        return []


async def insert_pitcher_appearances(conn, games: List[Dict[str, Any]]) -> int:
    """Insert pitcher appearances into database."""

    if not games:
        return 0

    insert_query = """
        INSERT INTO mlb_pitcher_appearances (
            mlb_player_id, game_pk, game_date, season, game_type,
            team_id, opponent_id, is_home, innings_pitched,
            hits, runs, earned_runs, walks, strikeouts, home_runs,
            hit_by_pitch, wild_pitches, balks, pitches_thrown,
            strikes, balls, batters_faced, decision, saves,
            blown_saves, holds, era, created_at, updated_at
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
            $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27,
            NOW(), NOW()
        )
        ON CONFLICT (mlb_player_id, game_pk, season) DO NOTHING
    """

    inserted = 0

    for game in games:
        try:
            # Convert innings pitched string (e.g., "6.1") to numeric
            ip_str = game.get('innings_pitched')
            innings_pitched = None
            if ip_str:
                try:
                    if isinstance(ip_str, str):
                        innings_pitched = float(ip_str)
                    else:
                        innings_pitched = ip_str
                except:
                    pass

            # Parse game date
            game_date = None
            if game.get('game_date'):
                try:
                    game_date = datetime.strptime(game['game_date'], '%Y-%m-%d').date()
                except:
                    pass

            result = await conn.execute(
                insert_query,
                game['mlb_player_id'],
                game.get('game_pk'),
                game_date,
                game.get('season'),
                game.get('game_type'),
                game.get('team_id'),
                game.get('opponent_id'),
                game.get('is_home'),
                innings_pitched,
                game.get('hits'),
                game.get('runs'),
                game.get('earned_runs'),
                game.get('walks'),
                game.get('strikeouts'),
                game.get('home_runs'),
                game.get('hit_by_pitch'),
                game.get('wild_pitches'),
                game.get('balks'),
                game.get('pitches_thrown'),
                game.get('strikes'),
                game.get('balls'),
                game.get('batters_faced'),
                game.get('decision'),
                game.get('saves'),
                game.get('blown_saves'),
                game.get('holds'),
                game.get('era'),
            )

            # Check if row was inserted (not skipped by ON CONFLICT)
            if result == 'INSERT 0 1':
                inserted += 1

        except Exception as e:
            print(f"    ⚠️  Error inserting game {game.get('game_pk')}: {e}")

    return inserted


async def collect_pitcher_data():
    """Main function to collect MLB pitcher data."""

    print("="*80)
    print("COLLECT MLB PITCHER DATA (2021-2025)")
    print("="*80)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Step 1: Create table
        print("="*80)
        print("1. TABLE SETUP")
        print("="*80)
        await create_mlb_pitcher_table(conn)

        # Step 2: Get pitchers to collect
        print("\n" + "="*80)
        print("2. IDENTIFYING PITCHERS")
        print("="*80)

        pitchers = await get_pitchers_to_collect(conn)
        print(f"\nFound {len(pitchers)} pitchers in prospects table")

        if not pitchers:
            print("\n⚠️  No pitchers found!")
            return

        # Step 3: Collect data
        print("\n" + "="*80)
        print("3. COLLECTING MLB PITCHER DATA")
        print("="*80)
        print("\nSeasons: 2021-2025")
        print(f"Rate limit: 0.15s per request")

        seasons = [2021, 2022, 2023, 2024, 2025]

        total_games = 0
        total_pitchers_with_data = 0
        failed_requests = 0

        async with aiohttp.ClientSession() as session:
            for i, pitcher in enumerate(pitchers, 1):
                if i % 25 == 0:
                    print(f"\nProgress: {i}/{len(pitchers)} ({i/len(pitchers)*100:.1f}%)")
                    print(f"  Games collected: {total_games}")
                    print(f"  Pitchers with data: {total_pitchers_with_data}")
                    print(f"  Failed requests: {failed_requests}")

                pitcher_games = 0

                # Collect all seasons for this pitcher
                for season in seasons:
                    games = await fetch_pitcher_game_logs(session, pitcher['mlb_player_id'], season)

                    if games:
                        inserted = await insert_pitcher_appearances(conn, games)
                        pitcher_games += inserted
                        total_games += inserted
                    else:
                        # Track if API call failed vs no data
                        pass

                if pitcher_games > 0:
                    total_pitchers_with_data += 1
                    if i % 25 == 1:  # Print first of each batch
                        print(f"  {pitcher['name']:30s} - {pitcher_games} games")

        # Step 4: Verification
        print("\n" + "="*80)
        print("4. VERIFICATION")
        print("="*80)

        total_records = await conn.fetchval("SELECT COUNT(*) FROM mlb_pitcher_appearances")
        unique_pitchers = await conn.fetchval("SELECT COUNT(DISTINCT mlb_player_id) FROM mlb_pitcher_appearances")

        # Count by season
        season_counts = await conn.fetch("""
            SELECT season, COUNT(*) as games, COUNT(DISTINCT mlb_player_id) as pitchers
            FROM mlb_pitcher_appearances
            GROUP BY season
            ORDER BY season
        """)

        print(f"\nTotal MLB pitcher appearances: {total_records:,}")
        print(f"Unique pitchers: {unique_pitchers:,}")

        print(f"\nBreakdown by season:")
        for row in season_counts:
            print(f"  {row['season']}: {row['games']:,} games, {row['pitchers']:,} pitchers")

        # Check pitchers with 20+ appearances
        pitchers_20plus = await conn.fetchval("""
            SELECT COUNT(DISTINCT mlb_player_id)
            FROM mlb_pitcher_appearances
            WHERE season >= 2021
            GROUP BY mlb_player_id
            HAVING COUNT(*) >= 20
        """)

        print(f"\nPitchers with 20+ appearances (2021+): {pitchers_20plus or 0}")

        # Step 5: Summary
        print("\n" + "="*80)
        print("5. SUMMARY")
        print("="*80)

        print(f"""
COLLECTION RESULTS:
- Pitchers queried: {len(pitchers)}
- Pitchers with MLB data: {total_pitchers_with_data}
- Total games collected: {total_games:,}
- Unique pitchers in DB: {unique_pitchers}
- Pitchers with 20+ games: {pitchers_20plus or 0}

IMPACT ON TRAINING DATA:
- Expected pitcher training samples: {pitchers_20plus or 0}
- (Pitchers with both MiLB and 20+ MLB games)

NEXT STEPS:
1. Re-run training data builder
2. Expected: 399 hitter samples + {pitchers_20plus or 0} pitcher samples
3. Train both models
        """)

    finally:
        await conn.close()

    print("\n" + "="*80)
    print("MLB PITCHER DATA COLLECTION COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(collect_pitcher_data())
