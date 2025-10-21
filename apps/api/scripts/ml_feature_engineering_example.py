"""
Machine Learning Feature Engineering Example
=============================================

This script demonstrates how to combine:
1. Fangraphs tool grades (from new tables)
2. MiLB performance statistics (from milb_game_logs)
3. Physical attributes
4. Pitch-by-pitch data (for pitchers)

To create comprehensive ML features for prospect ranking prediction.

Database: Railway PostgreSQL
Author: BMad Party Mode Team
Date: 2025-10-19
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def get_hitter_ml_features(conn, season=2024):
    """
    Get comprehensive ML features for hitters combining Fangraphs grades and MiLB stats
    """
    print(f"\n{'='*80}")
    print(f"HITTER ML FEATURES FOR {season}")
    print(f"{'='*80}\n")

    query = """
    WITH season_stats AS (
        -- Aggregate season stats for each hitter
        SELECT
            gl.mlb_player_id,
            gl.season,
            gl.level,
            -- Counting stats
            SUM(games_played) as games,
            SUM(at_bats) as ab,
            SUM(hits) as h,
            SUM(doubles) as doubles,
            SUM(triples) as triples,
            SUM(home_runs) as hr,
            SUM(rbi) as rbi,
            SUM(walks) as bb,
            SUM(strike_outs) as k,
            SUM(stolen_bases) as sb,
            SUM(caught_stealing) as cs,

            -- Rate stats (weighted avg by at_bats)
            SUM(batting_avg * at_bats) / NULLIF(SUM(at_bats), 0) as avg,
            SUM(on_base_pct * plate_appearances) / NULLIF(SUM(plate_appearances), 0) as obp,
            SUM(slugging_pct * at_bats) / NULLIF(SUM(at_bats), 0) as slg,
            SUM(ops * plate_appearances) / NULLIF(SUM(plate_appearances), 0) as ops,

            -- Age at midseason
            EXTRACT(YEAR FROM AGE(DATE($1 || '-07-01'), p.birth_date)) as age_at_season

        FROM milb_game_logs gl
        JOIN prospects p ON gl.mlb_player_id::varchar = p.mlb_player_id
        WHERE gl.season = $1
        AND gl.at_bats > 0
        GROUP BY gl.mlb_player_id, gl.season, gl.level, p.birth_date
    ),
    level_ranks AS (
        -- Rank players by OPS within their age group at each level
        SELECT
            mlb_player_id,
            season,
            level,
            age_at_season,
            ops,
            PERCENT_RANK() OVER (
                PARTITION BY level, age_at_season
                ORDER BY ops
            ) as ops_percentile_by_age
        FROM season_stats
    ),
    best_level_stats AS (
        -- Get stats from player's highest level in season
        SELECT DISTINCT ON (mlb_player_id)
            mlb_player_id,
            season,
            level,
            age_at_season,
            games,
            ab,
            h,
            doubles,
            triples,
            hr,
            rbi,
            bb,
            k,
            sb,
            cs,
            avg,
            obp,
            slg,
            ops,
            ops_percentile_by_age
        FROM season_stats ss
        JOIN level_ranks lr USING (mlb_player_id, season, level)
        ORDER BY mlb_player_id,
            CASE level
                WHEN 'AAA' THEN 1
                WHEN 'AA' THEN 2
                WHEN 'A+' THEN 3
                WHEN 'A' THEN 4
                ELSE 5
            END
    )
    SELECT
        p.name,
        p.position,
        p.organization,

        -- Fangraphs Grades (scouting)
        fg.hit_current,
        fg.hit_future,
        fg.game_power_current,
        fg.game_power_future,
        fg.speed_current,
        fg.speed_future,
        fg.fielding_current,
        fg.fielding_future,
        fg.fv as fangraphs_fv,
        fg.top_100_rank,

        -- Physical Attributes
        phys.frame_grade,
        phys.athleticism_grade,
        phys.arm_grade,

        -- Performance Stats
        s.level as highest_level,
        s.age_at_season,
        s.games,
        s.ab,
        s.avg,
        s.obp,
        s.slg,
        s.ops,
        s.ops_percentile_by_age,

        -- Derived Features
        ROUND((s.hr::numeric / NULLIF(s.ab, 0) * 100), 2) as hr_per_ab_pct,
        ROUND((s.bb::numeric / NULLIF(s.k, 0)), 2) as bb_k_ratio,
        ROUND((s.sb::numeric / NULLIF(s.sb + s.cs, 0) * 100), 2) as sb_success_rate,

        -- Age-adjusted features (how young for their level)
        CASE s.level
            WHEN 'AAA' THEN 24.5 - s.age_at_season  -- AAA avg age ~24.5
            WHEN 'AA' THEN 23.5 - s.age_at_season   -- AA avg age ~23.5
            WHEN 'A+' THEN 22.5 - s.age_at_season   -- A+ avg age ~22.5
            WHEN 'A' THEN 21.5 - s.age_at_season    -- A avg age ~21.5
            ELSE 0
        END as age_advantage_years,

        -- Composite power-speed score
        SQRT((s.hr * s.sb)::numeric) as power_speed_number

    FROM prospects p
    JOIN fangraphs_hitter_grades fg ON p.fg_player_id = fg.fangraphs_player_id
    LEFT JOIN fangraphs_physical_attributes phys ON p.fg_player_id = phys.fangraphs_player_id
    LEFT JOIN best_level_stats s ON p.mlb_player_id = s.mlb_player_id::varchar
    WHERE s.ab >= 50  -- Minimum PA threshold
    ORDER BY fg.fv DESC NULLS LAST, s.ops DESC NULLS LAST
    LIMIT 50
    """

    rows = await conn.fetch(query, season)

    df = pd.DataFrame(rows, columns=[
        'name', 'position', 'organization',
        'hit_current', 'hit_future', 'game_power_current', 'game_power_future',
        'speed_current', 'speed_future', 'fielding_current', 'fielding_future',
        'fangraphs_fv', 'top_100_rank',
        'frame_grade', 'athleticism_grade', 'arm_grade',
        'highest_level', 'age_at_season', 'games', 'ab', 'avg', 'obp', 'slg', 'ops',
        'ops_percentile_by_age', 'hr_per_ab_pct', 'bb_k_ratio', 'sb_success_rate',
        'age_advantage_years', 'power_speed_number'
    ])

    print(f"Retrieved {len(df)} hitters with complete data")
    print(f"\nTop 10 by FV + OPS:")
    print(df[['name', 'fangraphs_fv', 'ops', 'ops_percentile_by_age', 'age_advantage_years']].head(10))

    return df


async def get_pitcher_ml_features(conn, season=2024):
    """
    Get comprehensive ML features for pitchers combining Fangraphs grades and MiLB stats
    """
    print(f"\n{'='*80}")
    print(f"PITCHER ML FEATURES FOR {season}")
    print(f"{'='*80}\n")

    query = """
    WITH season_stats AS (
        SELECT
            gl.mlb_player_id,
            gl.season,
            gl.level,
            -- Counting stats
            SUM(games_played) as games,
            SUM(games_started) as gs,
            SUM(innings_pitched) as ip,
            SUM(earned_runs) as er,
            SUM(hits_allowed) as h,
            SUM(walks) as bb,
            SUM(strike_outs) as k,
            SUM(home_runs_allowed) as hr,

            -- Rate stats (weighted avg by IP)
            SUM(era * innings_pitched) / NULLIF(SUM(innings_pitched), 0) as era,
            SUM(whip * innings_pitched) / NULLIF(SUM(innings_pitched), 0) as whip,
            SUM(k_per_9 * innings_pitched) / NULLIF(SUM(innings_pitched), 0) as k9,
            SUM(bb_per_9 * innings_pitched) / NULLIF(SUM(innings_pitched), 0) as bb9,

            -- Age
            EXTRACT(YEAR FROM AGE(DATE($1 || '-07-01'), p.birth_date)) as age_at_season

        FROM milb_game_logs gl
        JOIN prospects p ON gl.mlb_player_id::varchar = p.mlb_player_id
        WHERE gl.season = $1
        AND gl.innings_pitched > 0
        GROUP BY gl.mlb_player_id, gl.season, gl.level, p.birth_date
    ),
    pitch_data_features AS (
        -- Get pitch arsenal characteristics
        SELECT
            mlb_pitcher_id as mlb_player_id,
            -- Fastball metrics
            AVG(CASE WHEN pitch_type IN ('FF', 'FT', 'SI') THEN start_speed END) as avg_fb_velo,
            MAX(CASE WHEN pitch_type IN ('FF', 'FT', 'SI') THEN start_speed END) as max_fb_velo,

            -- Breaking ball metrics
            AVG(CASE WHEN pitch_type IN ('SL', 'CU', 'KC') THEN start_speed END) as avg_breaking_velo,
            AVG(CASE WHEN pitch_type IN ('SL', 'CU', 'KC') THEN spin_rate END) as avg_breaking_spin,

            -- Offspeed metrics
            AVG(CASE WHEN pitch_type = 'CH' THEN start_speed END) as avg_ch_velo,

            -- Pitch mix
            COUNT(DISTINCT pitch_type) as pitch_types_thrown,

            -- Strike rate
            SUM(CASE WHEN is_strike THEN 1 ELSE 0 END)::float / COUNT(*) as strike_rate

        FROM milb_pitcher_pitches
        WHERE season = $1
        GROUP BY mlb_pitcher_id
    ),
    best_level_stats AS (
        SELECT DISTINCT ON (mlb_player_id)
            *
        FROM season_stats
        ORDER BY mlb_player_id,
            CASE level
                WHEN 'AAA' THEN 1
                WHEN 'AA' THEN 2
                WHEN 'A+' THEN 3
                WHEN 'A' THEN 4
                ELSE 5
            END
    )
    SELECT
        p.name,
        p.position,
        p.organization,

        -- Fangraphs Grades
        fg.fb_current,
        fg.fb_future,
        fg.sl_current,
        fg.sl_future,
        fg.cb_current,
        fg.cb_future,
        fg.ch_current,
        fg.ch_future,
        fg.cmd_current,
        fg.cmd_future,
        fg.velocity_sits_low,
        fg.velocity_sits_high,
        fg.velocity_tops,
        fg.fv as fangraphs_fv,
        fg.top_100_rank,
        fg.tj_date,

        -- Physical
        phys.frame_grade,
        phys.athleticism_grade,
        phys.delivery_grade,

        -- Performance stats
        s.level as highest_level,
        s.age_at_season,
        s.games,
        s.gs,
        s.ip,
        s.era,
        s.whip,
        s.k9,
        s.bb9,

        -- Pitch tracking data
        pd.avg_fb_velo,
        pd.max_fb_velo,
        pd.avg_breaking_velo,
        pd.avg_breaking_spin,
        pd.avg_ch_velo,
        pd.pitch_types_thrown,
        pd.strike_rate,

        -- Derived features
        ROUND((s.k::numeric / NULLIF(s.bb, 0)), 2) as k_bb_ratio,
        ROUND((s.k::numeric / NULLIF(s.ip, 0)), 2) as k_per_ip,

        -- Age-adjusted
        CASE s.level
            WHEN 'AAA' THEN 25.0 - s.age_at_season
            WHEN 'AA' THEN 24.0 - s.age_at_season
            WHEN 'A+' THEN 23.0 - s.age_at_season
            WHEN 'A' THEN 22.0 - s.age_at_season
            ELSE 0
        END as age_advantage_years,

        -- Stuff composite score (higher velo + higher secondary grades = better)
        (COALESCE(pd.avg_fb_velo, 0) - 90) * 2 +
        COALESCE(fg.sl_future, 0) +
        COALESCE(fg.cb_future, 0) +
        COALESCE(fg.ch_future, 0) as stuff_composite

    FROM prospects p
    JOIN fangraphs_pitcher_grades fg ON p.fg_player_id = fg.fangraphs_player_id
    LEFT JOIN fangraphs_physical_attributes phys ON p.fg_player_id = phys.fangraphs_player_id
    LEFT JOIN best_level_stats s ON p.mlb_player_id = s.mlb_player_id::varchar
    LEFT JOIN pitch_data_features pd ON p.mlb_player_id::integer = pd.mlb_player_id
    WHERE s.ip >= 20  -- Minimum IP threshold
    ORDER BY fg.fv DESC NULLS LAST, s.era ASC NULLS LAST
    LIMIT 50
    """

    rows = await conn.fetch(query, season)

    df = pd.DataFrame(rows, columns=[
        'name', 'position', 'organization',
        'fb_current', 'fb_future', 'sl_current', 'sl_future',
        'cb_current', 'cb_future', 'ch_current', 'ch_future',
        'cmd_current', 'cmd_future',
        'velocity_sits_low', 'velocity_sits_high', 'velocity_tops',
        'fangraphs_fv', 'top_100_rank', 'tj_date',
        'frame_grade', 'athleticism_grade', 'delivery_grade',
        'highest_level', 'age_at_season', 'games', 'gs', 'ip', 'era', 'whip', 'k9', 'bb9',
        'avg_fb_velo', 'max_fb_velo', 'avg_breaking_velo', 'avg_breaking_spin',
        'avg_ch_velo', 'pitch_types_thrown', 'strike_rate',
        'k_bb_ratio', 'k_per_ip', 'age_advantage_years', 'stuff_composite'
    ])

    print(f"Retrieved {len(df)} pitchers with complete data")
    print(f"\nTop 10 by FV + Stuff:")
    print(df[['name', 'fangraphs_fv', 'avg_fb_velo', 'k9', 'era', 'stuff_composite']].head(10))

    return df


async def main():
    """
    Main execution - generate ML-ready datasets
    """
    print("="*80)
    print("ML FEATURE ENGINEERING - COMBINING FANGRAPHS + MILB DATA")
    print("="*80)

    conn = await asyncpg.connect(DATABASE_URL)
    print("[OK] Connected to database\n")

    # Generate hitter features
    hitters_df = await get_hitter_ml_features(conn, season=2024)

    # Generate pitcher features
    pitchers_df = await get_pitcher_ml_features(conn, season=2024)

    # Save to CSV for ML model training
    hitters_df.to_csv('ml_hitters_features_2024.csv', index=False)
    pitchers_df.to_csv('ml_pitchers_features_2024.csv', index=False)

    print(f"\n{'='*80}")
    print("FEATURE SETS SAVED!")
    print(f"{'='*80}")
    print(f"  - ml_hitters_features_2024.csv ({len(hitters_df)} rows)")
    print(f"  - ml_pitchers_features_2024.csv ({len(pitchers_df)} rows)")

    print(f"\n{'='*80}")
    print("NEXT STEPS FOR ML:")
    print(f"{'='*80}")
    print("1. Load CSVs into your ML framework (scikit-learn, XGBoost, etc.)")
    print("2. Target variable options:")
    print("   - fangraphs_fv: Predict Future Value grade")
    print("   - top_100_rank: Predict if player will be Top 100")
    print("   - Combine with future MLB data to predict WAR, games played, etc.")
    print("3. Feature engineering ideas:")
    print("   - Normalize grades by position")
    print("   - Create interaction terms (e.g., hit_future * age_advantage)")
    print("   - Time-series features (trend over multiple seasons)")
    print("4. Model types to try:")
    print("   - XGBoost/LightGBM for gradient boosting")
    print("   - Random Forest for feature importance")
    print("   - Neural networks for complex interactions")
    print("5. Validation:")
    print("   - Train on 2021-2023, validate on 2024, test on 2025")
    print("   - Cross-validate within position groups")
    print("   - Check calibration against scouting consensus (FV)")

    await conn.close()
    print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
