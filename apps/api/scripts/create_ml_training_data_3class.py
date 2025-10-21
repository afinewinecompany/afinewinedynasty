"""
Create ML Training Data - 3-Class System
=========================================

Generate ML training datasets using the 3-class labeling system:
- Class 0: Bench/Reserve (FV 35-40)
- Class 1: Part-Time (FV 45)
- Class 2: MLB Regular+ (FV 50+)

This replaces the 4-class system which had 0 All-Star training examples.

Temporal Validation:
- Train: 2022-2023 (44 MLB Regular+, 141 Part-Time, 487 Bench)
- Validation: 2024
- Test: 2025 (true holdout)
"""

import asyncio
import asyncpg
import pandas as pd
import numpy as np
from datetime import datetime

DATABASE_URL = "postgresql://postgres:BVQjtsVwITqJKqdwOhgRLQwaWdeTXKgp@nozomi.proxy.rlwy.net:39235/railway"


async def get_hitter_features(conn, data_year: int, split_name: str):
    """
    Extract features for hitter prospects using 3-class labels.
    """
    print(f"\nExtracting hitter features for {split_name} ({data_year})...")

    query = """
        WITH prospect_grades AS (
            SELECT
                p.id as prospect_id,
                p.name,
                p.position,
                fg.fangraphs_player_id as fangraphs_id,

                -- Fangraphs scouting grades (future projections)
                fg.hit_future,
                fg.game_power_future,
                fg.raw_power_future,
                fg.speed_future,
                fg.fielding_future,

                -- Physical attributes
                phys.frame_future as frame_grade,
                phys.athleticism_future as athleticism_grade,

                -- Arm grade (from prospects table)
                p.arm_grade,

                -- MiLB performance stats (from PREVIOUS season)
                COALESCE(AVG(gl.batting_avg), 0) as batting_avg,
                COALESCE(AVG(gl.obp), 0) as obp,
                COALESCE(AVG(gl.slg), 0) as slg,
                COALESCE(AVG(gl.ops), 0) as avg_ops,
                COALESCE(AVG(gl.bb_rate), 0) as bb_rate,
                COALESCE(AVG(gl.k_rate), 0) as k_rate,
                COALESCE(AVG(gl.isolated_power), 0) as isolated_power,
                COALESCE(SUM(gl.hr), 0) as total_hr,
                COALESCE(SUM(gl.sb), 0) as total_sb,
                COALESCE(SUM(gl.pa), 0) as total_pa,
                COALESCE(AVG(gl.age), 0) as avg_age,
                COALESCE(MAX(gl.level), 0) as highest_level,

                -- 3-class label
                lbl.target,
                lbl.target_label,
                lbl.fangraphs_fv

            FROM prospects p
            JOIN fangraphs_hitter_grades fg ON p.fg_player_id = fg.fangraphs_player_id
            JOIN mlb_expectation_labels_3class lbl ON p.id = lbl.prospect_id AND lbl.data_year = $1
            LEFT JOIN fangraphs_physical_attributes phys
                ON fg.fangraphs_player_id = phys.fangraphs_player_id
                AND phys.data_year = $1
            LEFT JOIN milb_game_logs gl
                ON p.mlb_player_id = gl.player_id
                AND gl.season = $1 - 1
            WHERE fg.data_year = $1
            GROUP BY
                p.id, p.name, p.position, fg.fangraphs_player_id,
                fg.hit_future, fg.game_power_future, fg.raw_power_future,
                fg.speed_future, fg.fielding_future,
                phys.frame_future, phys.athleticism_future,
                p.arm_grade, lbl.target, lbl.target_label, lbl.fangraphs_fv
        )
        SELECT * FROM prospect_grades
        ORDER BY prospect_id
    """

    rows = await conn.fetch(query, data_year)

    if not rows:
        print(f"  [WARNING] No hitters found for {data_year}")
        return pd.DataFrame()

    df = pd.DataFrame([dict(row) for row in rows])

    # Show class distribution
    class_dist = df['target'].value_counts().sort_index()
    class_labels = {0: 'Bench', 1: 'Part-Time', 2: 'MLB Regular+'}
    print(f"  [OK] Extracted {len(df)} hitter prospects")
    print(f"       Class distribution: ", end="")
    print(", ".join([f"{class_labels[cls]}={count}" for cls, count in class_dist.items()]))

    return df


