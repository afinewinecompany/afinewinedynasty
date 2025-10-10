"""
Train ML model to predict MiLB performance from FanGraphs prospect grades.

Simpler approach: FanGraphs grades → MiLB stats (instead of MLB outcomes)
This gives us more training data since most prospects are still in MiLB.
"""
import pandas as pd
import numpy as np
import asyncio
from sqlalchemy import text
import sys
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import joblib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine


async def load_hitter_training_data():
    """Load FanGraphs hitter grades + MiLB performance."""
    async with engine.begin() as conn:
        query = text('''
            WITH fg_grades AS (
                SELECT
                    fg.fg_player_id,
                    fg.player_name,
                    fg.report_year,
                    fg.age,
                    fg.fv,
                    fg.hit_future,
                    fg.game_pwr_future,
                    fg.raw_pwr_future,
                    fg.spd_future,
                    fg.fld_future,
                    fg.pitch_sel,
                    fg.bat_ctrl,
                    fg.frame,
                    fg.athleticism,
                    fg.arm,
                    fg.performance,
                    fg.hard_hit_pct,
                    fg.top_100_rank
                FROM fangraphs_prospect_grades fg
                WHERE fg.report_year BETWEEN 2022 AND 2024
                  AND fg.hit_future IS NOT NULL
            ),
            milb_stats AS (
                SELECT
                    p.fg_player_id,
                    gl.season,
                    SUM(gl.plate_appearances) as total_pa,
                    SUM(gl.hits)::float / NULLIF(SUM(gl.at_bats), 0) as avg,
                    SUM(gl.walks)::float / NULLIF(SUM(gl.plate_appearances), 0) as bb_rate,
                    SUM(gl.strikeouts)::float / NULLIF(SUM(gl.plate_appearances), 0) as k_rate,
                    (SUM(gl.hits) + SUM(gl.walks))::float / NULLIF(SUM(gl.plate_appearances), 0) as obp,
                    (SUM(gl.hits) - SUM(gl.doubles) - SUM(gl.triples) - SUM(gl.home_runs) +
                     2*SUM(gl.doubles) + 3*SUM(gl.triples) + 4*SUM(gl.home_runs))::float / NULLIF(SUM(gl.at_bats), 0) as slg,
                    (SUM(gl.doubles) + SUM(gl.triples) + SUM(gl.home_runs))::float / NULLIF(SUM(gl.at_bats), 0) as iso,
                    SUM(gl.home_runs)::float / NULLIF(SUM(gl.plate_appearances), 0) as hr_rate,
                    MAX(gl.level) as highest_level
                FROM prospects p
                INNER JOIN milb_game_logs gl ON gl.mlb_player_id::varchar = p.mlb_player_id
                WHERE p.fg_player_id IS NOT NULL
                  AND gl.season BETWEEN 2022 AND 2025
                  AND gl.plate_appearances > 0
                GROUP BY p.fg_player_id, gl.season
                HAVING SUM(gl.plate_appearances) >= 100
            )
            SELECT
                fg.*,
                ms.season as perf_season,
                ms.total_pa,
                ms.avg,
                ms.obp,
                ms.slg,
                ms.obp + ms.slg as ops,
                ms.iso,
                ms.bb_rate,
                ms.k_rate,
                ms.hr_rate,
                ms.highest_level
            FROM fg_grades fg
            INNER JOIN milb_stats ms ON ms.fg_player_id = fg.fg_player_id
            WHERE ms.season >= fg.report_year
            ORDER BY fg.fv DESC NULLS LAST
        ''')

        result = await conn.execute(query)
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
        return df


def build_hitter_features(df):
    """Build feature matrix from FanGraphs grades."""
    features = []
    feature_names = []

    # Tool grades (future)
    for col in ['hit_future', 'game_pwr_future', 'raw_pwr_future', 'spd_future', 'fld_future']:
        features.append(df[col].fillna(40))
        feature_names.append(col)

    # Plate discipline
    for col in ['pitch_sel', 'bat_ctrl']:
        features.append(df[col].fillna(40))
        feature_names.append(col)

    # Physical
    for col in ['frame', 'athleticism', 'arm', 'performance']:
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

    features.append((101 - df['top_100_rank'].fillna(101)))
    feature_names.append('top_100_inverse')

    X = np.column_stack(features)
    return X, feature_names


