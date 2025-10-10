"""
Train ML models on ALL MiLB players - both MLB veterans and current prospects.

Approach: Predict MLB performance for everyone. Those without MLB experience
have baseline/zero stats, which provides valuable training signal about who
doesn't make it or performs poorly.
"""

import asyncio
import logging
from typing import Tuple
import os

import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AllPlayersPredictor:
    """Train on ALL players - prospects and MLB veterans alike."""

    def __init__(self):
        self.models = {}
        self.feature_names = []
        self.target_names = []

    async def load_all_milb_features(self) -> pd.DataFrame:
        """Load comprehensive MiLB features for ALL players."""
        logger.info("Loading MiLB features for ALL players...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    m.mlb_player_id,
                    m.level,
                    m.season,
                    EXTRACT(YEAR FROM MIN(m.game_date)) - EXTRACT(YEAR FROM p.birth_date) as age_at_level,
                    COUNT(*) as games_played,
                    SUM(m.plate_appearances) as total_pa,
                    SUM(m.at_bats) as total_ab,
                    SUM(m.runs) as total_runs,
                    SUM(m.hits) as total_hits,
                    SUM(m.doubles) as total_2b,
                    SUM(m.triples) as total_3b,
                    SUM(m.home_runs) as total_hr,
                    SUM(m.rbi) as total_rbi,
                    SUM(m.walks) as total_bb,
                    SUM(m.intentional_walks) as total_ibb,
                    SUM(m.strikeouts) as total_so,
                    SUM(m.stolen_bases) as total_sb,
                    SUM(m.caught_stealing) as total_cs,
                    SUM(m.hit_by_pitch) as total_hbp,
                    AVG(m.batting_avg) as avg_ba,
                    AVG(m.on_base_pct) as avg_obp,
                    AVG(m.slugging_pct) as avg_slg,
                    AVG(m.ops) as avg_ops,
                    AVG(m.babip) as avg_babip
                FROM milb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                WHERE m.data_source = 'mlb_stats_api_gamelog'
                AND m.mlb_player_id IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND (m.games_pitched IS NULL OR m.games_pitched = 0)
                GROUP BY m.mlb_player_id, m.level, m.season, p.birth_date
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'level', 'season', 'age_at_level', 'games_played',
                'total_pa', 'total_ab', 'total_runs', 'total_hits', 'total_2b',
                'total_3b', 'total_hr', 'total_rbi', 'total_bb', 'total_ibb',
                'total_so', 'total_sb', 'total_cs', 'total_hbp',
                'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops', 'avg_babip'
            ])

        # Convert to float
        numeric_cols = df.columns.difference(['mlb_player_id', 'level', 'season'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

        logger.info(f"Loaded {len(df)} player-level-season records")
        return df

    def calculate_comprehensive_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate age-adjusted and rate metrics."""

        # Age adjustments
        level_avg_ages = {'AAA': 25, 'AA': 23, 'A+': 22, 'A': 21}
        df['age_diff'] = df.apply(
            lambda row: level_avg_ages.get(row['level'], 22) - row['age_at_level']
            if pd.notna(row['age_at_level']) else 0,
            axis=1
        )

        # Calculate rates
        df['bb_rate'] = np.where(df['total_pa'] > 0, df['total_bb'] / df['total_pa'], 0)
        df['so_rate'] = np.where(df['total_pa'] > 0, df['total_so'] / df['total_pa'], 0)
        df['hr_rate'] = np.where(df['total_pa'] > 0, df['total_hr'] / df['total_pa'], 0)
        df['sb_rate'] = np.where(df['total_pa'] > 0, df['total_sb'] / df['total_pa'], 0)
        df['iso'] = df['avg_slg'] - df['avg_ba']

        # Age-adjusted metrics
        df['age_adj_ops'] = df['avg_ops'] + (df['age_diff'] * 0.010)
        df['age_adj_iso'] = df['iso'] + (df['age_diff'] * 0.005)
        df['age_adj_bb_rate'] = df['bb_rate'] + (df['age_diff'] * 0.005)
        df['age_adj_so_rate'] = df['so_rate'] - (df['age_diff'] * 0.008)

        return df

    def aggregate_by_player(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate features by player across all levels."""

        # Aggregate by player and level
        agg_dict = {
            'age_at_level': 'first',
            'age_diff': 'mean',
            'games_played': 'sum',
            'total_pa': 'sum',
            'total_ab': 'sum',
            'total_runs': 'sum',
            'total_hits': 'sum',
            'total_2b': 'sum',
            'total_3b': 'sum',
            'total_hr': 'sum',
            'total_rbi': 'sum',
            'total_bb': 'sum',
            'total_ibb': 'sum',
            'total_so': 'sum',
            'total_sb': 'sum',
            'total_cs': 'sum',
            'total_hbp': 'sum',
            'avg_ba': 'mean',
            'avg_obp': 'mean',
            'avg_slg': 'mean',
            'avg_ops': 'mean',
            'avg_babip': 'mean',
            'bb_rate': 'mean',
            'so_rate': 'mean',
            'hr_rate': 'mean',
            'sb_rate': 'mean',
            'iso': 'mean',
            'age_adj_ops': 'mean',
            'age_adj_iso': 'mean',
            'age_adj_bb_rate': 'mean',
            'age_adj_so_rate': 'mean'
        }

        agg_features = df.groupby(['mlb_player_id', 'level']).agg(agg_dict).reset_index()

        # Pivot by level
        level_features = []
        for level in ['AAA', 'AA', 'A+', 'A']:
            level_df = agg_features[agg_features['level'] == level].copy()
            level_df = level_df.drop('level', axis=1)
            level_df.columns = [f'{col}_{level}' if col != 'mlb_player_id' else col
                               for col in level_df.columns]
            level_features.append(level_df)

        # Merge all levels
        player_features = level_features[0]
        for level_df in level_features[1:]:
            player_features = player_features.merge(level_df, on='mlb_player_id', how='outer')

        player_features = player_features.fillna(0)

        # Add summary features
        player_features['total_milb_pa'] = sum(
            player_features.get(f'total_pa_{level}', 0)
            for level in ['AAA', 'AA', 'A+', 'A']
        )

        player_features['total_milb_games'] = sum(
            player_features.get(f'games_played_{level}', 0)
            for level in ['AAA', 'AA', 'A+', 'A']
        )

        # Highest level reached
        player_features['highest_level'] = 0
        for i, level in enumerate(['A', 'A+', 'AA', 'AAA'], start=1):
            mask = player_features[f'total_pa_{level}'] > 0
            player_features.loc[mask, 'highest_level'] = i

        logger.info(f"Created features for {len(player_features)} unique players")
        return player_features

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load MLB performance for ALL players (zero for those without MLB experience)."""
        logger.info("Loading MLB targets...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    mlb_player_id,
                    COUNT(*) as mlb_games,
                    SUM(plate_appearances) as mlb_total_pa,
                    SUM(at_bats) as mlb_total_ab,
                    SUM(hits) as mlb_total_hits,
                    SUM(doubles) as mlb_total_2b,
                    SUM(triples) as mlb_total_3b,
                    SUM(home_runs) as mlb_total_hr,
                    SUM(walks) as mlb_total_bb,
                    SUM(strikeouts) as mlb_total_so,
                    SUM(stolen_bases) as mlb_total_sb,
                    SUM(hit_by_pitch) as mlb_total_hbp,
                    SUM(sacrifice_flies) as mlb_total_sf,
                    AVG(batting_avg) as mlb_avg_ba,
                    AVG(on_base_pct) as mlb_avg_obp,
                    AVG(slugging_pct) as mlb_avg_slg,
                    AVG(ops) as mlb_avg_ops
                FROM mlb_game_logs
                WHERE mlb_player_id IS NOT NULL
                GROUP BY mlb_player_id
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'mlb_games', 'mlb_total_pa', 'mlb_total_ab',
                'mlb_total_hits', 'mlb_total_2b', 'mlb_total_3b', 'mlb_total_hr',
                'mlb_total_bb', 'mlb_total_so', 'mlb_total_sb', 'mlb_total_hbp',
                'mlb_total_sf', 'mlb_avg_ba', 'mlb_avg_obp', 'mlb_avg_slg', 'mlb_avg_ops'
            ])

        # Convert to float
        for col in df.columns:
            if col != 'mlb_player_id':
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)

        # Calculate derived metrics
        df['mlb_bb_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_bb'] / df['mlb_total_pa'], 0)
        df['mlb_so_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_so'] / df['mlb_total_pa'], 0)
        df['mlb_hr_rate'] = np.where(df['mlb_total_pa'] > 0, df['mlb_total_hr'] / df['mlb_total_pa'], 0)
        df['mlb_iso'] = df['mlb_avg_slg'] - df['mlb_avg_ba']

        # wOBA
        singles = df['mlb_total_hits'] - df['mlb_total_2b'] - df['mlb_total_3b'] - df['mlb_total_hr']
        woba_num = (0.69 * df['mlb_total_bb'] + 0.72 * df['mlb_total_hbp'] +
                    0.88 * singles + 1.24 * df['mlb_total_2b'] +
                    1.56 * df['mlb_total_3b'] + 1.95 * df['mlb_total_hr'])
        woba_denom = df['mlb_total_ab'] + df['mlb_total_bb'] + df['mlb_total_sf'] + df['mlb_total_hbp']
        df['mlb_woba'] = np.where(woba_denom > 0, woba_num / woba_denom, 0)

        # wRC+
        df['mlb_wrc_plus'] = ((df['mlb_woba'] - 0.320) / 1.25) * 100 + 100

        logger.info(f"Loaded MLB stats for {len(df)} players")
        return df

    async def prepare_full_dataset(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Prepare dataset with ALL players (LEFT join to keep everyone)."""
        logger.info("Preparing comprehensive dataset with ALL players...")

        # Load MiLB features
        milb_raw = await self.load_all_milb_features()
        milb_features_calculated = self.calculate_comprehensive_features(milb_raw)
        milb_features = self.aggregate_by_player(milb_features_calculated)

        # Load MLB targets
        mlb_targets = await self.load_mlb_targets()

        # LEFT JOIN - keep ALL MiLB players
        dataset = milb_features.merge(mlb_targets, on='mlb_player_id', how='left')

        # Fill missing MLB values with zeros (players without MLB experience)
        mlb_cols = [col for col in dataset.columns if col.startswith('mlb_')]
        dataset[mlb_cols] = dataset[mlb_cols].fillna(0)

        logger.info(f"Combined dataset: {len(dataset)} total players")
        logger.info(f"  With MLB experience: {(dataset['mlb_total_pa'] > 0).sum()}")
        logger.info(f"  Without MLB experience (prospects): {(dataset['mlb_total_pa'] == 0).sum()}")

        # Filter: require at least 100 MiLB PA
        dataset = dataset[dataset['total_milb_pa'] >= 100]

        logger.info(f"After filtering (100+ MiLB PA): {len(dataset)} players")

        # Separate features and targets
        feature_cols = [col for col in dataset.columns
                       if not col.startswith('mlb_') and col != 'mlb_player_id']
        target_cols = ['mlb_wrc_plus', 'mlb_woba', 'mlb_avg_ops', 'mlb_avg_obp',
                      'mlb_avg_slg', 'mlb_iso', 'mlb_bb_rate', 'mlb_so_rate', 'mlb_hr_rate']

        self.feature_names = feature_cols
        self.target_names = target_cols

        X = dataset[feature_cols]
        y = dataset[target_cols]

        X = X.fillna(0)

        logger.info(f"Features: {len(feature_cols)} columns")
        logger.info(f"Targets: {len(target_cols)} columns")

        return X, y

    async def train_models(self):
        """Train models on ALL players."""
        logger.info("\n" + "="*80)
        logger.info("Training ML Models on ALL Players")
        logger.info("="*80)

        X, y = await self.prepare_full_dataset()

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        models = {
            'Ridge': Ridge(alpha=1.0),
            'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10, n_jobs=-1),
            'Gradient Boosting': GradientBoostingRegressor(n_estimators=100, random_state=42, max_depth=5)
        }

        results = []

        for target in self.target_names:
            logger.info(f"\n--- Predicting {target} ---")

            for model_name, model in models.items():
                # Train
                model.fit(X_train, y_train[target])

                # Predict
                y_pred = model.predict(X_test)

                # Metrics
                r2 = r2_score(y_test[target], y_pred)
                mae = mean_absolute_error(y_test[target], y_pred)
                mse = mean_squared_error(y_test[target], y_pred)

                logger.info(f"  {model_name:20s}: R²={r2:7.3f}, MAE={mae:.4f}")

                results.append({
                    'target': target,
                    'model': model_name,
                    'r2': r2,
                    'mae': mae,
                    'mse': mse
                })

                # Feature importance for first target
                if target == 'mlb_wrc_plus' and model_name == 'Random Forest':
                    importance = pd.DataFrame({
                        'feature': self.feature_names,
                        'importance': model.feature_importances_
                    }).sort_values('importance', ascending=False)

                    logger.info("\nTop 20 Features for MLB Prediction:")
                    for _, row in importance.head(20).iterrows():
                        logger.info(f"  {row['feature']:40s}: {row['importance']:6.1%}")

        return pd.DataFrame(results)


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("ML Training on ALL Players (Prospects + MLB Veterans)")
    logger.info("="*80)

    predictor = AllPlayersPredictor()
    results = await predictor.train_models()

    # Save results
    os.makedirs('ml_results', exist_ok=True)
    results.to_csv('ml_results/all_players_results.csv', index=False)

    logger.info("\n" + "="*80)
    logger.info("Training Complete!")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
