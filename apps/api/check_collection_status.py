import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Try to load from railway config
railway_env_path = Path(__file__).parent.parent.parent / '.env.railway'
if railway_env_path.exists():
    with open(railway_env_path) as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value.strip('"').strip("'")

# Get database URL
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    print('ERROR: DATABASE_URL not found. Please set it in .env.railway or environment')
    sys.exit(1)

# Create engine
engine = create_engine(DATABASE_URL)

print('=' * 70)
print('COLLECTION STATUS CHECK')
print(f'Check time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 70)
print()

try:
    with engine.connect() as conn:
        # 1. Check for recent collection activity
        result = conn.execute(text('''
            SELECT
                collector_type,
                MAX(created_at) as last_run,
                COUNT(*) as total_runs_today,
                COUNT(DISTINCT player_id) as unique_players
            FROM social_media_posts
            WHERE created_at > NOW() - INTERVAL '24 HOURS'
            GROUP BY collector_type
            ORDER BY last_run DESC
        '''))

        print('📊 RECENT COLLECTION ACTIVITY (Last 24 hours)')
        print('-' * 70)
        print(f'{"Collector Type":<25} {"Last Run":<20} {"Runs":<10} {"Players":<10}')
        print('-' * 70)

        rows = list(result)
        if rows:
            for row in rows:
                last_run = row.last_run.strftime("%Y-%m-%d %H:%M") if row.last_run else "Never"
                print(f'{row.collector_type:<25} {last_run:<20} {row.total_runs_today:<10} {row.unique_players:<10}')
        else:
            print('No collection activity in the last 24 hours')

        print()

        # 2. Check play-by-play data status
        print('🏈 PLAY-BY-PLAY DATA STATUS')
        print('-' * 70)

        # Overall stats
        result = conn.execute(text('''
            SELECT
                COUNT(*) as total_plays,
                COUNT(DISTINCT game_id) as total_games,
                MIN(created_at) as oldest_play,
                MAX(created_at) as newest_play
            FROM play_by_play_data
        '''))

        for row in result:
            print(f'Total plays in database: {row.total_plays:,}')
            print(f'Total games with data: {row.total_games}')
            if row.oldest_play and row.newest_play:
                print(f'Date range: {row.oldest_play.date()} to {row.newest_play.date()}')

        print()

        # 3. Coverage by week
        result = conn.execute(text('''
            SELECT
                g.week,
                COUNT(DISTINCT g.game_id) as games_in_week,
                COUNT(DISTINCT p.game_id) as games_with_pbp,
                COUNT(p.play_id) as total_plays,
                STRING_AGG(DISTINCT CASE
                    WHEN p.game_id IS NULL THEN g.away_team || ' @ ' || g.home_team
                    ELSE NULL
                END, ', ') as missing_games
            FROM games g
            LEFT JOIN play_by_play_data p ON g.game_id = p.game_id
            WHERE g.season = 2024
            AND g.start_date < NOW()
            GROUP BY g.week
            ORDER BY g.week DESC
            LIMIT 10
        '''))

        print('📅 PLAY-BY-PLAY COVERAGE BY WEEK (2024 Season - Last 10 Weeks)')
        print('-' * 70)
        print(f'{"Week":<6} {"Games":<8} {"w/PBP":<8} {"Coverage":<10} {"Total Plays":<12} {"Missing":<20}')
        print('-' * 70)

        for row in result:
            coverage = (row.games_with_pbp / row.games_in_week * 100) if row.games_in_week > 0 else 0
            missing = row.missing_games[:40] + '...' if row.missing_games and len(row.missing_games) > 40 else (row.missing_games or '✓ Complete')
            print(f'{row.week:<6} {row.games_in_week:<8} {row.games_with_pbp:<8} {coverage:>6.1f}%    {row.total_plays:<12,} {missing:<20}')

        print()

        # 4. Check for games missing play-by-play data
        result = conn.execute(text('''
            SELECT
                g.week,
                g.game_id,
                g.home_team,
                g.away_team,
                g.start_date,
                g.season
            FROM games g
            LEFT JOIN play_by_play_data p ON g.game_id = p.game_id
            WHERE g.season = 2024
            AND g.start_date < NOW() - INTERVAL '3 HOURS'
            AND p.play_id IS NULL
            ORDER BY g.week DESC, g.start_date DESC
            LIMIT 15
        '''))

        missing_games = list(result)
        if missing_games:
            print('⚠️  GAMES MISSING PLAY-BY-PLAY DATA (Most Recent)')
            print('-' * 70)
            for row in missing_games:
                game_date = row.start_date.strftime("%Y-%m-%d %H:%M") if row.start_date else "Unknown"
                print(f'Week {row.week:2}: {row.away_team:3} @ {row.home_team:3} | {game_date} | Game ID: {row.game_id}')
        else:
            print('✅ All completed games have play-by-play data!')

        print()

        # 5. Check collection schedule status
        result = conn.execute(text('''
            SELECT
                COUNT(*) as scheduled_tasks,
                MIN(next_run) as next_scheduled,
                MAX(last_run) as last_executed
            FROM hype_collection_schedule
            WHERE is_active = true
        '''))

        print('⏰ COLLECTION SCHEDULE STATUS')
        print('-' * 70)
        for row in result:
            print(f'Active scheduled tasks: {row.scheduled_tasks}')
            if row.next_scheduled:
                print(f'Next scheduled run: {row.next_scheduled.strftime("%Y-%m-%d %H:%M:%S")}')
            if row.last_executed:
                print(f'Last executed: {row.last_executed.strftime("%Y-%m-%d %H:%M:%S")}')

        print()

        # 6. Check for currently running processes (by checking recent activity)
        result = conn.execute(text('''
            SELECT
                collector_type,
                MAX(created_at) as last_activity
            FROM social_media_posts
            WHERE created_at > NOW() - INTERVAL '5 MINUTES'
            GROUP BY collector_type
        '''))

        recent_activity = list(result)
        if recent_activity:
            print('🔄 POSSIBLY RUNNING COLLECTIONS (Activity in last 5 minutes)')
            print('-' * 70)
            for row in recent_activity:
                print(f'{row.collector_type}: Last activity {row.last_activity.strftime("%H:%M:%S")}')
        else:
            print('ℹ️  No collection activity in the last 5 minutes')

        print()
        print('=' * 70)
        print('STATUS CHECK COMPLETE')
        print('=' * 70)

except Exception as e:
    print(f'ERROR connecting to database: {e}')
    sys.exit(1)