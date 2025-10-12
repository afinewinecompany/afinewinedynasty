"""
Attempt to collect ALL 2025 games for Chase DeLauter including any rookie ball games
"""
import requests
import asyncio
import asyncpg
from pathlib import Path
import sys
import os
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent.parent))
os.chdir(Path(__file__).parent.parent.parent)

from app.core.config import settings

async def collect_all_delauter_2025():
    """Try to collect all 2025 DeLauter games including rookie ball."""

    player_id = 800050
    season = 2025
    base_url = "https://statsapi.mlb.com/api/v1"

    print("=" * 80)
    print("ATTEMPTING TO COLLECT ALL 2025 GAMES FOR CHASE DELAUTER")
    print("=" * 80)

    # Try different approaches to get game logs
    print("\n1. Trying people endpoint with hydrate...")
    url = f"{base_url}/people/{player_id}"
    params = {
        'hydrate': f'stats(group=[hitting],type=[gameLog],season={season})'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            if 'people' in data and len(data['people']) > 0:
                person = data['people'][0]
                print(f"   Player: {person.get('fullName')}")

                stats_list = person.get('stats', [])
                print(f"   Stats groups found: {len(stats_list)}")

                for stat_group in stats_list:
                    group_type = stat_group.get('type', {}).get('displayName')
                    print(f"\n   Group: {group_type}")

                    splits = stat_group.get('splits', [])
                    print(f"   Splits found: {len(splits)}")

                    if splits:
                        print(f"\n   First few games:")
                        for i, split in enumerate(splits[:5]):
                            game = split.get('game', {})
                            team = split.get('team', {})
                            stat = split.get('stat', {})
                            date = split.get('date', 'N/A')

                            print(f"     {date}: {team.get('name', 'Unknown')} - "
                                  f"{stat.get('atBats', 0)} AB, {stat.get('hits', 0)} H")

                        # Try to store these in database
                        print(f"\n2. Attempting to store {len(splits)} games in database...")
                        await store_games(splits, player_id, season)

    except Exception as e:
        print(f"   Error: {e}")

    print("\n3. Trying stats endpoint directly...")
    url = f"{base_url}/people/{player_id}/stats"
    params = {
        'stats': 'gameLog',
        'season': season,
        'group': 'hitting'
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            stats_list = data.get('stats', [])

            for stat_group in stats_list:
                splits = stat_group.get('splits', [])
                if splits:
                    print(f"   Found {len(splits)} game logs")

                    # Group by team to see levels
                    teams = {}
                    for split in splits:
                        team_name = split.get('team', {}).get('name', 'Unknown')
                        if team_name not in teams:
                            teams[team_name] = 0
                        teams[team_name] += 1

                    print(f"\n   Breakdown by team:")
                    for team, count in teams.items():
                        print(f"     {team}: {count} games")

    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 80)


async def store_games(splits, player_id, season):
    """Store game splits in database."""

    db_url = str(settings.SQLALCHEMY_DATABASE_URI)
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(db_url)

    try:
        stored_count = 0

        for split in splits:
            try:
                stat = split.get('stat', {})
                game = split.get('game', {})
                team = split.get('team', {})

                # Parse date
                date_str = split.get('date', '')
                game_date = None
                if date_str:
                    try:
                        game_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except:
                        pass

                # Get prospect_id
                prospect_id = await conn.fetchval(
                    "SELECT id FROM prospects WHERE mlb_id = $1 LIMIT 1",
                    player_id
                )

                if not prospect_id:
                    continue

                # Try to determine level from team name
                team_name = team.get('name', '')
                level = 'Unknown'
                if 'Columbus' in team_name:
                    level = 'AAA'
                elif 'Akron' in team_name:
                    level = 'AA'
                elif 'ACL' in team_name or 'FCL' in team_name or 'DSL' in team_name:
                    level = 'Rookie'

                # Insert query
                query = """
                    INSERT INTO milb_game_logs (
                        prospect_id, mlb_player_id, season, game_pk, game_date, game_type,
                        team, level,
                        games_played, at_bats, plate_appearances,
                        runs, hits, doubles, triples, home_runs, rbi,
                        walks, strikeouts, stolen_bases, caught_stealing,
                        batting_avg, on_base_pct, slugging_pct, ops,
                        data_source, created_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8,
                        1, $9, $10, $11, $12, $13, $14, $15, $16,
                        $17, $18, $19, $20,
                        $21, $22, $23, $24,
                        'mlb_api_2025_collection', NOW()
                    )
                    ON CONFLICT (mlb_player_id, game_pk, season)
                    DO UPDATE SET
                        level = EXCLUDED.level,
                        team = EXCLUDED.team,
                        updated_at = NOW()
                    RETURNING id
                """

                result = await conn.execute(
                    query,
                    prospect_id,
                    player_id,
                    season,
                    game.get('gamePk'),
                    game_date,
                    game.get('gameType', 'R'),
                    team_name,
                    level,
                    stat.get('atBats', 0),
                    stat.get('plateAppearances', 0),
                    stat.get('runs', 0),
                    stat.get('hits', 0),
                    stat.get('doubles', 0),
                    stat.get('triples', 0),
                    stat.get('homeRuns', 0),
                    stat.get('rbi', 0),
                    stat.get('baseOnBalls', 0),
                    stat.get('strikeOuts', 0),
                    stat.get('stolenBases', 0),
                    stat.get('caughtStealing', 0),
                    float(stat.get('avg', 0) or 0),
                    float(stat.get('obp', 0) or 0),
                    float(stat.get('slg', 0) or 0),
                    float(stat.get('ops', 0) or 0)
                )

                stored_count += 1

            except Exception as e:
                print(f"     Error storing game: {e}")

        print(f"   Successfully stored/updated {stored_count} games")

    except Exception as e:
        print(f"   Database error: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(collect_all_delauter_2025())