def train_ops_model(df):
    """Train model to predict MiLB OPS from FanGraphs grades."""
    print('\n' + '=' * 80)
    print('TRAINING HITTER MODEL: FanGraphs Grades -> MiLB OPS')
    print('=' * 80)

    X, feature_names = build_hitter_features(df)
    y = df['ops'].values

    print(f'Training samples: {len(df)} (prospect-season pairs)')
    print(f'Unique prospects: {df["fg_player_id"].nunique()}')
    print(f'Features: {len(feature_names)}')
    print(f'Target: OPS (mean={y.mean():.3f}, std={y.std():.3f})')

    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=5, random_state=42)
    rf.fit(X_train, y_train)

    # Evaluate
    train_pred = rf.predict(X_train)
    test_pred = rf.predict(X_test)

    print(f'\nModel Performance:')
    print(f'  Training R²: {r2_score(y_train, train_pred):.3f}')
    print(f'  Test R²: {r2_score(y_test, test_pred):.3f}')
    print(f'  Test MAE: {mean_absolute_error(y_test, test_pred):.3f} OPS')
    print(f'  Test RMSE: {np.sqrt(mean_squared_error(y_test, test_pred)):.3f} OPS')

    # Feature importance
    print('\nTop 10 Most Predictive Grades:')
    importances = sorted(zip(feature_names, rf.feature_importances_), key=lambda x: x[1], reverse=True)
    for i, (name, importance) in enumerate(importances[:10], 1):
        print(f'  {i:2d}. {name:20s} {importance:.3f}')

    return rf, feature_names, importances


async def main():
    print('=' * 80)
    print('FANGRAPHS -> MiLB PERFORMANCE PREDICTOR')
    print('=' * 80)
    print('\nPredicting MiLB performance from FanGraphs scouting grades.')
    print('Training: 2022-2024 prospect grades -> 2022-2025 MiLB stats\n')

    # Load hitter data
    print('Loading hitter training data...')
    hitters_df = await load_hitter_training_data()

    print(f'\nLoaded {len(hitters_df)} hitter prospect-season pairs')
    print(f'  Unique prospects: {hitters_df["fg_player_id"].nunique()}')
    print(f'  Report years: {sorted(hitters_df["report_year"].unique())}')
    print(f'  Performance years: {sorted(hitters_df["perf_season"].unique())}')

    if len(hitters_df) == 0:
        print('\n⚠️  No training data found!')
        print('\nTroubleshooting:')
        print('  1. Check that prospects.fg_player_id is populated (run link_fangraphs_to_prospects.py)')
        print('  2. Check that milb_game_logs has data for 2022-2025')
        print('  3. Verify the fg_player_id type matches between tables')
        return

    # Show sample
    print('\n' + '=' * 80)
    print('SAMPLE TRAINING DATA (Top 10 by FV)')
    print('=' * 80)
    sample = hitters_df.sort_values('fv', ascending=False).head(10)
    print(f'{"Player":<25} {"Year":<6} {"FV":<4} {"Hit":<4} {"Pwr":<4} {"PA":<5} {"OPS":<6}')
    print('-' * 80)
    for _, row in sample.iterrows():
        fv = int(row['fv']) if pd.notna(row['fv']) else '-'
        hit = int(row['hit_future']) if pd.notna(row['hit_future']) else '-'
        pwr = int(row['game_pwr_future']) if pd.notna(row['game_pwr_future']) else '-'
        pa = int(row['total_pa'])
        ops = row['ops']
        print(f'{row["player_name"]:<25} {row["report_year"]:<6} {str(fv):<4} {str(hit):<4} {str(pwr):<4} {pa:<5} {ops:.3f}')

    # Train model
    model, features, importances = train_ops_model(hitters_df)

    # Save model
    joblib.dump({
        'model': model,
        'features': features,
        'feature_importances': importances,
        'training_samples': len(hitters_df),
        'unique_prospects': hitters_df['fg_player_id'].nunique()
    }, 'fangraphs_milb_hitter_predictor.pkl')

    print('\nSaved model to fangraphs_milb_hitter_predictor.pkl')

    # Key insights
    print('\n' + '=' * 80)
    print('KEY INSIGHTS')
    print('=' * 80)

    top_3 = importances[:3]
    print('\nMost Predictive Grades:')
    for i, (name, imp) in enumerate(top_3, 1):
        print(f'  {i}. {name} ({imp:.1%} of prediction)')

    # Correlation analysis
    print('\nGrade vs Performance Correlations:')
    for grade in ['hit_future', 'game_pwr_future', 'fv']:
        if grade in hitters_df.columns:
            corr = hitters_df[grade].corr(hitters_df['ops'])
            print(f'  {grade}: r={corr:.3f}')

    print('\n' + '=' * 80)
    print('TRAINING COMPLETE')
    print('=' * 80)
    print('\nNext steps:')
    print('  1. Analyze which grades matter most for different prospect types')
    print('  2. Create V7 rankings blending FG grades with V6 rankings')
    print('  3. Identify undervalued prospects (high grades, low V6 rank)')


if __name__ == '__main__':
    asyncio.run(main())
