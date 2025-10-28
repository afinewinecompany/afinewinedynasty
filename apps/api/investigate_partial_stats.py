"""Investigate why some players have partial stats."""

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


async def investigate_players():
    """Investigate players with partial stats."""

    database_url = str(settings.SQLALCHEMY_DATABASE_URI).replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("\n" + "="*80)
        print("INVESTIGATING PARTIAL STATS ISSUE")
        print("="*80)

        # Test players
        test_players = [
            ('Aidan Miller', 'SS'),
            ('Leo De Vries', 'SS'),
            ('Bryce Eldridge', '1B')
        ]

        for player_name, position in test_players:
            print(f"\n{'='*60}")
            print(f"PLAYER: {player_name} ({position})")
            print('='*60)

            # Get player info
            query = text("""
                SELECT
                    p.mlb_player_id,
                    p.current_level,
                    p.organization
                FROM prospects p
                WHERE LOWER(p.name) = LOWER(:name)
            """)

            result = await db.execute(query, {'name': player_name})
            player_data = result.fetchone()

            if not player_data:
                print(f"  Player not found!")
                continue

            mlb_id = player_data[0]
            print(f"  MLB ID: {mlb_id}")
            print(f"  Current Level: {player_data[1]}")
            print(f"  Organization: {player_data[2]}")

            # Check ALL 2025 pitch data (not time-limited)
            pitch_query = text("""
                SELECT
                    level,
                    COUNT(*) as pitches,
                    COUNT(DISTINCT game_pk) as games,
                    MIN(game_date) as first_date,
                    MAX(game_date) as last_date,

                    -- Check data completeness
                    COUNT(launch_speed) as launch_speed_count,
                    COUNT(launch_angle) as launch_angle_count,
                    COUNT(zone) as zone_count,
                    COUNT(swing) as swing_count,
                    COUNT(swing_and_miss) as swing_and_miss_count,

                    -- Check percentiles for each metric
                    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed) as exit_velo_90th,
                    COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,
                    COUNT(*) FILTER (WHERE swing = TRUE AND swing_and_miss = FALSE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,
                    COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,
                    COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                        NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate

                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_id
                    AND season = 2025  -- ALL 2025 data
                GROUP BY level
                ORDER BY pitches DESC
            """)

            result = await db.execute(pitch_query, {'mlb_id': int(mlb_id)})
            level_data = result.fetchall()

            print(f"\n  2025 Pitch Data by Level:")
            for row in level_data:
                level = row[0]
                print(f"\n  Level: {level}")
                print(f"    Pitches: {row[1]}")
                print(f"    Games: {row[2]}")
                print(f"    Date Range: {row[3]} to {row[4]}")
                print(f"    Data Completeness:")
                print(f"      launch_speed: {row[5]}/{row[1]} ({row[5]*100.0/row[1]:.1f}%)")
                print(f"      launch_angle: {row[6]}/{row[1]} ({row[6]*100.0/row[1]:.1f}%)")
                print(f"      zone: {row[7]}/{row[1]} ({row[7]*100.0/row[1]:.1f}%)")
                print(f"      swing: {row[8]}/{row[1]} ({row[8]*100.0/row[1]:.1f}%)")
                print(f"      swing_and_miss: {row[9]}/{row[1]} ({row[9]*100.0/row[1]:.1f}%)")
                print(f"    Calculated Metrics:")
                print(f"      Exit Velo 90th: {row[10]}")
                print(f"      Hard Hit Rate: {row[11]}")
                print(f"      Contact Rate: {row[12]}")
                print(f"      Whiff Rate: {row[13]}")
                print(f"      Chase Rate: {row[14]}")

            # Now check what the aggregator returns
            print(f"\n  Testing PitchDataAggregator:")
            pitch_aggregator = PitchDataAggregator(db)

            # Get all levels the player played at
            all_levels_query = text("""
                SELECT DISTINCT level
                FROM milb_batter_pitches
                WHERE mlb_batter_id = :mlb_id
                    AND season = 2025
                ORDER BY level
            """)
            levels_result = await db.execute(all_levels_query, {'mlb_id': int(mlb_id)})
            all_levels = [row[0] for row in levels_result.fetchall()]

            print(f"    All 2025 Levels: {all_levels}")

            # Try with the first level (aggregator should get all levels anyway)
            if all_levels:
                try:
                    metrics = await pitch_aggregator.get_hitter_pitch_metrics(
                        mlb_id, all_levels[0], days=365  # Use full year
                    )
                    if metrics:
                        print(f"    SUCCESS - Sample Size: {metrics.get('sample_size')}")
                        print(f"    Metrics returned:")
                        for key, value in metrics.get('metrics', {}).items():
                            print(f"      {key}: {value}")
                    else:
                        print(f"    NO METRICS RETURNED")
                except Exception as e:
                    print(f"    ERROR: {e}")

            # Check the actual SQL query being used
            print(f"\n  Checking aggregation SQL directly:")

            # This is what the aggregator should be doing
            agg_query = text("""
                WITH player_stats AS (
                    SELECT
                        -- Exit Velocity 90th percentile
                        PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY launch_speed)
                            FILTER (WHERE launch_speed IS NOT NULL) as exit_velo_90th,

                        -- Hard Hit Rate (95+ mph)
                        COUNT(*) FILTER (WHERE launch_speed >= 95) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE launch_speed IS NOT NULL), 0) as hard_hit_rate,

                        -- Contact Rate
                        COUNT(*) FILTER (WHERE swing = TRUE AND swing_and_miss = FALSE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as contact_rate,

                        -- Whiff Rate
                        COUNT(*) FILTER (WHERE swing_and_miss = TRUE) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE swing = TRUE), 0) as whiff_rate,

                        -- Chase Rate
                        COUNT(*) FILTER (WHERE swing = TRUE AND zone > 9) * 100.0 /
                            NULLIF(COUNT(*) FILTER (WHERE zone > 9), 0) as chase_rate,

                        -- Sample size
                        COUNT(*) as pitches_seen,
                        COUNT(DISTINCT level) as levels_count,
                        array_agg(DISTINCT level) as levels_included

                    FROM milb_batter_pitches
                    WHERE mlb_batter_id = :mlb_id
                        AND season = 2025  -- ALL 2025 data regardless of level
                )
                SELECT * FROM player_stats
                WHERE pitches_seen >= 50  -- Min threshold
            """)

            result = await db.execute(agg_query, {'mlb_id': int(mlb_id)})
            agg_data = result.fetchone()

            if agg_data:
                print(f"    Aggregated across {agg_data[6]} levels: {agg_data[7]}")
                print(f"    Total Pitches: {agg_data[5]}")
                print(f"    Exit Velo 90th: {agg_data[0]}")
                print(f"    Hard Hit Rate: {agg_data[1]}%")
                print(f"    Contact Rate: {agg_data[2]}%")
                print(f"    Whiff Rate: {agg_data[3]}%")
                print(f"    Chase Rate: {agg_data[4]}%")
            else:
                print(f"    No aggregated data!")


if __name__ == "__main__":
    asyncio.run(investigate_players())