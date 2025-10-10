"""
Generate prospect rankings V6 - BALANCED APPROACH

IMPROVEMENTS:
1. Recency weighting: 2025 > 2024 > 2023 > older
2. Focused Statcast: Only impute Barrel% (most predictive power metric)
3. Blended scoring: 70% V4 (performance) + 30% V5 (projection)
4. Conservative youth bias (less extreme than V5)

PHILOSOPHY:
- V4 too conservative (ignores development curve)
- V5 too aggressive (overvalues youth)
- V6 balances proven performance with upside potential
"""
import asyncio
import pandas as pd
import numpy as np
import pickle
from sqlalchemy import text
from datetime import datetime
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from scripts.prospect_age_curves import ProspectAgeCurve

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BarrelImputer:
    """Impute only Barrel% (most important Statcast metric)."""

    def __init__(self):
        self.model = None

    def train(self, df: pd.DataFrame):
        """Train Barrel% predictor."""
        from sklearn.ensemble import RandomForestRegressor

        # Features most correlated with barrel%
        features = ['iso', 'hr_rate', 'slg', 'xbh_rate', 'total_pa']

        # Only train on players WITH barrel data
        train_df = df[df['barrel_pct'].notna() & (df['barrel_pct'] > 0)].copy()

        if len(train_df) < 50:
            logger.warning(f'Only {len(train_df)} players with Barrel data - using simple average')
            self.model = None
            return

        X = train_df[features]
        y = train_df['barrel_pct']

        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=5,
            random_state=42
        )
        self.model.fit(X, y)

        logger.info(f'Trained Barrel% model on {len(train_df)} players')

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict Barrel% for players without it."""
        df = df.copy()

        # xbh_rate already calculated in main
        features = ['iso', 'hr_rate', 'slg', 'xbh_rate', 'total_pa']

        # Only impute for players missing barrel%
        missing_mask = df['barrel_pct'].isna() | (df['barrel_pct'] == 0)

        if missing_mask.sum() > 0 and self.model is not None:
            X = df.loc[missing_mask, features]
            df.loc[missing_mask, 'barrel_pct'] = self.model.predict(X)
            df.loc[missing_mask, 'barrel_source'] = 'imputed'
            logger.info(f'Imputed Barrel% for {missing_mask.sum()} players')
        else:
            df['barrel_source'] = 'actual'
            df.loc[missing_mask, 'barrel_source'] = 'missing'

        # Clip to realistic range
        df['barrel_pct'] = df['barrel_pct'].clip(0, 25)

        return df


async def load_hitters_with_recency() -> pd.DataFrame:
    """Load hitter data with recency weighting."""

    async with engine.connect() as conn:
        result = await conn.execute(text('''
            SELECT
                m.mlb_player_id,
                p.name as full_name,
                p.birth_date,
                p.position as primary_position,
                p.current_team,
                m.season,
                m.level,
                SUM(m.plate_appearances) as pa,
                SUM(m.at_bats) as ab,
                SUM(m.hits) as h,
                SUM(m.doubles) as doubles,
                SUM(m.triples) as triples,
                SUM(m.home_runs) as hr,
                SUM(m.walks) as bb,
                SUM(m.strikeouts) as so,
                SUM(m.stolen_bases) as sb
            FROM milb_game_logs m
            INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
            WHERE m.plate_appearances > 0
            AND (COALESCE(m.games_pitched, 0) = 0)
            AND p.birth_date IS NOT NULL
            GROUP BY m.mlb_player_id, p.name, p.birth_date, p.position, p.current_team, m.season, m.level
        '''))
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'full_name', 'birth_date', 'primary_position', 'current_team',
        'season', 'level', 'pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb'
    ])

    logger.info(f'Loaded {len(df)} player-season records')

    # Recency weights (exponential decay)
    recency_weights = {
        2025: 1.00,
        2024: 0.85,
        2023: 0.65,
        2022: 0.45,
        2021: 0.30,
    }

    df['recency_weight'] = df['season'].map(recency_weights).fillna(0.20)

    # Apply recency weighting to counting stats
    for col in ['pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb']:
        df[f'{col}_weighted'] = df[col] * df['recency_weight']

    # Aggregate by player (weighted)
    agg_dict = {
        'full_name': 'first',
        'birth_date': 'first',
        'primary_position': 'first',
        'current_team': 'first',
        'level': lambda x: x.mode()[0] if len(x.mode()) > 0 else x.iloc[0],  # Most common level
        'pa': 'sum',
        'ab': 'sum',
        'h': 'sum',
        'doubles': 'sum',
        'triples': 'sum',
        'hr': 'sum',
        'bb': 'sum',
        'so': 'sum',
        'sb': 'sum',
        'pa_weighted': 'sum',
        'ab_weighted': 'sum',
        'h_weighted': 'sum',
        'doubles_weighted': 'sum',
        'triples_weighted': 'sum',
        'hr_weighted': 'sum',
        'bb_weighted': 'sum',
        'so_weighted': 'sum',
        'sb_weighted': 'sum',
    }

    player_df = df.groupby('mlb_player_id').agg(agg_dict).reset_index()

    # Rename weighted as main stats (for recency-adjusted performance)
    for col in ['pa', 'ab', 'h', 'doubles', 'triples', 'hr', 'bb', 'so', 'sb']:
        player_df[f'total_{col}'] = player_df[f'{col}_weighted']
        player_df[f'raw_{col}'] = player_df[col]

    # Get highest level achieved (not weighted)
    level_order = {'AAA': 5, 'AA': 4, 'A+': 3, 'A': 2, 'Rookie': 1}
    level_df = df.groupby('mlb_player_id')['level'].apply(
        lambda x: max(x, key=lambda l: level_order.get(l, 0))
    ).reset_index()
    player_df['highest_level'] = level_df['level']

    logger.info(f'Aggregated to {len(player_df)} players (recency-weighted)')

    return player_df


async def main():
    print('=' * 100)
    print('PROSPECT RANKINGS V6 - BALANCED BLEND')
    print('=' * 100)

    # Load data with recency weighting
    logger.info('Loading hitter data with recency weighting...')
    df = await load_hitters_with_recency()

    # Filter to prospects (100+ PA)
    df = df[df['total_pa'] >= 100].copy()
    logger.info(f'Filtered to {len(df)} hitters with 100+ PA')

    # Calculate basic stats
    logger.info('Calculating stats...')
    df['avg'] = df['total_h'] / df['total_ab'].replace(0, np.nan)
    df['obp'] = (df['total_h'] + df['total_bb']) / df['total_pa'].replace(0, np.nan)
    df['tb'] = (df['total_h'] + df['total_doubles'] + df['total_triples']*2 + df['total_hr']*3)
    df['slg'] = df['tb'] / df['total_ab'].replace(0, np.nan)
    df['ops'] = df['obp'] + df['slg']
    df['iso'] = df['slg'] - df['avg']
    df['bb_rate'] = df['total_bb'] / df['total_pa']
    df['so_rate'] = df['total_so'] / df['total_pa']
    df['hr_rate'] = df['total_hr'] / df['total_pa']
    df['xbh_rate'] = (df['total_doubles'] + df['total_triples'] + df['total_hr']) / df['total_ab'].replace(0, np.nan)
    df = df.fillna(0)

    # Get Statcast data
    logger.info('Loading Statcast data...')
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            SELECT mlb_player_id, barrel_pct
            FROM milb_statcast_metrics_imputed
        '''))
        statcast_rows = result.fetchall()

    statcast_df = pd.DataFrame(statcast_rows, columns=['mlb_player_id', 'barrel_pct'])
    df = df.merge(statcast_df, on='mlb_player_id', how='left')

    # Impute Barrel% (focused Statcast)
    logger.info('Imputing Barrel% for players without Statcast...')
    barrel_imputer = BarrelImputer()
    barrel_imputer.train(df)
    df = barrel_imputer.predict(df)

    # Age calculation
    df['current_age'] = (datetime.now() - pd.to_datetime(df['birth_date'])).dt.days / 365.25

    # V4 SCORE - Performance-based (70% weight)
    logger.info('Calculating V4 performance score...')

    level_factors = {
        'AAA': 0.90, 'AA': 0.80, 'A+': 0.70, 'A': 0.60, 'Rookie': 0.50
    }
    df['level_factor'] = df['highest_level'].map(level_factors).fillna(0.60)

    # Apply age curve (less aggressive than V5)
    age_curve = ProspectAgeCurve(
        optimal_age=21.5,
        age_sensitivity=2.8,  # Less steep than V5 (was 2.5)
        hard_cutoff_age=27.0,  # More lenient (was 26.5)
        young_bonus_multiplier=1.15  # Less bonus (was 1.2)
    )
    df['age_factor'] = df['current_age'].apply(age_curve.calculate_age_factor)

    # Predicted MLB performance
    df['pred_mlb_ops'] = df['ops'] * df['level_factor']
    df['pred_mlb_wrc_plus'] = ((df['pred_mlb_ops'] - 0.650) / 0.004) + 80
    df['pred_mlb_wrc_plus'] = df['pred_mlb_wrc_plus'].clip(60, 130)

    # Barrel boost (elite power = elite MLB outcome)
    df['barrel_boost'] = 1.0
    df.loc[df['barrel_pct'] >= 12, 'barrel_boost'] = 1.12
    df.loc[df['barrel_pct'] >= 10, 'barrel_boost'] = 1.08
    df.loc[df['barrel_pct'] >= 8, 'barrel_boost'] = 1.04

    df['v4_score'] = df['pred_mlb_wrc_plus'] * df['age_factor'] * df['barrel_boost']

    # V5 SCORE - ML Projection-based (30% weight)
    logger.info('Loading V5 projections...')

    # Load ML predictor
    with open('age_aware_mlb_predictor.pkl', 'rb') as f:
        model_data = pickle.load(f)
        models = model_data['models']
        feature_cols = model_data['feature_cols']
        level_encoding = model_data['level_encoding']

    # Prepare features
    df['level_quality'] = df['highest_level'].map(level_encoding).fillna(0.50)
    df['is_young'] = (df['current_age'] <= 22).astype(int)
    df['is_elite_age'] = (df['current_age'] <= 21).astype(int)
    df['age_squared'] = df['current_age'] ** 2
    df['age_gap'] = 1
    df['ops_x_level'] = df['ops'] * df['level_quality']
    df['iso_x_level'] = df['iso'] * df['level_quality']
    df['bb_rate_x_level'] = df['bb_rate'] * df['level_quality']

    # Rename for model
    df = df.rename(columns={
        'total_pa': 'milb_pa',
        'ops': 'milb_ops',
        'iso': 'milb_iso',
        'bb_rate': 'milb_bb_rate',
        'so_rate': 'milb_k_rate',
        'avg': 'milb_avg',
        'current_age': 'milb_age'
    })

    # Predict MLB wRC+
    X = df[feature_cols]
    rf = models['mlb_wrc_plus']['rf']
    gb = models['mlb_wrc_plus']['gb']
    df['projected_mlb_wrc_plus'] = (rf.predict(X) + gb.predict(X)) / 2
    df['projected_mlb_wrc_plus'] = df['projected_mlb_wrc_plus'].clip(60, 130)

    # V5 uses more aggressive age factor
    v5_age_curve = ProspectAgeCurve()  # Original aggressive curve
    df['v5_age_factor'] = df['milb_age'].apply(v5_age_curve.calculate_age_factor)

    df['v5_score'] = df['projected_mlb_wrc_plus'] * df['v5_age_factor']

    # BLENDED V6 SCORE - 70% V4 + 30% V5
    logger.info('Creating V6 blended score (70% V4 + 30% V5)...')

    # Normalize scores to same scale
    v4_max = df['v4_score'].max()
    v5_max = df['v5_score'].max()

    df['v4_normalized'] = (df['v4_score'] / v4_max) * 100
    df['v5_normalized'] = (df['v5_score'] / v5_max) * 100

    df['v6_score'] = (0.70 * df['v4_normalized']) + (0.30 * df['v5_normalized'])

    # Filter by age and MLB experience
    df = df[df['age_factor'] > 0].copy()
    logger.info(f'After age filter: {len(df)} hitters')

    # Get MLB experience
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            SELECT mlb_player_id, SUM(plate_appearances) as mlb_pa
            FROM mlb_game_logs
            GROUP BY mlb_player_id
        '''))
        mlb_rows = result.fetchall()

    mlb_df = pd.DataFrame(mlb_rows, columns=['mlb_player_id', 'mlb_pa'])
    df = df.merge(mlb_df, on='mlb_player_id', how='left')
    df['mlb_pa'] = df['mlb_pa'].fillna(0)

    df = df[df['mlb_pa'] < 500].copy()
    logger.info(f'After MLB experience filter: {len(df)} hitters')

    # Rank and save
    df = df.sort_values('v6_score', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)

    output_file = 'prospect_rankings_v6_blended.csv'
    df.to_csv(output_file, index=False)

    # Display
    print('\n' + '=' * 100)
    print('TOP 50 HITTERS - V6 BLENDED RANKINGS (70% V4 Performance + 30% V5 Projection)')
    print('=' * 100)

    display = df[[
        'rank', 'full_name', 'milb_age', 'primary_position', 'highest_level',
        'milb_pa', 'milb_ops', 'barrel_pct', 'barrel_source',
        'v4_normalized', 'v5_normalized', 'v6_score'
    ]].head(50)

    print(display.to_string(index=False))

    print('\n' + '=' * 100)
    print(f'SUMMARY')
    print('=' * 100)
    print(f'Total prospects: {len(df)}')
    print(f'Players with actual Barrel%: {(df["barrel_source"] == "actual").sum()}')
    print(f'Players with imputed Barrel%: {(df["barrel_source"] == "imputed").sum()}')
    print(f'Avg age (Top 50): {df.head(50)["milb_age"].mean():.1f} years')
    print(f'Avg age (All): {df["milb_age"].mean():.1f} years')
    print(f'\nSaved to {output_file}')


if __name__ == '__main__':
    asyncio.run(main())