async def get_pitcher_features(conn, data_year: int, split_name: str):
    """
    Extract features for pitcher prospects using 3-class labels.
    """
    print(f"\nExtracting pitcher features for {split_name} ({data_year})...")

    query = """
        WITH prospect_grades AS (
            SELECT
                p.id as prospect_id,
                p.name,
                p.position,
                fg.fangraphs_player_id as fangraphs_id,

                -- Fangraphs scouting grades (future projections)
                fg.fastball_future,
                fg.curveball_future,
                fg.slider_future,
                fg.changeup_future,
                fg.other_future,
                fg.command_future,

                -- Physical attributes
                phys.frame_future as frame_grade,
                phys.athleticism_future as athleticism_grade,

                -- MiLB performance stats (from PREVIOUS season)
                COALESCE(AVG(app.era), 0) as avg_era,
                COALESCE(AVG(app.whip), 0) as avg_whip,
                COALESCE(AVG(app.k_rate), 0) as k_rate,
                COALESCE(AVG(app.bb_rate), 0) as bb_rate,
                COALESCE(SUM(app.innings_pitched), 0) as total_ip,
                COALESCE(AVG(app.age), 0) as avg_age,
                COALESCE(MAX(app.level), 0) as highest_level,

                -- 3-class label
                lbl.target,
                lbl.target_label,
                lbl.fangraphs_fv

            FROM prospects p
            JOIN fangraphs_pitcher_grades fg ON p.fg_player_id = fg.fangraphs_player_id
            JOIN mlb_expectation_labels_3class lbl ON p.id = lbl.prospect_id AND lbl.data_year = $1
            LEFT JOIN fangraphs_physical_attributes phys
                ON fg.fangraphs_player_id = phys.fangraphs_player_id
                AND phys.data_year = $1
            LEFT JOIN pitcher_appearances app
                ON p.mlb_player_id = app.player_id
                AND app.season = $1 - 1
            WHERE fg.data_year = $1
            GROUP BY
                p.id, p.name, p.position, fg.fangraphs_player_id,
                fg.fastball_future, fg.curveball_future, fg.slider_future,
                fg.changeup_future, fg.other_future, fg.command_future,
                phys.frame_future, phys.athleticism_future,
                lbl.target, lbl.target_label, lbl.fangraphs_fv
        )
        SELECT * FROM prospect_grades
        ORDER BY prospect_id
    """

    rows = await conn.fetch(query, data_year)

    if not rows:
        print(f"  [WARNING] No pitchers found for {data_year}")
        return pd.DataFrame()

    df = pd.DataFrame([dict(row) for row in rows])

    # Show class distribution
    class_dist = df['target'].value_counts().sort_index()
    class_labels = {0: 'Bench', 1: 'Part-Time', 2: 'MLB Regular+'}
    print(f"  [OK] Extracted {len(df)} pitcher prospects")
    print(f"       Class distribution: ", end="")
    print(", ".join([f"{class_labels[cls]}={count}" for cls, count in class_dist.items()]))

    return df


