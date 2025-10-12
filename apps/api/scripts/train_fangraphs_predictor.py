"""
Train ML model to predict MLB success based on FanGraphs prospect grades.

This model will:
1. Match FanGraphs prospects (2022-2024) to their MLB performance
2. Build features from scouting grades + physical attributes
3. Predict MLB outcomes (wRC+, ERA, WAR, etc.)
4. Identify which grades/attributes are most predictive
"""
import pandas as pd
import numpy as np
import asyncio
from sqlalchemy import text
import sys
import os
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine


async def load_training_data():
    """
    Load FanGraphs grades matched to MLB performance.

    Strategy:
    - For 2022 grades, look at 2023-2025 MLB performance
    - For 2023 grades, look at 2024-2025 MLB performance
    - For 2024 grades, look at 2025 MLB performance

    This gives us prospect grades → future MLB outcomes.
    """
    print('Loading training data...')

    async with engine.begin() as conn:
        # Get hitters: FanGraphs grades → MLB batting stats
        hitter_query = text('''
            WITH fg_grades AS (
                SELECT
                    fg.fg_player_id,
                    fg.player_name,
                    fg.report_year,
                    fg.age,
                    fg.fv,

                    -- Hitting tool grades (future)
                    fg.hit_future,
                    fg.game_pwr_future,
                    fg.raw_pwr_future,
                    fg.spd_future,
                    fg.fld_future,
                    fg.pitch_sel,
                    fg.bat_ctrl,

                    -- Physical attributes
                    fg.frame,
                    fg.athleticism,
                    fg.arm,
                    fg.performance,
                    fg.hard_hit_pct,

                    -- Meta
                    fg.top_100_rank
                FROM fangraphs_prospect_grades fg
                WHERE fg.report_year BETWEEN 2022 AND 2024
                  AND fg.hit_future IS NOT NULL  -- Only hitters
            ),
            mlb_stats AS (
                SELECT
                    p.fg_player_id,
                    p.name,

                    -- Aggregate MLB performance (weighted by PA)
                    SUM(bl.pa) as total_mlb_pa,
                    SUM(bl.pa * bl.wrc_plus) / NULLIF(SUM(bl.pa), 0) as avg_wrc_plus,
                    SUM(bl.pa * bl.ops) / NULLIF(SUM(bl.pa), 0) as avg_ops,
                    SUM(bl.pa * bl.iso) / NULLIF(SUM(bl.pa), 0) as avg_iso,
                    SUM(bl.pa * bl.bb_rate) / NULLIF(SUM(bl.pa), 0) as avg_bb_rate,
                    SUM(bl.pa * bl.k_rate) / NULLIF(SUM(bl.pa), 0) as avg_k_rate,
                    SUM(bl.war) as total_war,
                    AVG(bl.war) as avg_war_per_season,
                    MIN(bl.season) as first_mlb_season,
                    MAX(bl.season) as last_mlb_season

                FROM prospects p
                INNER JOIN batting_logs bl ON bl.mlb_player_id = p.mlb_player_id
                WHERE bl.season BETWEEN 2022 AND 2025
                  AND bl.level = 'MLB'
                  AND bl.pa >= 50  -- Minimum PA to count
                GROUP BY p.fg_player_id, p.name
                HAVING SUM(bl.pa) >= 150  -- Need meaningful MLB sample
            )
            SELECT
                fg.*,
                mlb.total_mlb_pa,
                mlb.avg_wrc_plus,
                mlb.avg_ops,
                mlb.avg_iso,
                mlb.avg_bb_rate,
                mlb.avg_k_rate,
                mlb.total_war,
                mlb.avg_war_per_season,
                mlb.first_mlb_season,
                mlb.last_mlb_season,

                -- Calculate years from prospect report to MLB
                mlb.first_mlb_season - fg.report_year as years_to_mlb

            FROM fg_grades fg
            INNER JOIN mlb_stats mlb ON mlb.fg_player_id = fg.fg_player_id
            WHERE mlb.first_mlb_season >= fg.report_year  -- Only future performance
        ''')

        result = await conn.execute(hitter_query)
        hitters_df = pd.DataFrame(result.fetchall(), columns=result.keys())

        print(f'Loaded {len(hitters_df)} hitters with FG grades + MLB performance')

        # Get pitchers: FanGraphs grades → MLB pitching stats
        pitcher_query = text('''
            WITH fg_grades AS (
                SELECT
                    fg.fg_player_id,
                    fg.player_name,
                    fg.report_year,
                    fg.age,
                    fg.fv,

                    -- Pitching grades (future)
                    fg.fb_future,
                    fg.sl_future,
                    fg.cb_future,
                    fg.ch_future,
                    fg.cmd_future,

                    -- Physical attributes
                    fg.frame,
                    fg.athleticism,
                    fg.arm,
                    fg.performance,
                    fg.delivery,

                    -- Meta
                    fg.top_100_rank,
                    fg.tj_date
                FROM fangraphs_prospect_grades fg
                WHERE fg.report_year BETWEEN 2022 AND 2024
                  AND fg.fb_future IS NOT NULL  -- Only pitchers
            ),
            mlb_stats AS (
                SELECT
                    p.fg_player_id,
                    p.name,

                    -- Aggregate MLB pitching (weighted by IP)
                    SUM(pl.ip) as total_mlb_ip,
                    SUM(pl.ip * pl.era) / NULLIF(SUM(pl.ip), 0) as avg_era,
                    SUM(pl.ip * pl.fip) / NULLIF(SUM(pl.ip), 0) as avg_fip,
                    SUM(pl.ip * pl.whip) / NULLIF(SUM(pl.ip), 0) as avg_whip,
                    SUM(pl.ip * pl.k_rate) / NULLIF(SUM(pl.ip), 0) as avg_k_rate,
                    SUM(pl.ip * pl.bb_rate) / NULLIF(SUM(pl.ip), 0) as avg_bb_rate,
                    SUM(pl.war) as total_war,
                    AVG(pl.war) as avg_war_per_season,
                    MIN(pl.season) as first_mlb_season,
                    MAX(pl.season) as last_mlb_season

                FROM prospects p
                INNER JOIN pitching_logs pl ON pl.mlb_player_id = p.mlb_player_id
                WHERE pl.season BETWEEN 2022 AND 2025
                  AND pl.level = 'MLB'
                  AND pl.ip >= 20  -- Minimum IP to count
                GROUP BY p.fg_player_id, p.name
                HAVING SUM(pl.ip) >= 50  -- Need meaningful MLB sample
            )
            SELECT
                fg.*,
                mlb.total_mlb_ip,
                mlb.avg_era,
                mlb.avg_fip,
                mlb.avg_whip,
                mlb.avg_k_rate,
                mlb.avg_bb_rate,
                mlb.total_war,
                mlb.avg_war_per_season,
                mlb.first_mlb_season,
                mlb.last_mlb_season,
                mlb.first_mlb_season - fg.report_year as years_to_mlb

            FROM fg_grades fg
            INNER JOIN mlb_stats mlb ON mlb.fg_player_id = fg.fg_player_id
            WHERE mlb.first_mlb_season >= fg.report_year
        ''')

        result = await conn.execute(pitcher_query)
        pitchers_df = pd.DataFrame(result.fetchall(), columns=result.keys())

        print(f'Loaded {len(pitchers_df)} pitchers with FG grades + MLB performance')

        return hitters_df, pitchers_df


