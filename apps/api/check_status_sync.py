#!/usr/bin/env python3
"""Check pitch collection status using sync database connection"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime

load_dotenv()

# Get database URL and convert to sync
db_url = os.getenv('SQLALCHEMY_DATABASE_URI') or os.getenv('DATABASE_URL')
if 'postgresql+asyncpg://' in db_url:
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')

engine = create_engine(db_url)

with engine.connect() as conn:
    # Get current counts
    batter_result = conn.execute(text('SELECT COUNT(*) as count, COUNT(DISTINCT mlb_batter_id) as players FROM milb_batter_pitches'))
    batter_row = batter_result.fetchone()

    pitcher_result = conn.execute(text('SELECT COUNT(*) as count, COUNT(DISTINCT mlb_pitcher_id) as players FROM milb_pitcher_pitches'))
    pitcher_row = pitcher_result.fetchone()

    # Get by season
    season_result = conn.execute(text('''
        SELECT season, COUNT(*) as pitches, COUNT(DISTINCT mlb_batter_id) as players
        FROM milb_batter_pitches
        GROUP BY season
        ORDER BY season
    '''))
    seasons = season_result.fetchall()

    # Get recent activity (last 5 minutes)
    recent_result = conn.execute(text('''
        SELECT COUNT(*) as recent_count
        FROM milb_batter_pitches
        WHERE created_at >= NOW() - INTERVAL '5 minutes'
    '''))
    recent_row = recent_result.fetchone()

    # Get very recent activity (last 1 minute)
    very_recent_result = conn.execute(text('''
        SELECT COUNT(*) as recent_count
        FROM milb_batter_pitches
        WHERE created_at >= NOW() - INTERVAL '1 minute'
    '''))
    very_recent_row = very_recent_result.fetchone()

    print('='*70)
    print('PITCH COLLECTION STATUS')
    print('='*70)
    print(f'Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print()
    print('OVERALL PROGRESS:')
    print(f'  Batter pitches: {batter_row[0]:,} from {batter_row[1]} players')
    print(f'  Pitcher pitches: {pitcher_row[0]:,} from {pitcher_row[1]} players')
    print(f'  TOTAL: {batter_row[0] + pitcher_row[0]:,} pitches')
    print()
    print('BY SEASON:')
    for season, pitches, players in seasons:
        print(f'  {season}: {pitches:,} pitches, {players} players')
    print()
    print('ACTIVITY:')
    print(f'  Last 5 minutes: {recent_row[0]:,} pitches')
    print(f'  Last 1 minute: {very_recent_row[0]:,} pitches')
    if very_recent_row[0] > 0:
        print(f'  Rate: ~{very_recent_row[0]:.0f} pitches/minute')
        print('  Status: ACTIVE AND COLLECTING')
    elif recent_row[0] > 0:
        print(f'  Rate: ~{recent_row[0]/5:.0f} pitches/minute')
        print('  Status: ACTIVE (slower)')
    else:
        print('  Status: NO RECENT ACTIVITY')
    print('='*70)
