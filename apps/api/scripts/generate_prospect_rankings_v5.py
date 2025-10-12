"""
Generate prospect rankings (v5) with ML-imputed MLB performance projections.

KEY FEATURES:
- Uses actual MiLB->MLB transitions to predict future MLB performance
- Age-aware predictions (accounts for development curve)
- Compares prospects who did X at age Y in AA to actual MLB outcomes
- Flags prospects missing from FanGraphs consensus rankings
- Fair Statcast (ML-imputed for all players)
"""
import asyncio
import pandas as pd
import numpy as np
import pickle
from sqlalchemy import text
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.database import engine
from scripts.prospect_age_curves import ProspectAgeCurve

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MLBProjectionEngine:
    """Predicts MLB performance using age-aware model trained on real transitions."""

    def __init__(self):
        self.load_models()

    def load_models(self):
        """Load trained MLB predictor models."""
        with open('age_aware_mlb_predictor.pkl', 'rb') as f:
            data = pickle.load(f)
            self.models = data['models']
            self.feature_cols = data['feature_cols']
            self.level_encoding = data['level_encoding']

    def predict_mlb_performance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict MLB stats for prospects with no MLB experience."""
        df = df.copy()

        # Calculate current age
        df['current_age'] = (datetime.now() - pd.to_datetime(df['birth_date'])).dt.days / 365.25

        # Feature engineering (match training data)
        df['level_quality'] = df['highest_level'].map(self.level_encoding).fillna(0.50)
        df['is_young'] = (df['current_age'] <= 22).astype(int)
        df['is_elite_age'] = (df['current_age'] <= 21).astype(int)
        df['age_squared'] = df['current_age'] ** 2
        df['age_gap'] = 1  # Assume 1 year to MLB debut

        # Performance * Level interactions
        df['ops_x_level'] = df['ops'] * df['level_quality']
        df['iso_x_level'] = df['iso'] * df['level_quality']
        df['bb_rate_x_level'] = df['bb_rate'] * df['level_quality']

        # Rename to match training features
        df = df.rename(columns={
            'total_pa': 'milb_pa',
            'ops': 'milb_ops',
            'iso': 'milb_iso',
            'bb_rate': 'milb_bb_rate',
            'so_rate': 'milb_k_rate',
            'avg': 'milb_avg',
            'current_age': 'milb_age'
        })

        # Predict each target
        X = df[self.feature_cols]

        for target in ['mlb_wrc_plus', 'mlb_ops', 'mlb_iso', 'mlb_obp', 'mlb_slg']:
            rf = self.models[target]['rf']
            gb = self.models[target]['gb']

            # Ensemble prediction
            pred_rf = rf.predict(X)
            pred_gb = gb.predict(X)
            df[f'projected_{target}'] = (pred_rf + pred_gb) / 2

        # Clip to realistic ranges
        df['projected_mlb_wrc_plus'] = df['projected_mlb_wrc_plus'].clip(50, 140)
        df['projected_mlb_ops'] = df['projected_mlb_ops'].clip(0.500, 1.000)

        return df


async def main():
    print('=' * 100)
    print('PROSPECT RANKINGS V5 - MLB PROJECTION ENGINE')
    print('=' * 100)

    # Initialize projection engine
    logger.info('Loading MLB projection models...')
    projector = MLBProjectionEngine()

    # Load hitter data
    logger.info('Loading hitter data...')
    async with engine.connect() as conn:
        result = await conn.execute(text('''
            WITH hitter_stats AS (
                SELECT
                    m.mlb_player_id,
                    p.name as full_name,
                    p.birth_date,
                    p.position as primary_position,
                    p.current_team,
                    MAX(m.level) as highest_level,
                    SUM(m.plate_appearances) as total_pa,
                    SUM(m.at_bats) as total_ab,
                    SUM(m.hits) as total_h,
                    SUM(m.doubles) as total_doubles,
                    SUM(m.triples) as total_triples,
                    SUM(m.home_runs) as total_hr,
                    SUM(m.walks) as total_bb,
                    SUM(m.strikeouts) as total_so,
                    SUM(m.stolen_bases) as total_sb
                FROM milb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                WHERE m.plate_appearances > 0
                AND (COALESCE(m.games_pitched, 0) = 0)
                AND p.birth_date IS NOT NULL
                GROUP BY m.mlb_player_id, p.name, p.birth_date, p.position, p.current_team
                HAVING SUM(m.plate_appearances) >= 100
            ),
            mlb_stats AS (
                SELECT
                    mlb_player_id,
                    SUM(plate_appearances) as mlb_pa,
                    SUM(at_bats) as mlb_ab
                FROM mlb_game_logs
                GROUP BY mlb_player_id
            ),
            statcast AS (
                SELECT *
                FROM milb_statcast_metrics_imputed
            )
            SELECT
                hs.*,
                COALESCE(mlb.mlb_pa, 0) as mlb_pa,
                sc.avg_ev,
                sc.max_ev,
                sc.hard_hit_pct,
                sc.barrel_pct
            FROM hitter_stats hs
            LEFT JOIN mlb_stats mlb ON hs.mlb_player_id = mlb.mlb_player_id
            LEFT JOIN statcast sc ON hs.mlb_player_id = sc.mlb_player_id
        '''))
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=[
        'mlb_player_id', 'full_name', 'birth_date', 'primary_position', 'current_team',
        'highest_level', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
        'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb',
        'mlb_pa', 'avg_ev', 'max_ev', 'hard_hit_pct', 'barrel_pct'
    ])

    logger.info(f'Loaded {len(df)} hitters')

    # Calculate stats
    df['avg'] = df['total_h'] / df['total_ab'].replace(0, np.nan)
    df['obp'] = (df['total_h'] + df['total_bb']) / df['total_pa'].replace(0, np.nan)
    df['tb'] = (df['total_h'] + df['total_doubles'] + df['total_triples']*2 + df['total_hr']*3)
    df['slg'] = df['tb'] / df['total_ab'].replace(0, np.nan)
    df['ops'] = df['obp'] + df['slg']
    df['iso'] = df['slg'] - df['avg']
    df['bb_rate'] = df['total_bb'] / df['total_pa']
    df['so_rate'] = df['total_so'] / df['total_pa']
    df = df.fillna(0)

    # Project MLB performance
    logger.info('Projecting MLB performance using age-aware model...')
    df = projector.predict_mlb_performance(df)

    # Apply age curves
    logger.info('Applying age curves...')
    age_curve = ProspectAgeCurve()
    df['current_age'] = (datetime.now() - pd.to_datetime(df['birth_date'])).dt.days / 365.25
    df['age_factor'] = df['current_age'].apply(age_curve.calculate_age_factor)

    # Filter by age
    df = df[df['age_factor'] > 0].copy()
    logger.info(f'After age filter: {len(df)} hitters')

    # Filter out MLB veterans (500+ PA)
    df = df[df['mlb_pa'] < 500].copy()
    logger.info(f'After MLB experience filter: {len(df)} hitters')

    # Calculate prospect value
    df['prospect_value'] = df['projected_mlb_wrc_plus'] * df['age_factor']

    # Statcast boost (for players with data)
    df['sc_boost'] = 1.0
    df.loc[df['avg_ev'] >= 90, 'sc_boost'] *= 1.10
    df.loc[df['avg_ev'] >= 87, 'sc_boost'] *= 1.05
    df.loc[df['hard_hit_pct'] >= 40, 'sc_boost'] *= 1.08
    df.loc[df['barrel_pct'] >= 10, 'sc_boost'] *= 1.10

    df['prospect_value'] *= df['sc_boost']

    # Rank
    df = df.sort_values('prospect_value', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)

    # Save
    output_file = 'prospect_rankings_v5_hitters_mlb_projected.csv'
    df.to_csv(output_file, index=False)

    # Display top 50
    print('\n' + '=' * 100)
    print('TOP 50 HITTERS - WITH MLB PROJECTIONS')
    print('=' * 100)

    display_cols = [
        'rank', 'full_name', 'current_age', 'primary_position', 'highest_level',
        'milb_pa', 'milb_ops', 'projected_mlb_wrc_plus', 'age_factor', 'prospect_value'
    ]

    print(df[display_cols].head(50).to_string(index=False))

    print('\n' + '=' * 100)
    logger.info(f'Rankings saved to {output_file}')
    logger.info(f'Total prospects: {len(df)}')

if __name__ == '__main__':
    asyncio.run(main())