def build_hitter_features(df):
    """Build feature matrix for hitters."""
    features = []
    feature_names = []

    # Tool grades (future)
    for col in ['hit_future', 'game_pwr_future', 'raw_pwr_future', 'spd_future', 'fld_future']:
        if col in df.columns:
            features.append(df[col].fillna(40))  # Fill missing with league average (40)
            feature_names.append(col)

    # Plate discipline
    for col in ['pitch_sel', 'bat_ctrl']:
        if col in df.columns:
            features.append(df[col].fillna(40))
            feature_names.append(col)

    # Physical attributes
    for col in ['frame', 'athleticism', 'arm', 'performance']:
        if col in df.columns:
            features.append(df[col].fillna(0))
            feature_names.append(col)

    # Statcast
    if 'hard_hit_pct' in df.columns:
        features.append(df['hard_hit_pct'].fillna(0.35))
        feature_names.append('hard_hit_pct')

    # Context
    features.append(df['age'].fillna(21))
    feature_names.append('age')

    features.append(df['fv'].fillna(40))
    feature_names.append('fv')

    # Top 100 rank (inverse - lower rank = better)
    features.append((101 - df['top_100_rank'].fillna(101)))
    feature_names.append('top_100_inverse')

    X = np.column_stack(features)
    return X, feature_names


def build_pitcher_features(df):
    """Build feature matrix for pitchers."""
    features = []
    feature_names = []

    # Pitch grades (future)
    for col in ['fb_future', 'sl_future', 'cb_future', 'ch_future', 'cmd_future']:
        if col in df.columns:
            features.append(df[col].fillna(40))
            feature_names.append(col)

    # Physical attributes
    for col in ['frame', 'athleticism', 'arm', 'performance', 'delivery']:
        if col in df.columns:
            features.append(df[col].fillna(0))
            feature_names.append(col)

    # Context
    features.append(df['age'].fillna(22))
    feature_names.append('age')

    features.append(df['fv'].fillna(40))
    feature_names.append('fv')

    features.append((101 - df['top_100_rank'].fillna(101)))
    feature_names.append('top_100_inverse')

    # TJ surgery indicator
    if 'tj_date' in df.columns:
        features.append(df['tj_date'].notna().astype(int))
        feature_names.append('has_tj_surgery')

    X = np.column_stack(features)
    return X, feature_names