async def main():
    print("="*80)
    print("ML TRAINING DATA CREATION - 3-CLASS SYSTEM")
    print("="*80)

    print("\nClass System:")
    print("  Class 0: Bench/Reserve (FV 35-40)")
    print("  Class 1: Part-Time (FV 45)")
    print("  Class 2: MLB Regular+ (FV 50+)")

    print("\nTemporal Validation Strategy:")
    print("  Train: 2022-2023")
    print("  Validation: 2024")
    print("  Test: 2025 (true holdout)")

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)
    print("\n[OK] Connected to database")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        # ========== TRAIN SPLIT (2022-2023) ==========
        print("\n" + "="*80)
        print("CREATING TRAIN DATASET")
        print("Years: [2022, 2023]")
        print("="*80)

        train_dfs_hitters = []
        train_dfs_pitchers = []

        for year in [2022, 2023]:
            df_h = await get_hitter_features(conn, year, "train")
            df_p = await get_pitcher_features(conn, year, "train")
            if not df_h.empty:
                train_dfs_hitters.append(df_h)
            if not df_p.empty:
                train_dfs_pitchers.append(df_p)

        train_hitters = pd.concat(train_dfs_hitters, ignore_index=True) if train_dfs_hitters else pd.DataFrame()
        train_pitchers = pd.concat(train_dfs_pitchers, ignore_index=True) if train_dfs_pitchers else pd.DataFrame()

        train_hitters_file = f'ml_data_hitters_3class_train_{timestamp}.csv'
        train_pitchers_file = f'ml_data_pitchers_3class_train_{timestamp}.csv'

        if not train_hitters.empty:
            train_hitters.to_csv(train_hitters_file, index=False)
            print(f"\n[OK] Saved train data:")
            print(f"     Hitters: {train_hitters_file} ({len(train_hitters)} rows, {len(train_hitters.columns)} features)")

        if not train_pitchers.empty:
            train_pitchers.to_csv(train_pitchers_file, index=False)
            print(f"     Pitchers: {train_pitchers_file} ({len(train_pitchers)} rows, {len(train_pitchers.columns)} features)")

        # ========== VALIDATION SPLIT (2024) ==========
        print("\n" + "="*80)
        print("CREATING VAL DATASET")
        print("Years: [2024]")
        print("="*80)

        val_hitters = await get_hitter_features(conn, 2024, "val")
        val_pitchers = await get_pitcher_features(conn, 2024, "val")

        val_hitters_file = f'ml_data_hitters_3class_val_{timestamp}.csv'
        val_pitchers_file = f'ml_data_pitchers_3class_val_{timestamp}.csv'

        if not val_hitters.empty:
            val_hitters.to_csv(val_hitters_file, index=False)
            print(f"\n[OK] Saved val data:")
            print(f"     Hitters: {val_hitters_file} ({len(val_hitters)} rows, {len(val_hitters.columns)} features)")

        if not val_pitchers.empty:
            val_pitchers.to_csv(val_pitchers_file, index=False)
            print(f"     Pitchers: {val_pitchers_file} ({len(val_pitchers)} rows, {len(val_pitchers.columns)} features)")

        # ========== TEST SPLIT (2025) ==========
        print("\n" + "="*80)
        print("CREATING TEST DATASET")
        print("Years: [2025]")
        print("="*80)

        test_hitters = await get_hitter_features(conn, 2025, "test")
        test_pitchers = await get_pitcher_features(conn, 2025, "test")

        test_hitters_file = f'ml_data_hitters_3class_test_{timestamp}.csv'
        test_pitchers_file = f'ml_data_pitchers_3class_test_{timestamp}.csv'

        if not test_hitters.empty:
            test_hitters.to_csv(test_hitters_file, index=False)
            print(f"\n[OK] Saved test data:")
            print(f"     Hitters: {test_hitters_file} ({len(test_hitters)} rows, {len(test_hitters.columns)} features)")

        if not test_pitchers.empty:
            test_pitchers.to_csv(test_pitchers_file, index=False)
            print(f"     Pitchers: {test_pitchers_file} ({len(test_pitchers)} rows, {len(test_pitchers.columns)} features)")

        # ========== SUMMARY ==========
        print("\n" + "="*80)
        print("3-CLASS ML DATASETS CREATED")
        print("="*80)

        print(f"\n{'Split':<12} {'Hitters':<10} {'Pitchers':<10}")
        print("-" * 35)
        print(f"{'Train':<12} {len(train_hitters):>9} {len(train_pitchers):>9}")
        print(f"{'Validation':<12} {len(val_hitters):>9} {len(val_pitchers):>9}")
        print(f"{'Test':<12} {len(test_hitters):>9} {len(test_pitchers):>9}")

        print("\nKey Improvement:")
        print("  4-class had 0 All-Star training examples")
        print(f"  3-class has {(train_hitters['target']==2).sum()} MLB Regular+ hitter training examples")
        print(f"  3-class has {(train_pitchers['target']==2).sum()} MLB Regular+ pitcher training examples")

        print("\nNext Steps:")
        print("  1. Train 3-class Random Forest baseline")
        print("  2. Expected: 0.72-0.75 F1 (vs 0.697 F1 position-specific baseline)")
        print("  3. Then implement XGBoost for 0.74-0.78 F1")

    finally:
        await conn.close()
        print("\n[OK] Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
