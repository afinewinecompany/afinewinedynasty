"""
Validate FanGraphs grades against actual MLB outcomes using ID mappings.
Train a model to predict MLB success from FanGraphs grades.
"""

import asyncio
import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import xgboost as xgb
import pickle
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FanGraphsMLBValidator:
    """Validate FanGraphs grades against MLB outcomes."""

    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.validation_data = None

    async def load_fangraphs_with_mlb_outcomes(self):
        """Load FanGraphs grades matched to MLB outcomes using ID mapping."""

        query = """
        WITH fg_prospects AS (
            -- Get FanGraphs prospects with their grades
            SELECT DISTINCT ON (fg_player_id)
                fg_player_id,
                player_name,
                organization,
                position,
                age,
                fv,
                fb_grade,
                sl_grade,
                cb_grade,
                ch_grade,
                cmd_grade
            FROM fangraphs_prospect_grades
            WHERE fg_player_id IS NOT NULL
              AND fv IS NOT NULL
            ORDER BY fg_player_id, import_date DESC
        ),
        mlb_stats AS (
            -- Get MLB performance stats
            SELECT
                mlb_player_id,
                AVG(NULLIF(ops, 0)) as mlb_ops,
                AVG(NULLIF(batting_avg, 0)) as mlb_avg,
                SUM(home_runs) as total_hr,
                SUM(stolen_bases) as total_sb,
                COUNT(DISTINCT season) as mlb_seasons,
                SUM(games_played) as mlb_games
            FROM mlb_game_logs
            WHERE season >= 2018
              AND games_played > 0
            GROUP BY mlb_player_id
            HAVING SUM(games_played) >= 50
        )
        -- Join using the ID mapping
        SELECT
            fg.*,
            ms.mlb_ops,
            ms.mlb_avg,
            ms.total_hr,
            ms.total_sb,
            ms.mlb_seasons,
            ms.mlb_games,
            pm.mlb_id
        FROM fg_prospects fg
        INNER JOIN player_id_mapping pm ON fg.fg_player_id = pm.fg_id
        INNER JOIN mlb_stats ms ON pm.mlb_id = ms.mlb_player_id
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to numeric
        numeric_cols = ['age', 'fv', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade',
                       'cmd_grade', 'mlb_ops', 'mlb_avg', 'total_hr', 'total_sb',
                       'mlb_seasons', 'mlb_games']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"Loaded {len(df)} FanGraphs prospects with MLB outcomes")
        return df

    async def analyze_fv_accuracy(self, df):
        """Analyze how well FV predicts MLB outcomes."""

        print("\n" + "="*80)
        print("FANGRAPHS FV VALIDATION AGAINST MLB OUTCOMES")
        print("="*80)

        # Group by FV tier and analyze outcomes
        fv_tiers = [
            (60, 80, "60-80 (Elite)"),
            (55, 60, "55 (Plus)"),
            (50, 55, "50 (Above Average)"),
            (45, 50, "45 (Average)"),
            (40, 45, "40 (Below Average)"),
            (35, 40, "35 (Fringe)")
        ]

        print("\nFV Tier | Count | Avg OPS | Avg HR | Avg Games | Success Rate")
        print("-" * 70)

        for min_fv, max_fv, label in fv_tiers:
            tier_data = df[(df['fv'] >= min_fv) & (df['fv'] < max_fv)]
            if len(tier_data) > 0:
                avg_ops = tier_data['mlb_ops'].mean()
                avg_hr = tier_data['total_hr'].mean()
                avg_games = tier_data['mlb_games'].mean()
                # Success = OPS > 0.700
                success_rate = (tier_data['mlb_ops'] > 0.700).mean() * 100

                print(f"{label:20s} | {len(tier_data):5d} | {avg_ops:.3f} | {avg_hr:6.1f} | "
                      f"{avg_games:9.1f} | {success_rate:5.1f}%")

        # Correlation analysis
        print("\n" + "="*80)
        print("CORRELATION: FANGRAPHS GRADES vs MLB OPS")
        print("="*80)

        correlations = {}
        grade_cols = ['fv', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade']

        for col in grade_cols:
            if col in df.columns and df[col].notna().sum() > 10:
                corr = df[[col, 'mlb_ops']].corr().iloc[0, 1]
                correlations[col] = corr
                print(f"{col:15s}: {corr:.3f}")

        return correlations

    def prepare_modeling_data(self, df):
        """Prepare data for modeling."""

        # Create feature columns
        df['is_pitcher'] = df['position'].str.contains('P', na=False).astype(int)
        df['is_hitter'] = (~df['position'].str.contains('P', na=False)).astype(int)

        # For hitters, pitching grades don't matter
        df.loc[df['is_hitter'] == 1, ['fb_grade', 'sl_grade', 'cb_grade', 'ch_grade']] = 0

        # Fill missing values
        df['fv'] = df['fv'].fillna(45)
        df['fb_grade'] = df['fb_grade'].fillna(0)
        df['sl_grade'] = df['sl_grade'].fillna(0)
        df['cb_grade'] = df['cb_grade'].fillna(0)
        df['ch_grade'] = df['ch_grade'].fillna(0)
        df['cmd_grade'] = df['cmd_grade'].fillna(0)
        df['age'] = df['age'].fillna(22)

        return df

    async def train_validation_model(self, df):
        """Train model on FanGraphs grades to predict MLB OPS."""

        df = self.prepare_modeling_data(df)

        # Select features
        feature_cols = ['fv', 'age', 'fb_grade', 'sl_grade', 'cb_grade',
                       'ch_grade', 'cmd_grade', 'is_pitcher', 'is_hitter']

        X = df[feature_cols]
        y = df['mlb_ops'].fillna(0.700)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        print("\n" + "="*80)
        print("MODEL PERFORMANCE: FANGRAPHS → MLB OPS")
        print("="*80)

        models = {
            'xgboost': xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42),
            'random_forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
            'gradient_boost': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        }

        best_model = None
        best_score = -1

        for name, model in models.items():
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)

            r2 = r2_score(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)

            self.models[name] = model

            if r2 > best_score:
                best_score = r2
                best_model = model

            print(f"{name:15s} - R²: {r2:.3f}, RMSE: {rmse:.3f}, MAE: {mae:.3f}")

        # Feature importance
        print("\n" + "="*80)
        print("FEATURE IMPORTANCE")
        print("="*80)

        importance_df = pd.DataFrame({
            'feature': feature_cols,
            'importance': best_model.feature_importances_
        }).sort_values('importance', ascending=False)

        print(importance_df.to_string(index=False))

        return best_model, importance_df

    async def predict_current_prospects(self):
        """Use the model to predict outcomes for current prospects."""

        # Load current prospects
        query = """
        SELECT DISTINCT ON (fg_player_id)
            fg_player_id,
            player_name,
            organization,
            position,
            age,
            fv,
            fb_grade,
            sl_grade,
            cb_grade,
            ch_grade,
            cmd_grade
        FROM fangraphs_prospect_grades
        WHERE fg_player_id IS NOT NULL
          AND fv >= 45
        ORDER BY fg_player_id, import_date DESC
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            prospects_df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to numeric
        numeric_cols = ['age', 'fv', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade']
        for col in numeric_cols:
            if col in prospects_df.columns:
                prospects_df[col] = pd.to_numeric(prospects_df[col], errors='coerce')

        # Prepare features
        prospects_df = self.prepare_modeling_data(prospects_df)

        feature_cols = ['fv', 'age', 'fb_grade', 'sl_grade', 'cb_grade',
                       'ch_grade', 'cmd_grade', 'is_pitcher', 'is_hitter']

        X = prospects_df[feature_cols]
        X_scaled = self.scaler.transform(X)

        # Generate predictions from all models
        predictions = {}
        for name, model in self.models.items():
            predictions[name] = model.predict(X_scaled)

        # Average predictions
        prospects_df['predicted_ops'] = np.mean(list(predictions.values()), axis=0)

        # Sort by prediction
        prospects_df = prospects_df.sort_values('predicted_ops', ascending=False)

        print("\n" + "="*80)
        print("TOP 30 PROSPECTS BY PREDICTED MLB OPS")
        print("="*80)

        display_cols = ['player_name', 'organization', 'position', 'fv', 'age', 'predicted_ops']
        print(prospects_df[display_cols].head(30).to_string(index=False))

        # Save results
        prospects_df.to_csv('fangraphs_validated_predictions.csv', index=False)
        logger.info("Predictions saved to fangraphs_validated_predictions.csv")

        return prospects_df

    async def run_validation(self):
        """Run complete validation pipeline."""

        # Load data with MLB outcomes
        logger.info("Loading FanGraphs prospects with MLB outcomes...")
        mlb_df = await self.load_fangraphs_with_mlb_outcomes()

        if len(mlb_df) == 0:
            logger.warning("No FanGraphs prospects found with MLB outcomes")
            logger.info("This likely means the ID mapping didn't match any prospects")
            return

        # Analyze FV accuracy
        correlations = await self.analyze_fv_accuracy(mlb_df)

        # Train model
        logger.info("Training validation model...")
        model, importance = await self.train_validation_model(mlb_df)

        # Predict for current prospects
        logger.info("Generating predictions for current prospects...")
        predictions = await self.predict_current_prospects()

        # Save everything
        with open('fangraphs_mlb_validation_model.pkl', 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scaler': self.scaler,
                'correlations': correlations,
                'importance': importance.to_dict(),
                'validation_data': mlb_df.to_dict()
            }, f)

        logger.info("Validation complete!")
        return self


async def main():
    validator = FanGraphsMLBValidator()
    await validator.run_validation()


if __name__ == "__main__":
    asyncio.run(main())