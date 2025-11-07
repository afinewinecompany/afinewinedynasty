"""Debug script to identify Decimal type issues in statline rankings."""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = "postgresql+asyncpg://postgres:NGvvYlzjGRfwJQbSlCmHQJmAwqnlqRQZ@autorack.proxy.rlwy.net:24426/railway"


async def debug_decimal_issue():
    """Debug Decimal type issues in the statline ranking query."""

    # Create engine and session
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        print("\n" + "="*60)
        print("Debugging Decimal Type Issues")
        print("="*60)

        # Run the main query
        query = """
            WITH player_pitch_metrics AS (
                SELECT
                    bp.mlb_batter_id,
                    p.name,
                    p.age,
                    bp.level,

                    -- Plate Appearance Counting (new method)
                    COUNT(DISTINCT bp.game_pk) as games,
                    COUNT(DISTINCT CASE
                        WHEN bp.is_final_pitch = true
                        THEN bp.game_pk || '_' || bp.at_bat_index
                    END) as total_pa,

                    -- Hit Detection (from pa_result descriptions)
                    SUM(CASE WHEN bp.is_final_pitch = true AND LOWER(bp.pa_result) LIKE '%single%' THEN 1 ELSE 0 END) as singles,
                    SUM(CASE WHEN bp.is_final_pitch = true AND LOWER(bp.pa_result) LIKE '%double%' THEN 1 ELSE 0 END) as doubles,
                    SUM(CASE WHEN bp.is_final_pitch = true AND LOWER(bp.pa_result) LIKE '%triple%' THEN 1 ELSE 0 END) as triples,
                    SUM(CASE WHEN bp.is_final_pitch = true AND LOWER(bp.pa_result) LIKE '%home%run%' THEN 1 ELSE 0 END) as home_runs,

                    -- Other outcomes
                    SUM(CASE WHEN bp.is_final_pitch = true AND LOWER(bp.pa_result) LIKE '%walk%' THEN 1 ELSE 0 END) as walks,
                    SUM(CASE WHEN bp.is_final_pitch = true AND LOWER(bp.pa_result) LIKE '%strikeout%' THEN 1 ELSE 0 END) as strikeouts,

                    -- Pitch-level metrics
                    COUNT(*) as total_pitches,
                    AVG(CASE WHEN bp.zone <= 9 THEN 100.0 ELSE 0.0 END) as zone_rate,
                    AVG(CASE WHEN bp.swing = true THEN 100.0 ELSE 0.0 END) as swing_rate,
                    AVG(CASE WHEN bp.zone > 9 AND bp.swing = true THEN 100.0
                            WHEN bp.zone > 9 THEN 0.0
                            ELSE NULL END) as chase_rate,
                    AVG(CASE WHEN bp.swing = true AND bp.contact = true THEN 100.0
                            WHEN bp.swing = true THEN 0.0
                            ELSE NULL END) as contact_rate,

                    -- Batted Ball Quality (when available)
                    AVG(CASE WHEN bp.launch_speed IS NOT NULL THEN bp.launch_speed END) as avg_exit_velo,
                    SUM(CASE WHEN bp.launch_speed >= 95 THEN 1 ELSE 0 END) as hard_hit_balls,
                    SUM(CASE WHEN bp.trajectory IN ('line_drive', 'fly_ball') THEN 1 ELSE 0 END) as balls_in_air

                FROM milb_batter_pitches bp
                LEFT JOIN prospects p ON bp.mlb_batter_id = p.mlb_id
                WHERE bp.season = 2025
                GROUP BY bp.mlb_batter_id, p.name, p.age, bp.level
                HAVING COUNT(DISTINCT CASE
                    WHEN bp.is_final_pitch = true
                    THEN bp.game_pk || '_' || bp.at_bat_index
                END) >= 1
            )
            SELECT
                mlb_batter_id,
                COALESCE(name, 'Unknown') as name,
                age,
                level,
                games,
                total_pa,
                singles,
                doubles,
                triples,
                home_runs,
                walks,
                strikeouts,

                -- Component Scores with extreme safety
                COALESCE(
                    -- Discipline Score (40% weight): zone awareness, contact, chase rate, walks
                    (COALESCE(100.0 - chase_rate, 50) * 0.3 +  -- Lower chase is better
                     COALESCE(contact_rate, 75) * 0.3 +          -- Higher contact is better
                     COALESCE(zone_rate, 50) * 0.2 +             -- Zone awareness
                     COALESCE((walks * 100.0 / NULLIF(total_pa, 0)), 8) * 0.2),  -- Walk rate
                    50.0
                ) as discipline_score,

                COALESCE(
                    -- Power Score (35% weight): hard hit rate, home runs, balls in air
                    (COALESCE((hard_hit_balls * 100.0 / NULLIF(total_pitches, 0)), 10) * 0.35 +  -- Hard hit rate
                     COALESCE((home_runs * 100.0 / NULLIF(total_pa, 0)), 3) * 0.3 +              -- Home run rate
                     COALESCE(avg_exit_velo - 75, 10) * 0.2 +                                     -- Exit velo above 75
                     COALESCE((balls_in_air * 100.0 / NULLIF(total_pitches, 0)), 30) * 0.15),    -- Balls in air
                    50.0
                ) as power_score,

                COALESCE(
                    -- Contact Score (25% weight): contact rate, batting average, K avoidance
                    (COALESCE(contact_rate, 75) * 0.4 +                                           -- Contact rate
                     COALESCE(((singles + doubles + triples + home_runs) * 100.0 / NULLIF(total_pa, 0)), 25) * 0.3 +  -- Batting average proxy
                     COALESCE(100.0 - (strikeouts * 100.0 / NULLIF(total_pa, 0)), 80) * 0.3),    -- K avoidance
                    50.0
                ) as contact_score

            FROM player_pitch_metrics
            ORDER BY total_pa DESC
            LIMIT 5
        """

        result = await db.execute(text(query))
        players_data = [dict(row._mapping) for row in result]

        print(f"\nFound {len(players_data)} players")

        # Check the type of each field
        if players_data:
            print("\n=== Checking data types for first player ===")
            player = players_data[0]

            for key, value in player.items():
                value_type = type(value).__name__
                print(f"{key:20}: {value_type:15} = {value}")

                # Try operations that might fail
                if isinstance(value, (int, float, Decimal)) and value is not None:
                    try:
                        # Test float conversion
                        float_val = float(value)
                        # Test multiplication
                        result = float_val * 0.5
                        print(f"  -> Can convert to float and multiply: {result}")
                    except Exception as e:
                        print(f"  -> ERROR: {e}")

    await engine.dispose()
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(debug_decimal_issue())