def train_hitter_model(df):
    """Train model to predict MLB wRC+ from FanGraphs grades."""
    print('\n' + '=' * 80)
    print('TRAINING HITTER MODEL: FanGraphs Grades -> MLB wRC+')
    print('=' * 80)

    # Build features
    X, feature_names = build_hitter_features(df)
    y = df['avg_wrc_plus'].values

    print(f'Training samples: {len(df)}')
    print(f'Features: {len(feature_names)}')
    print(f'Target: wRC+ (mean={y.mean():.1f}, std={y.std():.1f})')

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train Random Forest
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=5, random_state=42)
    rf.fit(X_train, y_train)

    # Evaluate
    train_pred = rf.predict(X_train)
    test_pred = rf.predict(X_test)

    print(f'\nTraining R²: {r2_score(y_train, train_pred):.3f}')
    print(f'Test R²: {r2_score(y_test, test_pred):.3f}')
    print(f'Test MAE: {mean_absolute_error(y_test, test_pred):.1f} wRC+')
    print(f'Test RMSE: {np.sqrt(mean_squared_error(y_test, test_pred)):.1f} wRC+')

    # Feature importance
    print('\nTop 10 Most Predictive Features:')
    importances = sorted(zip(feature_names, rf.feature_importances_), key=lambda x: x[1], reverse=True)
    for i, (name, importance) in enumerate(importances[:10], 1):
        print(f'  {i:2d}. {name:20s} {importance:.3f}')

    return rf, feature_names


def train_pitcher_model(df):
    """Train model to predict MLB FIP from FanGraphs grades."""
    print('\n' + '=' * 80)
    print('TRAINING PITCHER MODEL: FanGraphs Grades -> MLB FIP')
    print('=' * 80)

    # Build features
    X, feature_names = build_pitcher_features(df)
    y = df['avg_fip'].values

    print(f'Training samples: {len(df)}')
    print(f'Features: {len(feature_names)}')
    print(f'Target: FIP (mean={y.mean():.2f}, std={y.std():.2f})')

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train Random Forest
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=5, random_state=42)
    rf.fit(X_train, y_train)

    # Evaluate
    train_pred = rf.predict(X_train)
    test_pred = rf.predict(X_test)

    print(f'\nTraining R²: {r2_score(y_train, train_pred):.3f}')
    print(f'Test R²: {r2_score(y_test, test_pred):.3f}')
    print(f'Test MAE: {mean_absolute_error(y_test, test_pred):.2f} FIP')
    print(f'Test RMSE: {np.sqrt(mean_squared_error(y_test, test_pred)):.2f} FIP')

    # Feature importance
    print('\nTop 10 Most Predictive Features:')
    importances = sorted(zip(feature_names, rf.feature_importances_), key=lambda x: x[1], reverse=True)
    for i, (name, importance) in enumerate(importances[:10], 1):
        print(f'  {i:2d}. {name:20s} {importance:.3f}')

    return rf, feature_names


async def main():
    print('=' * 80)
    print('FANGRAPHS GRADE ML PREDICTOR')
    print('=' * 80)
    print('\nThis model predicts MLB success from FanGraphs scouting grades.')
    print('Training data: 2022-2024 prospect grades -> 2022-2025 MLB performance\n')

    # Load data
    hitters_df, pitchers_df = await load_training_data()

    if len(hitters_df) == 0:
        print('\nWARNING: No hitter training data found!')
        print('Make sure:')
        print('  1. FanGraphs grades imported (run import_fangraphs_csvs.py)')
        print('  2. Prospects have fg_player_id populated')
        print('  3. MLB batting_logs exist for 2022-2025')
    else:
        # Train hitter model
        hitter_model, hitter_features = train_hitter_model(hitters_df)

        # Save model
        joblib.dump({
            'model': hitter_model,
            'features': hitter_features,
            'training_samples': len(hitters_df)
        }, 'fangraphs_hitter_predictor.pkl')
        print('\nSaved hitter model to fangraphs_hitter_predictor.pkl')

    if len(pitchers_df) == 0:
        print('\nWARNING: No pitcher training data found!')
    else:
        # Train pitcher model
        pitcher_model, pitcher_features = train_pitcher_model(pitchers_df)

        # Save model
        joblib.dump({
            'model': pitcher_model,
            'features': pitcher_features,
            'training_samples': len(pitchers_df)
        }, 'fangraphs_pitcher_predictor.pkl')
        print('\nSaved pitcher model to fangraphs_pitcher_predictor.pkl')

    print('\n' + '=' * 80)
    print('TRAINING COMPLETE')
    print('=' * 80)


if __name__ == '__main__':
    asyncio.run(main())
