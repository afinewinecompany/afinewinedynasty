"""
Aggregate Statcast play-by-play data into player-level metrics.

Calculates advanced metrics like:
- Fly Ball Exit Velocity (avg EV on fly balls only)
- Average Launch Angle (overall and on hard hits)
- Max Exit Velocity
- 90th Percentile Exit Velocity
- Hard Hit % (95+ mph)
- Barrel % (specific EV/LA combinations)
- Ground Ball %, Line Drive %, Fly Ball %
"""

import asyncio
import pandas as pd
from sqlalchemy import text
from app.db.database import engine
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def load_statcast_data() -> pd.DataFrame:
    """Load all plate appearances with Statcast data."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                mlb_player_id,
                season,
                level,
                launch_speed,
                launch_angle,
                total_distance,
                trajectory,
                hardness
            FROM milb_plate_appearances
            WHERE launch_speed IS NOT NULL
            ORDER BY mlb_player_id, season, level
        """))

        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'season', 'level', 'launch_speed',
        'launch_angle', 'total_distance', 'trajectory', 'hardness'
    ])

    logger.info(f"Loaded {len(df):,} batted balls with Statcast data")
    logger.info(f"Unique players: {df['mlb_player_id'].nunique()}")

    return df


def calculate_barrel(row):
    """
    Calculate if a batted ball is a barrel.

    Barrel definition (simplified):
    - EV >= 98 mph AND LA between 26-30 degrees, OR
    - EV >= 99 mph AND LA between 24-33 degrees, OR
    - EV >= 100 mph AND LA between 22-35 degrees, OR
    - EV >= 101 mph AND LA between 20-37 degrees
    """
    ev = row['launch_speed']
    la = row['launch_angle']

    if pd.isna(ev) or pd.isna(la):
        return False

    if ev >= 101 and 20 <= la <= 37:
        return True
    elif ev >= 100 and 22 <= la <= 35:
        return True
    elif ev >= 99 and 24 <= la <= 33:
        return True
    elif ev >= 98 and 26 <= la <= 30:
        return True

    return False


