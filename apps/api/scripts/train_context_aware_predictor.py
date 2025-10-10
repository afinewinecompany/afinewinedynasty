"""
Train ML models with LEAGUE and POSITION CONTEXT ADJUSTMENTS.

This enhanced version integrates:
- League factors (level-adjusted performance)
- Age factors (age-relative performance)
- Position factors (position-adjusted performance)
- Comprehensive adjustments combining all context
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


class ContextAwarePredictor:
    """Train with league, age, and position context adjustments."""

    def __init__(self):
        self.models = {}
        self.feature_names = []
        self.target_names = []

    async def load_milb_with_context(self) -> pd.DataFrame:
        """Load MiLB data with league and position factors."""
        logger.info("Loading MiLB features WITH league/position context...")

        async with engine.begin() as conn:
            query = """
                SELECT
                    m.mlb_player_id,
                    m.level,
                    m.season,
                    p.position as primary_position,
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
                    AVG(m.babip) as avg_babip,
                    -- League factors
                    lf.lg_ops,
                    lf.lg_iso,
                    lf.lg_bb_rate,
                    lf.lg_so_rate,
                    lf.lg_hr_rate,
                    lf.lg_avg_age,
                    lf.lg_median_age,
                    -- Position factors
                    pf.pos_ops,
                    pf.pos_iso,
                    pf.pos_bb_rate,
                    pf.pos_so_rate,
                    pf.pos_avg_age
                FROM milb_game_logs m
                INNER JOIN prospects p ON m.mlb_player_id = CAST(p.mlb_player_id AS INTEGER)
                LEFT JOIN milb_league_factors lf ON m.season = lf.season AND m.level = lf.level
                LEFT JOIN milb_position_factors pf ON m.season = pf.season
                    AND m.level = pf.level
                    AND CASE
                        WHEN p.position = 'C' THEN 'C'
                        WHEN p.position IN ('SS', '2B', '3B', '1B') THEN 'IF'
                        WHEN p.position IN ('LF', 'CF', 'RF', 'OF') THEN 'OF'
                        WHEN p.position = 'DH' THEN 'DH'
                        ELSE 'TWP'
                    END = pf.position_group
                WHERE m.data_source = 'mlb_stats_api_gamelog'
                AND m.mlb_player_id IS NOT NULL
                AND p.birth_date IS NOT NULL
                AND (m.games_pitched IS NULL OR m.games_pitched = 0)
                GROUP BY m.mlb_player_id, m.level, m.season, p.birth_date, p.position,
                         lf.lg_ops, lf.lg_iso, lf.lg_bb_rate, lf.lg_so_rate, lf.lg_hr_rate,
                         lf.lg_avg_age, lf.lg_median_age,
                         pf.pos_ops, pf.pos_iso, pf.pos_bb_rate, pf.pos_so_rate, pf.pos_avg_age
            """

            result = await conn.execute(text(query))
            rows = result.fetchall()

            df = pd.DataFrame(rows, columns=[
                'mlb_player_id', 'level', 'season', 'primary_position', 'age_at_level',
                'games_played', 'total_pa', 'total_ab', 'total_runs', 'total_hits',
                'total_2b', 'total_3b', 'total_hr', 'total_rbi', 'total_bb', 'total_ibb',
                'total_so', 'total_sb', 'total_cs', 'total_hbp',
                'avg_ba', 'avg_obp', 'avg_slg', 'avg_ops', 'avg_babip',
                'lg_ops', 'lg_iso', 'lg_bb_rate', 'lg_so_rate', 'lg_hr_rate',
                'lg_avg_age', 'lg_median_age',
                'pos_ops', 'pos_iso', 'pos_bb_rate', 'pos_so_rate', 'pos_avg_age'
            ])

        # Convert to float
        numeric_cols = df.columns.difference(['mlb_player_id', 'level', 'season', 'primary_position'])
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(float)

        logger.info(f"Loaded {len(df)} player-level-season records with context")
        return df

    def calculate_context_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate context-aware features using league and position factors."""

        # Calculate basic rates first
        df['bb_rate'] = np.where(df['total_pa'] > 0, df['total_bb'] / df['total_pa'] * 100, 0)
        df['so_rate'] = np.where(df['total_pa'] > 0, df['total_so'] / df['total_pa'] * 100, 0)
        df['hr_rate'] = np.where(df['total_pa'] > 0, df['total_hr'] / df['total_pa'] * 100, 0)
        df['sb_rate'] = np.where(df['total_pa'] > 0, df['total_sb'] / df['total_pa'] * 100, 0)
        df['iso'] = df['avg_slg'] - df['avg_ba']

        # ========== LEAGUE-RELATIVE FEATURES ==========
        # Compare player to league average at same level
        df['ops_vs_league'] = np.where(df['lg_ops'] > 0, df['avg_ops'] / df['lg_ops'], 1.0)
        df['iso_vs_league'] = np.where(df['lg_iso'] > 0, df['iso'] / df['lg_iso'], 1.0)
        df['bb_rate_vs_league'] = np.where(df['lg_bb_rate'] > 0, df['bb_rate'] / df['lg_bb_rate'], 1.0)
        df['so_rate_vs_league'] = np.where(df['lg_so_rate'] > 0, df['so_rate'] / df['lg_so_rate'], 1.0)
        df['hr_rate_vs_league'] = np.where(df['lg_hr_rate'] > 0, df['hr_rate'] / df['lg_hr_rate'], 1.0)

        # ========== AGE-RELATIVE FEATURES ==========
        # Compare player age to league average age
        df['age_vs_league_avg'] = df['age_at_level'] - df['lg_avg_age']
        df['age_vs_league_median'] = df['age_at_level'] - df['lg_median_age']

        # Age-adjusted performance (younger = boost, older = penalty)
        df['age_adj_ops'] = df['avg_ops'] * (1 + (df['age_vs_league_avg'] * -0.02))
        df['age_adj_iso'] = df['iso'] * (1 + (df['age_vs_league_avg'] * -0.02))

        # ========== POSITION-RELATIVE FEATURES ==========
        # Compare player to position peers at same level
        df['ops_vs_position'] = np.where(df['pos_ops'] > 0, df['avg_ops'] / df['pos_ops'], 1.0)
        df['iso_vs_position'] = np.where(df['pos_iso'] > 0, df['iso'] / df['pos_iso'], 1.0)
        df['bb_rate_vs_position'] = np.where(df['pos_bb_rate'] > 0, df['bb_rate'] / df['pos_bb_rate'], 1.0)
        df['so_rate_vs_position'] = np.where(df['pos_so_rate'] > 0, df['so_rate'] / df['pos_so_rate'], 1.0)

        # ========== COMPREHENSIVE ADJUSTMENT ==========
        # Combine all context: level + age + position
        level_factor = df['ops_vs_league']
        age_factor = 1 + (df['age_vs_league_avg'] * -0.02)
        position_factor = np.where(df['pos_ops'] > 0, df['lg_ops'] / df['pos_ops'], 1.0)

        df['fully_adjusted_ops'] = df['avg_ops'] * level_factor * age_factor * position_factor
        df['fully_adjusted_iso'] = df['iso'] * level_factor * age_factor * position_factor

        # ========== PROSPECT VALUE INDICATORS ==========
        # Young + high level = high ceiling
        df['prospect_age_score'] = np.where(
            df['age_vs_league_avg'] < -1.5,  # 1.5+ years younger
            2.0,  # Elite age for level
            np.where(df['age_vs_league_avg'] < 0, 1.5, 1.0)  # Good age or average
        )

        # Performance above peers
        df['performance_vs_peers'] = (df['ops_vs_league'] + df['ops_vs_position']) / 2

        # Combined prospect score
        df['prospect_value_score'] = df['prospect_age_score'] * df['performance_vs_peers']

        logger.info("Created context-aware features:")
        logger.info(f"  - League-relative: ops_vs_league, iso_vs_league, bb_rate_vs_league, etc.")
        logger.info(f"  - Age-relative: age_vs_league_avg, age_adj_ops, prospect_age_score")
        logger.info(f"  - Position-relative: ops_vs_position, iso_vs_position, etc.")
        logger.info(f"  - Comprehensive: fully_adjusted_ops, prospect_value_score")

        return df

    def aggregate_by_player(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate context features by player across all levels."""

        # Define aggregation strategy
        agg_dict = {
            'age_at_level': 'mean',
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
            'total_so': 'sum',
            'total_sb': 'sum',
            'total_cs': 'sum',
            'avg_ba': 'mean',
            'avg_obp': 'mean',
            'avg_slg': 'mean',
            'avg_ops': 'mean',
            'bb_rate': 'mean',
            'so_rate': 'mean',
            'hr_rate': 'mean',
            'iso': 'mean',
            # Context features
            'ops_vs_league': 'mean',
            'iso_vs_league': 'mean',
            'bb_rate_vs_league': 'mean',
            'so_rate_vs_league': 'mean',
            'hr_rate_vs_league': 'mean',
            'age_vs_league_avg': 'mean',
            'age_vs_league_median': 'mean',
            'age_adj_ops': 'mean',
            'age_adj_iso': 'mean',
            'ops_vs_position': 'mean',
            'iso_vs_position': 'mean',
            'bb_rate_vs_position': 'mean',
            'so_rate_vs_position': 'mean',
            'fully_adjusted_ops': 'mean',
            'fully_adjusted_iso': 'mean',
            'prospect_age_score': 'mean',
            'performance_vs_peers': 'mean',
            'prospect_value_score': 'mean'
        }

        # Aggregate by player and level
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

        # Highest level reached
        player_features['highest_level'] = 0
        for i, level in enumerate(['A', 'A+', 'AA', 'AAA'], start=1):
            mask = player_features[f'total_pa_{level}'] > 0
            player_features.loc[mask, 'highest_level'] = i

        # Weighted context scores (prioritize higher levels)
        player_features['weighted_ops_vs_league'] = (
            player_features.get('ops_vs_league_AAA', 0) * 4 +
            player_features.get('ops_vs_league_AA', 0) * 3 +
            player_features.get('ops_vs_league_A+', 0) * 2 +
            player_features.get('ops_vs_league_A', 0) * 1
        ) / 10

        player_features['weighted_prospect_score'] = (
            player_features.get('prospect_value_score_AAA', 0) * 4 +
            player_features.get('prospect_value_score_AA', 0) * 3 +
            player_features.get('prospect_value_score_A+', 0) * 2 +
            player_features.get('prospect_value_score_A', 0) * 1
        ) / 10

        logger.info(f"Created features for {len(player_features)} unique players")
        return player_features

    async def load_mlb_targets(self) -> pd.DataFrame:
        """Load MLB performance targets."""
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
        """Prepare dataset with context-aware features."""
        logger.info("Preparing context-aware dataset...")

        # Load MiLB with context
        milb_raw = await self.load_milb_with_context()
        milb_features_calculated = self.calculate_context_features(milb_raw)
        milb_features = self.aggregate_by_player(milb_features_calculated)

        # Load MLB targets
        mlb_targets = await self.load_mlb_targets()

        # LEFT JOIN - keep ALL MiLB players
        dataset = milb_features.merge(mlb_targets, on='mlb_player_id', how='left')

        # Fill missing MLB values with zeros
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
        """Train models with context-aware features."""
        logger.info("\n" + "="*80)
        logger.info("Training CONTEXT-AWARE ML Models (League + Age + Position Factors)")
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

                # Feature importance for wRC+
                if target == 'mlb_wrc_plus' and model_name == 'Random Forest':
                    importance = pd.DataFrame({
                        'feature': self.feature_names,
                        'importance': model.feature_importances_
                    }).sort_values('importance', ascending=False)

                    logger.info("\n🎯 Top 30 Features for MLB Prediction (WITH CONTEXT):")
                    for _, row in importance.head(30).iterrows():
                        logger.info(f"  {row['feature']:50s}: {row['importance']:6.1%}")

                    # Show context feature contributions
                    context_features = importance[importance['feature'].str.contains(
                        'vs_league|vs_position|adjusted|prospect_|age_vs'
                    )]
                    if not context_features.empty:
                        logger.info(f"\n🔍 Context Features Total Importance: {context_features['importance'].sum():.1%}")

        return pd.DataFrame(results)


async def main():
    """Main execution."""
    logger.info("="*80)
    logger.info("Context-Aware ML Training")
    logger.info("Integrating: League Factors + Age Factors + Position Factors")
    logger.info("="*80)

    predictor = ContextAwarePredictor()
    results = await predictor.train_models()

    # Save results
    os.makedirs('ml_results', exist_ok=True)
    results.to_csv('ml_results/context_aware_results.csv', index=False)

    logger.info("\n" + "="*80)
    logger.info("Training Complete! Results saved to ml_results/context_aware_results.csv")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
