"""Test script to diagnose why pitch metrics aren't showing for some players."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.services.pitch_data_aggregator import PitchDataAggregator
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_pitch_metrics():
    """Test pitch metrics retrieval for specific players."""

    # Create database connection
    database_url = str(settings.SQLALCHEMY_DATABASE_URI).replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Get a sample of players with pitch data
        query = text("""
            SELECT DISTINCT
                p.name,
                p.mlb_player_id,
                p.position,
                p.current_level,
                COUNT(DISTINCT bp.game_pk) as games_with_pitch_data,
                COUNT(*) as total_pitches,
                array_agg(DISTINCT bp.level) as levels_played
            FROM prospects p
            INNER JOIN milb_batter_pitches bp ON p.mlb_player_id::integer = bp.mlb_batter_id
            WHERE bp.game_date >= CURRENT_DATE - INTERVAL '60 days'
                AND p.position NOT IN ('SP', 'RP', 'P')
            GROUP BY p.name, p.mlb_player_id, p.position, p.current_level
            HAVING COUNT(*) >= 100  -- At least 100 pitches
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """)

        result = await db.execute(query)
        test_players = result.fetchall()

        print("\n" + "="*80)
        print("TESTING PITCH METRICS RETRIEVAL")
        print("="*80)

        pitch_aggregator = PitchDataAggregator(db)

        for player in test_players:
            name, mlb_id, position, current_level, games, pitches, levels = player

            print(f"\n{name} ({position})")
            print(f"  MLB ID: {mlb_id}")
            print(f"  Current Level: {current_level}")
            print(f"  Levels Played: {levels}")
            print(f"  Games with Pitch Data: {games}")
            print(f"  Total Pitches: {pitches}")

            # Try to get pitch metrics using current_level
            if current_level:
                print(f"\n  Testing with current_level: {current_level}")
                try:
                    metrics = await pitch_aggregator.get_hitter_pitch_metrics(
                        mlb_id, current_level, days=60
                    )
                    if metrics:
                        print(f"  [SUCCESS] Retrieved metrics:")
                        print(f"    - Sample Size: {metrics.get('sample_size')}")
                        print(f"    - Metrics: {list(metrics.get('metrics', {}).keys())}")
                    else:
                        print(f"  [FAIL] No metrics returned (insufficient data?)")
                except Exception as e:
                    print(f"  [ERROR]: {e}")

            # Try with each level they've played
            for level in levels:
                print(f"\n  Testing with level from pitch data: {level}")
                try:
                    metrics = await pitch_aggregator.get_hitter_pitch_metrics(
                        mlb_id, level, days=60
                    )
                    if metrics:
                        print(f"  [SUCCESS] Retrieved metrics:")
                        print(f"    - Sample Size: {metrics.get('sample_size')}")
                        print(f"    - Level Used: {metrics.get('level')}")
                        print(f"    - Metrics Available: {list(metrics.get('metrics', {}).keys())}")
                        break  # Found working level
                    else:
                        print(f"  [FAIL] No metrics returned")
                except Exception as e:
                    print(f"  [ERROR]: {e}")

        # Now check pitchers
        print("\n" + "="*80)
        print("TESTING PITCHER METRICS")
        print("="*80)

        query = text("""
            SELECT DISTINCT
                p.name,
                p.mlb_player_id,
                p.position,
                p.current_level,
                COUNT(DISTINCT pp.game_pk) as games_with_pitch_data,
                COUNT(*) as total_pitches,
                array_agg(DISTINCT pp.level) as levels_played
            FROM prospects p
            INNER JOIN milb_pitcher_pitches pp ON p.mlb_player_id::integer = pp.mlb_pitcher_id
            WHERE pp.game_date >= CURRENT_DATE - INTERVAL '60 days'
                AND p.position IN ('SP', 'RP', 'P')
            GROUP BY p.name, p.mlb_player_id, p.position, p.current_level
            HAVING COUNT(*) >= 200  -- At least 200 pitches for pitchers
            ORDER BY COUNT(*) DESC
            LIMIT 3
        """)

        result = await db.execute(query)
        test_pitchers = result.fetchall()

        for pitcher in test_pitchers:
            name, mlb_id, position, current_level, games, pitches, levels = pitcher

            print(f"\n{name} ({position})")
            print(f"  MLB ID: {mlb_id}")
            print(f"  Current Level: {current_level}")
            print(f"  Levels Played: {levels}")
            print(f"  Total Pitches: {pitches}")

            # Try with first level from pitch data
            if levels:
                test_level = levels[0]
                print(f"\n  Testing with level: {test_level}")
                try:
                    metrics = await pitch_aggregator.get_pitcher_pitch_metrics(
                        mlb_id, test_level, days=60
                    )
                    if metrics:
                        print(f"  ✓ Success! Retrieved metrics:")
                        print(f"    - Sample Size: {metrics.get('sample_size')}")
                        print(f"    - Metrics: {list(metrics.get('metrics', {}).keys())}")
                    else:
                        print(f"  ✗ No metrics returned")
                except Exception as e:
                    print(f"  ✗ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_pitch_metrics())