def aggregate_player_statcast(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate Statcast metrics by player-season-level."""

    # Add calculated fields
    df['is_hard_hit'] = df['launch_speed'] >= 95
    df['is_barrel'] = df.apply(calculate_barrel, axis=1)

    # Map trajectories to standard types
    trajectory_map = {
        'fly_ball': 'FB',
        'ground_ball': 'GB',
        'line_drive': 'LD',
        'popup': 'PU'
    }
    df['trajectory_clean'] = df['trajectory'].map(trajectory_map)

    # Group by player-season-level
    grouped = df.groupby(['mlb_player_id', 'season', 'level'])

    metrics = []

    for (player_id, season, level), group in grouped:
        total_batted_balls = len(group)

        if total_batted_balls == 0:
            continue

        # Exit Velocity Metrics
        avg_ev = group['launch_speed'].mean()
        max_ev = group['launch_speed'].max()
        ev_90th = group['launch_speed'].quantile(0.90)

        # Launch Angle Metrics
        avg_la = group['launch_angle'].mean()

        # Launch angle on hard hits only
        hard_hits = group[group['is_hard_hit']]
        avg_la_hard = hard_hits['launch_angle'].mean() if len(hard_hits) > 0 else None

        # Fly Ball Exit Velocity
        fly_balls = group[group['trajectory_clean'] == 'FB']
        fb_ev = fly_balls['launch_speed'].mean() if len(fly_balls) > 0 else None

        # Hard Hit %
        hard_hit_pct = (group['is_hard_hit'].sum() / total_batted_balls) * 100

        # Barrel %
        barrel_pct = (group['is_barrel'].sum() / total_batted_balls) * 100

        # Batted Ball Type %
        gb_pct = ((group['trajectory_clean'] == 'GB').sum() / total_batted_balls) * 100
        ld_pct = ((group['trajectory_clean'] == 'LD').sum() / total_batted_balls) * 100
        fb_pct = ((group['trajectory_clean'] == 'FB').sum() / total_batted_balls) * 100
        pu_pct = ((group['trajectory_clean'] == 'PU').sum() / total_batted_balls) * 100

        # Average Distance
        avg_distance = group['total_distance'].mean()
        max_distance = group['total_distance'].max()

        metrics.append({
            'mlb_player_id': player_id,
            'season': season,
            'level': level,
            'batted_balls': total_batted_balls,

            # Exit Velocity
            'avg_ev': round(avg_ev, 1) if pd.notna(avg_ev) else None,
            'max_ev': round(max_ev, 1) if pd.notna(max_ev) else None,
            'ev_90th': round(ev_90th, 1) if pd.notna(ev_90th) else None,
            'hard_hit_pct': round(hard_hit_pct, 1),

            # Launch Angle
            'avg_la': round(avg_la, 1) if pd.notna(avg_la) else None,
            'avg_la_hard': round(avg_la_hard, 1) if pd.notna(avg_la_hard) else None,

            # Fly Ball EV
            'fb_ev': round(fb_ev, 1) if pd.notna(fb_ev) else None,

            # Advanced Metrics
            'barrel_pct': round(barrel_pct, 1),

            # Batted Ball Distribution
            'gb_pct': round(gb_pct, 1),
            'ld_pct': round(ld_pct, 1),
            'fb_pct': round(fb_pct, 1),
            'pu_pct': round(pu_pct, 1),

            # Distance
            'avg_distance': round(avg_distance, 1) if pd.notna(avg_distance) else None,
            'max_distance': round(max_distance, 1) if pd.notna(max_distance) else None
        })

    result_df = pd.DataFrame(metrics)
    logger.info(f"Aggregated metrics for {len(result_df)} player-season-level combinations")

    return result_df


async def save_aggregated_metrics(df: pd.DataFrame):
    """Save aggregated Statcast metrics to database."""

    # Create table
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS milb_statcast_metrics (
                id SERIAL PRIMARY KEY,
                mlb_player_id INTEGER NOT NULL,
                season INTEGER NOT NULL,
                level VARCHAR(20) NOT NULL,
                batted_balls INTEGER NOT NULL,

                -- Exit Velocity Metrics
                avg_ev FLOAT,
                max_ev FLOAT,
                ev_90th FLOAT,
                hard_hit_pct FLOAT,

                -- Launch Angle Metrics
                avg_la FLOAT,
                avg_la_hard FLOAT,

                -- Fly Ball Exit Velocity
                fb_ev FLOAT,

                -- Advanced Metrics
                barrel_pct FLOAT,

                -- Batted Ball Distribution
                gb_pct FLOAT,
                ld_pct FLOAT,
                fb_pct FLOAT,
                pu_pct FLOAT,

                -- Distance Metrics
                avg_distance FLOAT,
                max_distance FLOAT,

                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),

                UNIQUE(mlb_player_id, season, level)
            )
        """))

        # Create index
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_statcast_metrics_player
            ON milb_statcast_metrics(mlb_player_id)
        """))

        logger.info("Table created/verified")

    # Insert data
    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        async with engine.begin() as conn:
            # Check if exists
            result = await conn.execute(
                text("""
                    SELECT id FROM milb_statcast_metrics
                    WHERE mlb_player_id = :player_id
                    AND season = :season
                    AND level = :level
                """),
                {
                    'player_id': int(row['mlb_player_id']),
                    'season': int(row['season']),
                    'level': row['level']
                }
            )

            existing = result.fetchone()

            if existing:
                # Update
                await conn.execute(text("""
                    UPDATE milb_statcast_metrics
                    SET batted_balls = :batted_balls,
                        avg_ev = :avg_ev,
                        max_ev = :max_ev,
                        ev_90th = :ev_90th,
                        hard_hit_pct = :hard_hit_pct,
                        avg_la = :avg_la,
                        avg_la_hard = :avg_la_hard,
                        fb_ev = :fb_ev,
                        barrel_pct = :barrel_pct,
                        gb_pct = :gb_pct,
                        ld_pct = :ld_pct,
                        fb_pct = :fb_pct,
                        pu_pct = :pu_pct,
                        avg_distance = :avg_distance,
                        max_distance = :max_distance,
                        updated_at = NOW()
                    WHERE id = :id
                """), {
                    'id': existing[0],
                    'batted_balls': int(row['batted_balls']),
                    'avg_ev': float(row['avg_ev']) if pd.notna(row['avg_ev']) else None,
                    'max_ev': float(row['max_ev']) if pd.notna(row['max_ev']) else None,
                    'ev_90th': float(row['ev_90th']) if pd.notna(row['ev_90th']) else None,
                    'hard_hit_pct': float(row['hard_hit_pct']),
                    'avg_la': float(row['avg_la']) if pd.notna(row['avg_la']) else None,
                    'avg_la_hard': float(row['avg_la_hard']) if pd.notna(row['avg_la_hard']) else None,
                    'fb_ev': float(row['fb_ev']) if pd.notna(row['fb_ev']) else None,
                    'barrel_pct': float(row['barrel_pct']),
                    'gb_pct': float(row['gb_pct']),
                    'ld_pct': float(row['ld_pct']),
                    'fb_pct': float(row['fb_pct']),
                    'pu_pct': float(row['pu_pct']),
                    'avg_distance': float(row['avg_distance']) if pd.notna(row['avg_distance']) else None,
                    'max_distance': float(row['max_distance']) if pd.notna(row['max_distance']) else None
                })
                updated += 1
            else:
                # Insert
                await conn.execute(text("""
                    INSERT INTO milb_statcast_metrics
                    (mlb_player_id, season, level, batted_balls,
                     avg_ev, max_ev, ev_90th, hard_hit_pct,
                     avg_la, avg_la_hard, fb_ev, barrel_pct,
                     gb_pct, ld_pct, fb_pct, pu_pct,
                     avg_distance, max_distance)
                    VALUES
                    (:player_id, :season, :level, :batted_balls,
                     :avg_ev, :max_ev, :ev_90th, :hard_hit_pct,
                     :avg_la, :avg_la_hard, :fb_ev, :barrel_pct,
                     :gb_pct, :ld_pct, :fb_pct, :pu_pct,
                     :avg_distance, :max_distance)
                """), {
                    'player_id': int(row['mlb_player_id']),
                    'season': int(row['season']),
                    'level': row['level'],
                    'batted_balls': int(row['batted_balls']),
                    'avg_ev': float(row['avg_ev']) if pd.notna(row['avg_ev']) else None,
                    'max_ev': float(row['max_ev']) if pd.notna(row['max_ev']) else None,
                    'ev_90th': float(row['ev_90th']) if pd.notna(row['ev_90th']) else None,
                    'hard_hit_pct': float(row['hard_hit_pct']),
                    'avg_la': float(row['avg_la']) if pd.notna(row['avg_la']) else None,
                    'avg_la_hard': float(row['avg_la_hard']) if pd.notna(row['avg_la_hard']) else None,
                    'fb_ev': float(row['fb_ev']) if pd.notna(row['fb_ev']) else None,
                    'barrel_pct': float(row['barrel_pct']),
                    'gb_pct': float(row['gb_pct']),
                    'ld_pct': float(row['ld_pct']),
                    'fb_pct': float(row['fb_pct']),
                    'pu_pct': float(row['pu_pct']),
                    'avg_distance': float(row['avg_distance']) if pd.notna(row['avg_distance']) else None,
                    'max_distance': float(row['max_distance']) if pd.notna(row['max_distance']) else None
                })
                inserted += 1

        if (inserted + updated) % 100 == 0:
            logger.info(f"Progress: {inserted} inserted, {updated} updated")

    logger.info(f"Complete: {inserted} inserted, {updated} updated")


async def show_sample_metrics():
    """Display sample aggregated metrics."""
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT
                mlb_player_id,
                season,
                level,
                batted_balls,
                avg_ev,
                max_ev,
                ev_90th,
                hard_hit_pct,
                avg_la,
                avg_la_hard,
                fb_ev,
                barrel_pct
            FROM milb_statcast_metrics
            WHERE batted_balls >= 50
            ORDER BY avg_ev DESC
            LIMIT 10
        """))

        rows = result.fetchall()

    print("\n" + "="*100)
    print("TOP 10 PLAYERS BY AVG EXIT VELOCITY (min 50 batted balls)")
    print("="*100)
    print(f"{'Player ID':<12} {'Season':<8} {'Level':<8} {'BBalls':<8} {'Avg EV':<8} {'Max EV':<8} {'90th%':<8} {'HH%':<8} {'Avg LA':<8} {'LA Hard':<8} {'FB EV':<8} {'Barrel%':<8}")
    print("-"*100)

    for row in rows:
        print(f"{row[0]:<12} {row[1]:<8} {row[2]:<8} {row[3]:<8} {row[4] or 'N/A':<8} {row[5] or 'N/A':<8} {row[6] or 'N/A':<8} {row[7]:<8.1f} {row[8] or 'N/A':<8} {row[9] or 'N/A':<8} {row[10] or 'N/A':<8} {row[11]:<8.1f}")


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Statcast Metrics Aggregation")
    logger.info("="*80)

    # Load raw Statcast data
    df = await load_statcast_data()

    if len(df) == 0:
        logger.warning("No Statcast data found. Make sure collection has run first.")
        return

    # Aggregate metrics
    metrics_df = aggregate_player_statcast(df)

    # Save to database
    await save_aggregated_metrics(metrics_df)

    # Show samples
    await show_sample_metrics()

    logger.info("\n" + "="*80)
    logger.info("Aggregation Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
