"""
Aggregate pitcher Statcast metrics from pitch-by-pitch data.

Creates summary statistics grouped by player/season/level similar to
the milb_statcast_metrics table for hitters.

Requires: mlb_statcast_pitching table to be populated first
"""

import asyncio
import logging
from sqlalchemy import text
from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def create_pitcher_statcast_metrics_table():
    """Create table to store aggregated pitcher Statcast metrics."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS pitcher_statcast_metrics (
                id SERIAL PRIMARY KEY,
                mlb_player_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                level VARCHAR(10) NOT NULL,

                -- Pitch counts
                total_pitches INTEGER,

                -- Velocity (by pitch type)
                avg_fastball_velo FLOAT,
                max_fastball_velo FLOAT,
                avg_breaking_velo FLOAT,
                avg_offspeed_velo FLOAT,

                -- Spin rate
                avg_fastball_spin FLOAT,
                avg_breaking_spin FLOAT,
                avg_slider_spin FLOAT,

                -- Movement (inches)
                avg_fastball_horiz_break FLOAT,
                avg_fastball_vert_break FLOAT,
                avg_breaking_horiz_break FLOAT,
                avg_breaking_vert_break FLOAT,

                -- Release point consistency
                avg_release_x FLOAT,
                std_release_x FLOAT,
                avg_release_z FLOAT,
                std_release_z FLOAT,
                avg_extension FLOAT,

                -- Pitch mix
                fastball_pct FLOAT,
                breaking_pct FLOAT,
                offspeed_pct FLOAT,

                -- Results
                whiff_rate FLOAT,
                chase_rate FLOAT,
                zone_rate FLOAT,
                hard_contact_rate FLOAT,

                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                UNIQUE(mlb_player_id, season, level)
            )
        """))
        logger.info("Created pitcher_statcast_metrics table")


async def aggregate_pitcher_statcast():
    """Aggregate pitch-by-pitch data into summary metrics."""

    async with engine.begin() as conn:
        # Check if we have any data
        result = await conn.execute(text("SELECT COUNT(*) FROM mlb_statcast_pitching"))
        count = result.scalar()

        if count == 0:
            logger.warning("No pitch-by-pitch data found in mlb_statcast_pitching")
            logger.info("Run collect_mlb_statcast.py first to populate pitcher data")
            return

        logger.info(f"Aggregating {count:,} pitches...")

        # Aggregate by player/season/level
        await conn.execute(text("""
            INSERT INTO pitcher_statcast_metrics (
                mlb_player_id, season, level,
                total_pitches,
                avg_fastball_velo, max_fastball_velo,
                avg_breaking_velo, avg_offspeed_velo,
                avg_fastball_spin, avg_breaking_spin, avg_slider_spin,
                avg_fastball_horiz_break, avg_fastball_vert_break,
                avg_breaking_horiz_break, avg_breaking_vert_break,
                avg_release_x, std_release_x,
                avg_release_z, std_release_z,
                avg_extension,
                fastball_pct, breaking_pct, offspeed_pct,
                whiff_rate, chase_rate, zone_rate
            )
            SELECT
                mlb_player_id,
                season,
                'MLB' as level,  -- All MLB data

                COUNT(*) as total_pitches,

                -- Fastball velocity (4-seam, 2-seam, sinker, cutter)
                AVG(CASE WHEN pitch_type IN ('FF', 'FT', 'SI', 'FC') THEN release_speed END) as avg_fastball_velo,
                MAX(CASE WHEN pitch_type IN ('FF', 'FT', 'SI', 'FC') THEN release_speed END) as max_fastball_velo,

                -- Breaking ball velocity (slider, curve, slurve)
                AVG(CASE WHEN pitch_type IN ('SL', 'CU', 'KC', 'SV') THEN release_speed END) as avg_breaking_velo,

                -- Offspeed velocity (change, split, screwball)
                AVG(CASE WHEN pitch_type IN ('CH', 'FS', 'SC') THEN release_speed END) as avg_offspeed_velo,

                -- Spin rates
                AVG(CASE WHEN pitch_type IN ('FF', 'FT', 'SI') THEN release_spin_rate END) as avg_fastball_spin,
                AVG(CASE WHEN pitch_type IN ('CU', 'KC') THEN release_spin_rate END) as avg_breaking_spin,
                AVG(CASE WHEN pitch_type = 'SL' THEN release_spin_rate END) as avg_slider_spin,

                -- Movement (pfx = break from spin)
                AVG(CASE WHEN pitch_type IN ('FF', 'FT') THEN pfx_x END) as avg_fastball_horiz_break,
                AVG(CASE WHEN pitch_type IN ('FF', 'FT') THEN pfx_z END) as avg_fastball_vert_break,
                AVG(CASE WHEN pitch_type IN ('SL', 'CU') THEN pfx_x END) as avg_breaking_horiz_break,
                AVG(CASE WHEN pitch_type IN ('SL', 'CU') THEN pfx_z END) as avg_breaking_vert_break,

                -- Release point
                AVG(release_pos_x) as avg_release_x,
                STDDEV(release_pos_x) as std_release_x,
                AVG(release_pos_z) as avg_release_z,
                STDDEV(release_pos_z) as std_release_z,
                AVG(release_extension) as avg_extension,

                -- Pitch mix percentages
                SUM(CASE WHEN pitch_type IN ('FF', 'FT', 'SI', 'FC') THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as fastball_pct,
                SUM(CASE WHEN pitch_type IN ('SL', 'CU', 'KC', 'SV') THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as breaking_pct,
                SUM(CASE WHEN pitch_type IN ('CH', 'FS', 'SC') THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as offspeed_pct,

                -- Results (description = 'swinging_strike', 'foul', etc.)
                SUM(CASE WHEN description = 'swinging_strike' THEN 1 ELSE 0 END)::FLOAT /
                    NULLIF(SUM(CASE WHEN description IN ('swinging_strike', 'foul', 'hit_into_play') THEN 1 ELSE 0 END), 0) * 100 as whiff_rate,

                -- Chase rate (swings outside zone)
                SUM(CASE WHEN zone > 9 AND description IN ('swinging_strike', 'foul', 'hit_into_play') THEN 1 ELSE 0 END)::FLOAT /
                    NULLIF(SUM(CASE WHEN zone > 9 THEN 1 ELSE 0 END), 0) * 100 as chase_rate,

                -- Zone rate (pitches in strike zone)
                SUM(CASE WHEN zone <= 9 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) * 100 as zone_rate

            FROM mlb_statcast_pitching
            WHERE release_speed IS NOT NULL
            GROUP BY mlb_player_id, season
            ON CONFLICT (mlb_player_id, season, level)
            DO UPDATE SET
                total_pitches = EXCLUDED.total_pitches,
                avg_fastball_velo = EXCLUDED.avg_fastball_velo,
                max_fastball_velo = EXCLUDED.max_fastball_velo,
                updated_at = NOW()
        """))

        # Get count of players aggregated
        result = await conn.execute(text("SELECT COUNT(DISTINCT mlb_player_id) FROM pitcher_statcast_metrics"))
        player_count = result.scalar()

        logger.info(f"✅ Aggregated Statcast data for {player_count} pitchers")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("PITCHER STATCAST AGGREGATION")
    logger.info("="*80)

    await create_pitcher_statcast_metrics_table()
    await aggregate_pitcher_statcast()

    logger.info("\n" + "="*80)
    logger.info("DONE! Pitcher Statcast metrics ready for use in rankings")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
