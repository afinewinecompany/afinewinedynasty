"""
Create ML Training Data for MLB Expectation Classification
===========================================================

Combines multi-year Fangraphs grades with MiLB performance data
to create feature-rich training/validation/test datasets.

Output: 3 CSV files (train/val/test) ready for XGBoost/LightGBM training
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def get_hitter_features(conn, data_year: int, split_name: str):
    """
    Extract features for hitter prospects.

    Features include:
    - Fangraphs tool grades (hit, power, speed, fielding)
    - Physical attributes (frame, athleticism, arm)
    - MiLB performance stats (from prior season)
    - Age and level context
    - Multi-year trends (for prospects with history)
    """

    print(f"\nExtracting hitter features for {split_name} ({data_year})...")

    query = """
    WITH prior_season_stats AS (
        SELECT
            p.id as prospect_id,
            p.mlb_player_id,

            -- Aggregate prior season stats (weighted by PA)
            SUM(gl.plate_appearances) as total_pa,
            SUM(gl.at_bats) as total_ab,
            SUM(gl.hits) as total_hits,
            SUM(gl.doubles) as total_doubles,
            SUM(gl.triples) as total_triples,
            SUM(gl.home_runs) as total_hr,
            SUM(gl.walks) as total_bb,
            SUM(gl.strikeouts) as total_k,
            SUM(gl.stolen_bases) as total_sb,
            SUM(gl.caught_stealing) as total_cs,

            -- Weighted averages
            CASE WHEN SUM(gl.plate_appearances) > 0
                THEN SUM(gl.on_base_pct * gl.plate_appearances) / SUM(gl.plate_appearances)
                ELSE NULL END as avg_obp,
            CASE WHEN SUM(gl.plate_appearances) > 0
                THEN SUM(gl.slugging_pct * gl.plate_appearances) / SUM(gl.plate_appearances)
                ELSE NULL END as avg_slg,

            -- Level distribution
            MAX(CASE WHEN gl.level = 'AAA' THEN 1 ELSE 0 END) as played_aaa,
            MAX(CASE WHEN gl.level = 'AA' THEN 1 ELSE 0 END) as played_aa,
            MAX(CASE WHEN gl.level = 'A+' THEN 1 ELSE 0 END) as played_a_plus,

            -- Best level achieved
            MAX(CASE
                WHEN gl.level = 'AAA' THEN 5
                WHEN gl.level = 'AA' THEN 4
                WHEN gl.level = 'A+' THEN 3
                WHEN gl.level = 'A' THEN 2
                ELSE 1
            END) as highest_level,

            -- Age at season (calculate from birth_date if available)
            CASE WHEN p.birth_date IS NOT NULL
                THEN EXTRACT(YEAR FROM AGE(TO_DATE(($1 - 1)::text || '-07-01', 'YYYY-MM-DD'), p.birth_date))
                ELSE NULL END as avg_age

        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id = gl.mlb_player_id::varchar
            AND gl.season = $1 - 1  -- Prior season
        WHERE p.id IN (
            SELECT prospect_id FROM mlb_expectation_labels WHERE data_year = $1
        )
        GROUP BY p.id, p.mlb_player_id
    ),
    year_over_year_changes AS (
        SELECT
            fg_curr.fangraphs_player_id,

            -- FV trajectory
            fg_curr.fv - COALESCE(fg_prev.fv, fg_curr.fv) as fv_change_1yr,

            -- Tool grade changes
            fg_curr.hit_future - COALESCE(fg_prev.hit_future, fg_curr.hit_future) as hit_change,
            fg_curr.game_power_future - COALESCE(fg_prev.game_power_future, fg_curr.game_power_future) as power_change,
            fg_curr.speed_future - COALESCE(fg_prev.speed_future, fg_curr.speed_future) as speed_change

        FROM fangraphs_hitter_grades fg_curr
        LEFT JOIN fangraphs_hitter_grades fg_prev
            ON fg_curr.fangraphs_player_id = fg_prev.fangraphs_player_id
            AND fg_prev.data_year = fg_curr.data_year - 1
        WHERE fg_curr.data_year = $1
    )
    SELECT
        -- IDs
        l.prospect_id,
        l.data_year,
        p.name,
        p.position,
        p.fg_player_id as fangraphs_id,

        -- TARGET VARIABLE
        l.mlb_expectation_numeric as target,
        l.mlb_expectation as target_label,
        l.fv as fangraphs_fv,

        -- FANGRAPHS TOOL GRADES (Future values - what we expect at peak)
        fg.hit_future,
        fg.game_power_future,
        fg.raw_power_future,
        fg.speed_future,
        fg.fielding_future,
        fg.versatility_future,
        fg.pitch_sel_future,
        fg.bat_ctrl_future,
        fg.hard_hit_pct,

        -- Current vs Future gap (development potential)
        fg.hit_future - fg.hit_current as hit_upside,
        fg.game_power_future - fg.game_power_current as power_upside,
        fg.speed_future - fg.speed_current as speed_upside,
        fg.fielding_future - fg.fielding_current as fielding_upside,

        -- PHYSICAL ATTRIBUTES
        phys.frame_grade,
        phys.athleticism_grade,
        phys.arm_grade,
        CASE phys.levers
            WHEN 'Short' THEN 1
            WHEN 'Med' THEN 2
            WHEN 'Long' THEN 3
            ELSE 2 END as levers_encoded,

        -- PRIOR SEASON PERFORMANCE
        pss.total_pa,
        pss.total_ab,
        pss.total_hr,
        pss.total_sb,
        pss.avg_obp,
        pss.avg_slg,
        CASE WHEN pss.total_ab > 0
            THEN pss.total_hits::float / pss.total_ab
            ELSE NULL END as batting_avg,

        -- Derived stats
        CASE WHEN pss.total_ab > 0
            THEN (pss.total_doubles + 2*pss.total_triples + 3*pss.total_hr)::float / pss.total_ab
            ELSE NULL END as isolated_power,
        CASE WHEN pss.total_k > 0
            THEN pss.total_bb::float / pss.total_k
            ELSE NULL END as bb_k_ratio,
        CASE WHEN pss.total_pa > 0
            THEN pss.total_k::float / pss.total_pa
            ELSE NULL END as k_rate,
        CASE WHEN pss.total_pa > 0
            THEN pss.total_bb::float / pss.total_pa
            ELSE NULL END as bb_rate,

        -- Power-Speed Number
        CASE WHEN pss.total_hr + pss.total_sb > 0
            THEN (2 * pss.total_hr * pss.total_sb)::float / (pss.total_hr + pss.total_sb)
            ELSE 0 END as power_speed_number,

        -- Level context
        pss.played_aaa,
        pss.played_aa,
        pss.played_a_plus,
        pss.highest_level,
        pss.avg_age,

        -- YEAR-OVER-YEAR CHANGES
        yoy.fv_change_1yr,
        yoy.hit_change,
        yoy.power_change,
        yoy.speed_change

    FROM mlb_expectation_labels l
    JOIN prospects p ON l.prospect_id = p.id
    JOIN fangraphs_hitter_grades fg
        ON p.fg_player_id = fg.fangraphs_player_id
        AND fg.data_year = l.data_year
    LEFT JOIN fangraphs_physical_attributes phys
        ON p.fg_player_id = phys.fangraphs_player_id
        AND phys.data_year = l.data_year
    LEFT JOIN prior_season_stats pss ON l.prospect_id = pss.prospect_id
    LEFT JOIN year_over_year_changes yoy ON p.fg_player_id = yoy.fangraphs_player_id
    WHERE l.data_year = $1
    ORDER BY l.fv DESC, p.name
    """

    rows = await conn.fetch(query, data_year)
    df = pd.DataFrame([dict(r) for r in rows])

    print(f"  [OK] Extracted {len(df):,} hitter prospects")
    print(f"       Class distribution: All-Star={sum(df['target']==3)}, Regular={sum(df['target']==2)}, Part-Time={sum(df['target']==1)}, Bench={sum(df['target']==0)}")

    return df


async def get_pitcher_features(conn, data_year: int, split_name: str):
    """
    Extract features for pitcher prospects.

    Features include:
    - Fangraphs pitch grades (FB, SL, CB, CH, CMD)
    - Velocity data
    - Physical attributes
    - MiLB performance stats (from prior season)
    - Age and level context
    - Multi-year trends
    """

    print(f"\nExtracting pitcher features for {split_name} ({data_year})...")

    query = """
    WITH prior_season_stats AS (
        SELECT
            p.id as prospect_id,
            p.mlb_player_id,

            -- Aggregate prior season stats (weighted by IP)
            SUM(gl.innings_pitched) as total_ip,
            SUM(gl.earned_runs) as total_er,
            SUM(gl.hits_allowed) as total_h,
            SUM(gl.walks_allowed) as total_bb,
            SUM(gl.strikeouts) as total_k,
            SUM(gl.home_runs_allowed) as total_hr_allowed,

            -- ERA (calculated)
            CASE WHEN SUM(gl.innings_pitched) > 0
                THEN (SUM(gl.earned_runs) * 9.0) / SUM(gl.innings_pitched)
                ELSE NULL END as era,

            -- WHIP
            CASE WHEN SUM(gl.innings_pitched) > 0
                THEN (SUM(gl.walks_allowed) + SUM(gl.hits_allowed))::float / SUM(gl.innings_pitched)
                ELSE NULL END as whip,

            -- K/9, BB/9
            CASE WHEN SUM(gl.innings_pitched) > 0
                THEN (SUM(gl.strikeouts) * 9.0) / SUM(gl.innings_pitched)
                ELSE NULL END as k_per_9,
            CASE WHEN SUM(gl.innings_pitched) > 0
                THEN (SUM(gl.walks_allowed) * 9.0) / SUM(gl.innings_pitched)
                ELSE NULL END as bb_per_9,

            -- K/BB ratio
            CASE WHEN SUM(gl.walks_allowed) > 0
                THEN SUM(gl.strikeouts)::float / SUM(gl.walks_allowed)
                ELSE NULL END as k_bb_ratio,

            -- Level distribution
            MAX(CASE WHEN gl.level = 'AAA' THEN 1 ELSE 0 END) as played_aaa,
            MAX(CASE WHEN gl.level = 'AA' THEN 1 ELSE 0 END) as played_aa,
            MAX(CASE WHEN gl.level = 'A+' THEN 1 ELSE 0 END) as played_a_plus,

            -- Best level achieved
            MAX(CASE
                WHEN gl.level = 'AAA' THEN 5
                WHEN gl.level = 'AA' THEN 4
                WHEN gl.level = 'A+' THEN 3
                WHEN gl.level = 'A' THEN 2
                ELSE 1
            END) as highest_level,

            -- Age at season (calculate from birth_date if available)
            CASE WHEN p.birth_date IS NOT NULL
                THEN EXTRACT(YEAR FROM AGE(TO_DATE(($1 - 1)::text || '-07-01', 'YYYY-MM-DD'), p.birth_date))
                ELSE NULL END as avg_age

        FROM prospects p
        LEFT JOIN milb_game_logs gl
            ON p.mlb_player_id = gl.mlb_player_id::varchar
            AND gl.season = $1 - 1  -- Prior season
        WHERE p.id IN (
            SELECT prospect_id FROM mlb_expectation_labels WHERE data_year = $1
        )
        GROUP BY p.id, p.mlb_player_id
    ),
    year_over_year_changes AS (
        SELECT
            fg_curr.fangraphs_player_id,

            -- FV trajectory
            fg_curr.fv - COALESCE(fg_prev.fv, fg_curr.fv) as fv_change_1yr,

            -- Pitch grade changes
            fg_curr.fb_future - COALESCE(fg_prev.fb_future, fg_curr.fb_future) as fb_change,
            fg_curr.cmd_future - COALESCE(fg_prev.cmd_future, fg_curr.cmd_future) as cmd_change,

            -- Velocity changes
            fg_curr.velocity_sits_high - COALESCE(fg_prev.velocity_sits_high, fg_curr.velocity_sits_high) as velo_change

        FROM fangraphs_pitcher_grades fg_curr
        LEFT JOIN fangraphs_pitcher_grades fg_prev
            ON fg_curr.fangraphs_player_id = fg_prev.fangraphs_player_id
            AND fg_prev.data_year = fg_curr.data_year - 1
        WHERE fg_curr.data_year = $1
    )
    SELECT
        -- IDs
        l.prospect_id,
        l.data_year,
        p.name,
        p.position,
        p.fg_player_id as fangraphs_id,

        -- TARGET VARIABLE
        l.mlb_expectation_numeric as target,
        l.mlb_expectation as target_label,
        l.fv as fangraphs_fv,

        -- FANGRAPHS PITCH GRADES (Future values)
        fg.fb_future,
        fg.sl_future,
        fg.cb_future,
        fg.ch_future,
        fg.cmd_future,  -- Command (most important for pitchers!)

        -- Current vs Future gap (development potential)
        fg.fb_future - fg.fb_current as fb_upside,
        fg.cmd_future - fg.cmd_current as cmd_upside,

        -- VELOCITY
        fg.velocity_sits_low,
        fg.velocity_sits_high,
        fg.velocity_tops,
        (fg.velocity_sits_low + fg.velocity_sits_high) / 2.0 as velocity_avg,

        -- Pitch arsenal diversity (count of plus pitches)
        (CASE WHEN fg.fb_future >= 55 THEN 1 ELSE 0 END +
         CASE WHEN fg.sl_future >= 55 THEN 1 ELSE 0 END +
         CASE WHEN fg.cb_future >= 55 THEN 1 ELSE 0 END +
         CASE WHEN fg.ch_future >= 55 THEN 1 ELSE 0 END) as plus_pitch_count,

        -- PHYSICAL ATTRIBUTES
        phys.frame_grade,
        phys.athleticism_grade,
        phys.arm_grade,
        phys.delivery_grade,

        -- Tommy John surgery history
        CASE WHEN fg.tj_date IS NOT NULL THEN 1 ELSE 0 END as has_tj_surgery,

        -- PRIOR SEASON PERFORMANCE
        pss.total_ip,
        pss.era,
        pss.whip,
        pss.k_per_9,
        pss.bb_per_9,
        pss.k_bb_ratio,
        pss.total_k,
        pss.total_bb,
        pss.total_hr_allowed,

        -- Level context
        pss.played_aaa,
        pss.played_aa,
        pss.played_a_plus,
        pss.highest_level,
        pss.avg_age,

        -- YEAR-OVER-YEAR CHANGES
        yoy.fv_change_1yr,
        yoy.fb_change,
        yoy.cmd_change,
        yoy.velo_change

    FROM mlb_expectation_labels l
    JOIN prospects p ON l.prospect_id = p.id
    JOIN fangraphs_pitcher_grades fg
        ON p.fg_player_id = fg.fangraphs_player_id
        AND fg.data_year = l.data_year
    LEFT JOIN fangraphs_physical_attributes phys
        ON p.fg_player_id = phys.fangraphs_player_id
        AND phys.data_year = l.data_year
    LEFT JOIN prior_season_stats pss ON l.prospect_id = pss.prospect_id
    LEFT JOIN year_over_year_changes yoy ON p.fg_player_id = yoy.fangraphs_player_id
    WHERE l.data_year = $1
    ORDER BY l.fv DESC, p.name
    """

    rows = await conn.fetch(query, data_year)
    df = pd.DataFrame([dict(r) for r in rows])

    print(f"  [OK] Extracted {len(df):,} pitcher prospects")
    print(f"       Class distribution: All-Star={sum(df['target']==3)}, Regular={sum(df['target']==2)}, Part-Time={sum(df['target']==1)}, Bench={sum(df['target']==0)}")

    return df


async def main():
    print("=" * 80)
    print("ML TRAINING DATA CREATION - TEMPORAL VALIDATION")
    print("=" * 80)

    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    # Define temporal splits
    splits = {
        'train': [2022, 2023],
        'val': [2024],
        'test': [2025]
    }

    # Extract data for each split
    for split_name, years in splits.items():
        print(f"\n{'='*80}")
        print(f"CREATING {split_name.upper()} DATASET")
        print(f"Years: {years}")
        print("=" * 80)

        all_hitters = []
        all_pitchers = []

        for year in years:
            hitters_df = await get_hitter_features(conn, year, split_name)
            pitchers_df = await get_pitcher_features(conn, year, split_name)

            all_hitters.append(hitters_df)
            all_pitchers.append(pitchers_df)

        # Combine years for this split
        hitters_combined = pd.concat(all_hitters, ignore_index=True)
        pitchers_combined = pd.concat(all_pitchers, ignore_index=True)

        # Save to CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        hitters_file = f"ml_data_hitters_{split_name}_{timestamp}.csv"
        pitchers_file = f"ml_data_pitchers_{split_name}_{timestamp}.csv"

        hitters_combined.to_csv(hitters_file, index=False)
        pitchers_combined.to_csv(pitchers_file, index=False)

        print(f"\n[OK] Saved {split_name} data:")
        print(f"     Hitters: {hitters_file} ({len(hitters_combined):,} rows, {len(hitters_combined.columns)} features)")
        print(f"     Pitchers: {pitchers_file} ({len(pitchers_combined):,} rows, {len(pitchers_combined.columns)} features)")

    print("\n" + "=" * 80)
    print("DATA QUALITY SUMMARY")
    print("=" * 80)

    # Check for missing data
    print("\nMissing Data Analysis (Train Set):")
    train_hitters = pd.read_csv([f for f in ['ml_data_hitters_train_*.csv'] if f.startswith('ml_data_hitters_train')][-1])

    missing_pct = (train_hitters.isnull().sum() / len(train_hitters) * 100).sort_values(ascending=False)
    print("\nTop 10 features with missing values (Hitters):")
    for feat, pct in missing_pct.head(10).items():
        if pct > 0:
            print(f"  {feat:<30} {pct:>6.1f}% missing")

    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("""
1. Feature Engineering:
   - Handle missing values (imputation or drop)
   - Encode categorical variables (position)
   - Normalize/standardize numeric features
   - Create interaction features (e.g., power × speed)

2. Class Imbalance:
   - Apply SMOTE to training set only
   - Use class_weight='balanced' in XGBoost
   - Consider hierarchical classification

3. Model Training:
   - Start with Random Forest baseline
   - Train XGBoost with hyperparameter tuning
   - Try LightGBM for comparison
   - Ensemble best models

4. Evaluation:
   - Weighted F1-score (primary metric)
   - Per-class precision/recall
   - Confusion matrix analysis
   - SHAP feature importance

See MLB_EXPECTATION_CLASSIFICATION_GUIDE.md for complete implementation details.
    """)

    await conn.close()
    print("\n[OK] Database connection closed")
    print("\n[OK] ML TRAINING DATA READY FOR MODEL TRAINING!")


if __name__ == "__main__":
    asyncio.run(main())
