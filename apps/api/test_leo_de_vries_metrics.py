"""Test script to investigate Leo De Vries metrics issue."""

import asyncio
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.services.pitch_data_aggregator import PitchDataAggregator
from app.services.prospect_ranking_service import ProspectRankingService
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_leo_de_vries():
    """Test Leo De Vries specifically."""

    # Create database connection
    database_url = str(settings.SQLALCHEMY_DATABASE_URI).replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("\n" + "="*80)
        print("INVESTIGATING LEO DE VRIES METRICS")
        print("="*80)

        # First, find Leo De Vries in the database
        query = text("""
            SELECT
                p.id,
                p.name,
                p.mlb_player_id,
                p.position,
                p.current_level,
                p.age,
                p.organization
            FROM prospects p
            WHERE LOWER(p.name) LIKE '%leo%de%vries%'
        """)

        result = await db.execute(query)
        leo_data = result.fetchone()

        if not leo_data:
            print("ERROR: Leo De Vries not found in prospects table!")
            return

        print(f"\nProspect Info:")
        print(f"  Name: {leo_data[1]}")
        print(f"  MLB ID: {leo_data[2]}")
        print(f"  Position: {leo_data[3]}")
        print(f"  Current Level: {leo_data[4]}")
        print(f"  Age: {leo_data[5]}")
        print(f"  Organization: {leo_data[6]}")

        mlb_id = leo_data[2]

        # Check if he has pitch data as a pitcher
        pitch_query = text("""
            SELECT
                COUNT(*) as total_pitches,
                COUNT(DISTINCT game_pk) as games,
                array_agg(DISTINCT level) as levels,
                MIN(game_date) as first_date,
                MAX(game_date) as last_date,
                MAX(season) as latest_season
            FROM milb_pitcher_pitches
            WHERE mlb_pitcher_id = :mlb_id
        """)

        result = await db.execute(pitch_query, {'mlb_id': int(mlb_id)})
        pitch_data = result.fetchone()

        print(f"\nPitcher Pitch Data:")
        print(f"  Total Pitches: {pitch_data[0]}")
        print(f"  Games: {pitch_data[1]}")
        print(f"  Levels: {pitch_data[2]}")
        print(f"  Date Range: {pitch_data[3]} to {pitch_data[4]}")
        print(f"  Latest Season: {pitch_data[5]}")

        # Check recent game logs
        game_log_query = text("""
            SELECT
                COUNT(*) as total_games,
                AVG(CASE WHEN at_bats > 0 THEN ops END) as avg_ops,
                AVG(era) as avg_era,
                AVG(innings_pitched) as avg_ip,
                MAX(level) as recent_level,
                MAX(game_date) as last_game
            FROM milb_game_logs
            WHERE CAST(mlb_player_id AS VARCHAR) = :mlb_id
                AND game_date >= CURRENT_DATE - INTERVAL '60 days'
        """)

        result = await db.execute(game_log_query, {'mlb_id': str(mlb_id)})
        game_data = result.fetchone()

        print(f"\nRecent Game Logs (60 days):")
        print(f"  Total Games: {game_data[0]}")
        print(f"  Average OPS: {game_data[1]}")
        print(f"  Average ERA: {game_data[2]}")
        print(f"  Average IP: {game_data[3]}")
        print(f"  Recent Level: {game_data[4]}")
        print(f"  Last Game: {game_data[5]}")

        # Now try to get pitch metrics using PitchDataAggregator
        print("\n" + "-"*80)
        print("TESTING PITCH DATA AGGREGATOR")
        print("-"*80)

        pitch_aggregator = PitchDataAggregator(db)

        # Try with different levels
        test_levels = []
        if leo_data[4]:  # current_level
            test_levels.append(leo_data[4])
        if game_data[3]:  # recent_level
            test_levels.append(game_data[3])
        if pitch_data[2]:  # levels from pitch data
            test_levels.extend(pitch_data[2])

        test_levels = list(set(test_levels))  # Remove duplicates

        for level in test_levels:
            print(f"\nTrying level: {level}")
            try:
                metrics = await pitch_aggregator.get_pitcher_pitch_metrics(
                    mlb_id, level, days=60
                )
                if metrics:
                    print(f"  SUCCESS! Got metrics:")
                    print(f"    Sample Size: {metrics.get('sample_size')}")
                    print(f"    Metrics: {json.dumps(metrics.get('metrics', {}), indent=6)}")
                    print(f"    Percentiles: {json.dumps(metrics.get('percentiles', {}), indent=6)}")
                    break
                else:
                    print(f"  No metrics returned (insufficient data?)")
            except Exception as e:
                print(f"  ERROR: {e}")

        # Test the ProspectRankingService to see what it returns
        print("\n" + "-"*80)
        print("TESTING PROSPECT RANKING SERVICE")
        print("-"*80)

        ranking_service = ProspectRankingService(db)

        # Build prospect dict similar to what the service expects
        prospect_dict = {
            'id': leo_data[0],
            'name': leo_data[1],
            'position': leo_data[3],
            'mlb_player_id': leo_data[2],
            'current_level': leo_data[4],
            'recent_level': game_data[4],  # Index 4 now
            'recent_ops': game_data[1],  # OPS for hitter
            'recent_era': game_data[2],  # ERA (should be None for hitter)
            'recent_games': game_data[0]
        }

        recent_stats = {
            'recent_ops': game_data[1],  # OPS for hitter
            'recent_era': game_data[2],  # ERA (should be None for hitter)
            'recent_games': game_data[0],
            'recent_level': game_data[4]  # Index 4 now
        }

        # Leo is a shortstop, so he's a hitter
        is_hitter = prospect_dict['position'] not in ['SP', 'RP', 'P', 'RHP', 'LHP']

        print(f"\nCalling calculate_performance_modifier with:")
        print(f"  Prospect: {prospect_dict['name']}")
        print(f"  Recent Level: {recent_stats.get('recent_level')}")
        print(f"  Recent OPS: {recent_stats.get('recent_ops')}")
        print(f"  Recent ERA: {recent_stats.get('recent_era')}")
        print(f"  Is Hitter: {is_hitter}")

        modifier, breakdown = await ranking_service.calculate_performance_modifier(
            prospect_dict,
            recent_stats,
            is_hitter=is_hitter
        )

        print(f"\nResult:")
        print(f"  Modifier: {modifier}")
        print(f"  Breakdown: {json.dumps(breakdown, indent=4) if breakdown else 'None'}")

        # Check what the composite rankings endpoint would return
        print("\n" + "-"*80)
        print("CHECKING COMPOSITE RANKINGS DATA")
        print("-"*80)

        composite_query = text("""
            SELECT
                p.name,
                p.position,
                COALESCE(pit.fv, h.fv) as fangraphs_fv,
                recent.era as recent_era,
                recent.games_played as recent_games,
                recent.level as recent_level
            FROM prospects p
            LEFT JOIN fangraphs_pitcher_grades pit
                ON p.fg_player_id = pit.fangraphs_player_id
                AND pit.data_year = 2025
            LEFT JOIN fangraphs_hitter_grades h
                ON p.fg_player_id = h.fangraphs_player_id
                AND h.data_year = 2025
            LEFT JOIN LATERAL (
                SELECT
                    AVG(CASE WHEN innings_pitched > 0 THEN era END) as era,
                    COUNT(*) as games_played,
                    MAX(level) as level
                FROM milb_game_logs
                WHERE CAST(mlb_player_id AS VARCHAR) = p.mlb_player_id
                    AND game_date > CURRENT_DATE - INTERVAL '60 days'
            ) recent ON true
            WHERE p.id = :prospect_id
        """)

        result = await db.execute(composite_query, {'prospect_id': leo_data[0]})
        composite_data = result.fetchone()

        print(f"\nComposite Rankings Query Result:")
        print(f"  Name: {composite_data[0]}")
        print(f"  Position: {composite_data[1]}")
        print(f"  FanGraphs FV: {composite_data[2]}")
        print(f"  Recent ERA: {composite_data[3]}")
        print(f"  Recent Games: {composite_data[4]}")
        print(f"  Recent Level: {composite_data[5]}")


if __name__ == "__main__":
    asyncio.run(test_leo_de_vries())