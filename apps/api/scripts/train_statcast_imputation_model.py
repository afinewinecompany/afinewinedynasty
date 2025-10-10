"""
Train ML Model to Impute Missing Statcast Metrics

PROBLEM: Only some players have Statcast data, creating unfair advantages.

SOLUTION: Train models to predict Statcast metrics from traditional stats,
then impute (fill in) missing values for all players.

For Hitters:
- Predict: Exit Velo, Hard Hit%, Barrel%, Launch Angle
- From: ISO, HR rate, BB rate, SO rate, OPS, SLG

This ensures ALL players benefit equally from Statcast-based adjustments.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
import pickle
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StatcastImputationModel:
    """Train models to predict Statcast metrics from traditional stats."""

    def __init__(self):
        self.models = {}  # Will store one model per Statcast metric
        self.feature_names = []

    async def load_hitter_data_with_statcast(self) -> pd.DataFrame:
        """
        Load MiLB hitters who HAVE Statcast data.
        These are our training examples.
        """
        logger.info("Loading hitters with Statcast data for training...")

        async with engine.begin() as conn:
            result = await conn.execute(text("""
                WITH hitter_stats AS (
                    SELECT
                        m.mlb_player_id,
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
                    WHERE m.plate_appearances > 0
                    AND (COALESCE(m.games_pitched, 0) = 0)
                    GROUP BY m.mlb_player_id
                    HAVING SUM(m.plate_appearances) >= 100
                )
                SELECT
                    hs.*,
                    sc.avg_ev,
                    sc.max_ev,
                    sc.hard_hit_pct,
                    sc.barrel_pct,
                    sc.avg_la
                FROM hitter_stats hs
                INNER JOIN milb_statcast_metrics sc ON hs.mlb_player_id = sc.mlb_player_id
                WHERE sc.avg_ev > 0  -- Must have actual Statcast data
            """))
            rows = result.fetchall()

        if not rows:
            logger.error("No training data found! Need players with both MiLB stats AND Statcast.")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
            'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb',
            'avg_ev', 'max_ev', 'hard_hit_pct', 'barrel_pct', 'avg_la'
        ])

        # Convert to numeric
        for col in df.columns:
            if col != 'mlb_player_id':
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df.dropna()

        logger.info(f"Loaded {len(df)} hitters with both traditional stats AND Statcast")
        return df

    def calculate_traditional_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate traditional stats that will predict Statcast metrics."""
        df = df.copy()

        # Basic rates
        df['avg'] = df['total_h'] / df['total_ab'].replace(0, np.nan)
        df['obp'] = (df['total_h'] + df['total_bb']) / df['total_pa'].replace(0, np.nan)

        # Power indicators
        df['iso'] = ((df['total_doubles'] + df['total_triples']*2 + df['total_hr']*3) /
                     df['total_ab'].replace(0, np.nan))
        df['slg'] = ((df['total_h'] + df['total_doubles'] + df['total_triples']*2 + df['total_hr']*3) /
                     df['total_ab'].replace(0, np.nan))
        df['ops'] = df['obp'] + df['slg']

        # Contact/discipline
        df['bb_rate'] = df['total_bb'] / df['total_pa']
        df['so_rate'] = df['total_so'] / df['total_pa']
        df['contact_rate'] = 1 - df['so_rate']
        df['bb_so_ratio'] = df['total_bb'] / df['total_so'].replace(0, np.nan)

        # Power metrics
        df['hr_rate'] = df['total_hr'] / df['total_pa']
        df['hr_per_fb'] = df['total_hr'] / (df['total_hr'] + df['total_doubles'] + df['total_triples']).replace(0, np.nan)
        df['xbh_rate'] = (df['total_doubles'] + df['total_triples'] + df['total_hr']) / df['total_ab'].replace(0, np.nan)

        # Speed
        df['sb_rate'] = df['total_sb'] / df['total_pa']

        # Sample size
        df['log_pa'] = np.log1p(df['total_pa'])

        df = df.fillna(0)
        return df

    def train_models(self, df: pd.DataFrame):
        """
        Train separate Random Forest models for each Statcast metric.

        Models:
        1. Exit Velo (avg_ev)
        2. Max Exit Velo (max_ev)
        3. Hard Hit % (hard_hit_pct)
        4. Barrel % (barrel_pct)
        5. Launch Angle (avg_la)
        """
        logger.info("\n" + "="*80)
        logger.info("TRAINING STATCAST IMPUTATION MODELS")
        logger.info("="*80)

        # Feature columns (traditional stats)
        feature_cols = [
            'avg', 'obp', 'slg', 'ops', 'iso',
            'bb_rate', 'so_rate', 'contact_rate', 'bb_so_ratio',
            'hr_rate', 'hr_per_fb', 'xbh_rate', 'sb_rate',
            'log_pa'
        ]
        self.feature_names = feature_cols

        # Target columns (Statcast metrics to predict)
        target_cols = {
            'avg_ev': 'Average Exit Velocity',
            'max_ev': 'Max Exit Velocity',
            'hard_hit_pct': 'Hard Hit %',
            'barrel_pct': 'Barrel %',
            'avg_la': 'Average Launch Angle'
        }

        X = df[feature_cols]

        results = []

        for target, target_name in target_cols.items():
            logger.info(f"\n--- Training model for {target_name} ---")

            y = df[target]

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )

            # Train Random Forest
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                min_samples_leaf=3,
                random_state=42,
                n_jobs=-1
            )

            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            r2 = r2_score(y_test, y_pred)
            mae = mean_absolute_error(y_test, y_pred)

            logger.info(f"  R² Score: {r2:.3f}")
            logger.info(f"  MAE: {mae:.2f}")

            # Feature importance
            importance = pd.DataFrame({
                'feature': feature_cols,
                'importance': model.feature_importances_
            }).sort_values('importance', ascending=False)

            logger.info(f"  Top 5 predictors:")
            for _, row in importance.head(5).iterrows():
                logger.info(f"    {row['feature']}: {row['importance']:.3f}")

            # Store model
            self.models[target] = model

            results.append({
                'metric': target_name,
                'r2': r2,
                'mae': mae
            })

        # Summary
        logger.info("\n" + "="*80)
        logger.info("MODEL TRAINING SUMMARY")
        logger.info("="*80)
        results_df = pd.DataFrame(results)
        print(results_df.to_string(index=False))

        return results_df

    def save_models(self, filename: str = 'statcast_imputation_models.pkl'):
        """Save trained models to disk."""
        model_data = {
            'models': self.models,
            'feature_names': self.feature_names
        }

        with open(filename, 'wb') as f:
            pickle.dump(model_data, f)

        logger.info(f"\n✅ Models saved to {filename}")

    async def predict_for_all_hitters(self) -> pd.DataFrame:
        """
        Load ALL hitters (with or without Statcast) and predict metrics.

        For players WITH Statcast: Use actual values
        For players WITHOUT Statcast: Use predicted values
        """
        logger.info("\n" + "="*80)
        logger.info("IMPUTING STATCAST METRICS FOR ALL HITTERS")
        logger.info("="*80)

        async with engine.begin() as conn:
            result = await conn.execute(text("""
                WITH hitter_stats AS (
                    SELECT
                        m.mlb_player_id,
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
                    WHERE m.plate_appearances > 0
                    AND (COALESCE(m.games_pitched, 0) = 0)
                    GROUP BY m.mlb_player_id
                    HAVING SUM(m.plate_appearances) >= 100
                )
                SELECT
                    hs.*,
                    sc.avg_ev as actual_avg_ev,
                    sc.max_ev as actual_max_ev,
                    sc.hard_hit_pct as actual_hard_hit_pct,
                    sc.barrel_pct as actual_barrel_pct,
                    sc.avg_la as actual_avg_la
                FROM hitter_stats hs
                LEFT JOIN milb_statcast_metrics sc ON hs.mlb_player_id = sc.mlb_player_id
            """))
            rows = result.fetchall()

        df = pd.DataFrame(rows, columns=[
            'mlb_player_id', 'total_pa', 'total_ab', 'total_h', 'total_doubles',
            'total_triples', 'total_hr', 'total_bb', 'total_so', 'total_sb',
            'actual_avg_ev', 'actual_max_ev', 'actual_hard_hit_pct',
            'actual_barrel_pct', 'actual_avg_la'
        ])

        # Convert to numeric
        for col in df.columns:
            if col != 'mlb_player_id':
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Calculate traditional features
        df = self.calculate_traditional_features(df)

        # Predict Statcast metrics
        X = df[self.feature_names]

        for metric, model in self.models.items():
            pred_col = f'pred_{metric}'
            df[pred_col] = model.predict(X)

        # Create final columns: Use actual if available, else predicted
        df['avg_ev'] = df['actual_avg_ev'].fillna(df['pred_avg_ev'])
        df['max_ev'] = df['actual_max_ev'].fillna(df['pred_max_ev'])
        df['hard_hit_pct'] = df['actual_hard_hit_pct'].fillna(df['pred_hard_hit_pct'])
        df['barrel_pct'] = df['actual_barrel_pct'].fillna(df['pred_barrel_pct'])
        df['avg_la'] = df['actual_avg_la'].fillna(df['pred_avg_la'])

        # Track which were imputed
        df['statcast_source'] = np.where(df['actual_avg_ev'].notna(), 'actual', 'imputed')

        logger.info(f"\nProcessed {len(df)} hitters:")
        logger.info(f"  With actual Statcast: {(df['statcast_source'] == 'actual').sum()}")
        logger.info(f"  With imputed Statcast: {(df['statcast_source'] == 'imputed').sum()}")

        return df

    async def save_imputed_data(self, df: pd.DataFrame):
        """Save imputed Statcast data to new table."""
        logger.info("\nSaving imputed Statcast data to database...")

        async with engine.begin() as conn:
            # Create table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS milb_statcast_metrics_imputed (
                    id SERIAL PRIMARY KEY,
                    mlb_player_id INTEGER UNIQUE NOT NULL,
                    avg_ev FLOAT,
                    max_ev FLOAT,
                    hard_hit_pct FLOAT,
                    barrel_pct FLOAT,
                    avg_la FLOAT,
                    statcast_source VARCHAR(20),  -- 'actual' or 'imputed'
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))

            # Clear existing data
            await conn.execute(text("DELETE FROM milb_statcast_metrics_imputed"))

            # Insert
            for _, row in df.iterrows():
                await conn.execute(text("""
                    INSERT INTO milb_statcast_metrics_imputed
                    (mlb_player_id, avg_ev, max_ev, hard_hit_pct, barrel_pct, avg_la, statcast_source)
                    VALUES (:mlb_player_id, :avg_ev, :max_ev, :hard_hit_pct, :barrel_pct, :avg_la, :statcast_source)
                    ON CONFLICT (mlb_player_id) DO UPDATE SET
                        avg_ev = EXCLUDED.avg_ev,
                        max_ev = EXCLUDED.max_ev,
                        hard_hit_pct = EXCLUDED.hard_hit_pct,
                        barrel_pct = EXCLUDED.barrel_pct,
                        avg_la = EXCLUDED.avg_la,
                        statcast_source = EXCLUDED.statcast_source,
                        updated_at = NOW()
                """), {
                    'mlb_player_id': int(row['mlb_player_id']),
                    'avg_ev': float(row['avg_ev']),
                    'max_ev': float(row['max_ev']),
                    'hard_hit_pct': float(row['hard_hit_pct']),
                    'barrel_pct': float(row['barrel_pct']),
                    'avg_la': float(row['avg_la']),
                    'statcast_source': row['statcast_source']
                })

        logger.info(f"✅ Saved {len(df)} records to milb_statcast_metrics_imputed")


async def main():
    """Main execution."""
    model = StatcastImputationModel()

    # Step 1: Load training data (players with Statcast)
    training_data = await model.load_hitter_data_with_statcast()

    if training_data.empty:
        logger.error("Cannot train models without Statcast data!")
        return

    # Step 2: Calculate features
    training_data = model.calculate_traditional_features(training_data)

    # Step 3: Train models
    results = model.train_models(training_data)

    # Step 4: Save models
    model.save_models()

    # Step 5: Predict for ALL players
    all_hitters = await model.predict_for_all_hitters()

    # Step 6: Save imputed data
    await model.save_imputed_data(all_hitters)

    # Export to CSV for review
    export_cols = [
        'mlb_player_id', 'total_pa', 'ops', 'iso', 'hr_rate',
        'avg_ev', 'max_ev', 'hard_hit_pct', 'barrel_pct', 'statcast_source'
    ]
    all_hitters[export_cols].to_csv('statcast_imputed_preview.csv', index=False)
    logger.info("\n✅ Preview exported to statcast_imputed_preview.csv")

    logger.info("\n" + "="*80)
    logger.info("COMPLETE! All hitters now have Statcast metrics (actual or imputed)")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
