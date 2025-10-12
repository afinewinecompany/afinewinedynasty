"""
Train a model specifically on FanGraphs grades → MLB outcomes
to validate how scouting grades translate to MLB performance.
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


class FanGraphsToMLBValidator:
    """Validate FanGraphs grades against MLB outcomes."""

    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.grade_correlations = {}

    async def load_fangraphs_with_mlb(self):
        """Load FanGraphs grades for players who made it to MLB."""

        query = """
            WITH mlb_players AS (
                SELECT DISTINCT
                    mlb_player_id,
                    AVG(NULLIF(ops, 0)) as mlb_ops,
                    AVG(NULLIF(batting_avg, 0)) as mlb_avg,
                    SUM(home_runs) as total_mlb_hr,
                    SUM(stolen_bases) as total_mlb_sb,
                    COUNT(DISTINCT season) as mlb_seasons,
                    SUM(games_played) as mlb_games
                FROM mlb_game_logs
                WHERE season >= 2018
                  AND games_played > 0
                GROUP BY mlb_player_id
                HAVING SUM(games_played) >= 50
            ),
            fg_grades AS (
                SELECT
                    player_name,
                    mlb_id,
                    fv,
                    hit_present, hit_future,
                    game_power_present, game_power_future,
                    raw_power_present, raw_power_future,
                    speed_present, speed_future,
                    field_present, field_future,
                    has_upside,
                    frame, athleticism, arm_strength,
                    fb_grade, cmd_grade,
                    position,
                    season,
                    ROW_NUMBER() OVER (PARTITION BY mlb_id ORDER BY season DESC) as rn
                FROM fangraphs_prospect_grades
                WHERE mlb_id IS NOT NULL
                  AND fv IS NOT NULL
            ),
            latest_grades AS (
                SELECT * FROM fg_grades WHERE rn = 1
            )
            SELECT
                lg.*,
                mp.mlb_ops,
                mp.mlb_avg,
                mp.total_mlb_hr,
                mp.total_mlb_sb,
                mp.mlb_seasons,
                mp.mlb_games
            FROM latest_grades lg
            INNER JOIN mlb_players mp ON lg.mlb_id::varchar = mp.mlb_player_id::varchar
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to float
        for col in df.columns:
            if col not in ['player_name', 'position']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"Loaded {len(df)} FanGraphs prospects with MLB outcomes")
        return df

    async def load_current_prospects(self):
        """Load current prospects who haven't made MLB yet."""

        query = """
            WITH recent_grades AS (
                SELECT
                    player_name,
                    mlb_id,
                    fv,
                    hit_present, hit_future,
                    game_power_present, game_power_future,
                    raw_power_present, raw_power_future,
                    speed_present, speed_future,
                    field_present, field_future,
                    has_upside,
                    frame, athleticism, arm_strength,
                    fb_grade, cmd_grade,
                    position,
                    season,
                    ROW_NUMBER() OVER (PARTITION BY player_name ORDER BY season DESC) as rn
                FROM fangraphs_prospect_grades
                WHERE season >= 2024
                  AND fv IS NOT NULL
            )
            SELECT * FROM recent_grades WHERE rn = 1
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        # Convert to float
        for col in df.columns:
            if col not in ['player_name', 'position']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"Loaded {len(df)} current prospects for prediction")
        return df

    def analyze_grade_correlations(self, df):
        """Analyze how each grade correlates with MLB performance."""

        grade_cols = ['fv', 'hit_future', 'game_power_future', 'raw_power_future',
                     'speed_future', 'field_future']

        if 'mlb_ops' in df.columns:
            print("\n" + "="*80)
            print("FANGRAPHS GRADE CORRELATIONS WITH MLB OPS")
            print("="*80)

            for col in grade_cols:
                if col in df.columns:
                    correlation = df[[col, 'mlb_ops']].corr().iloc[0, 1]
                    self.grade_correlations[col] = correlation
                    print(f"{col:20s}: {correlation:.3f}")

            # Analyze by FV tiers
            print("\n" + "="*80)
            print("MLB PERFORMANCE BY FV TIER")
            print("="*80)

            fv_tiers = [
                (60, 80, '60-80 (Elite)'),
                (50, 60, '50-55 (Above Average)'),
                (45, 50, '45 (Average)'),
                (40, 45, '40 (Below Average)'),
                (0, 40, 'Below 40')
            ]

            for min_fv, max_fv, label in fv_tiers:
                tier_data = df[(df['fv'] >= min_fv) & (df['fv'] < max_fv)]
                if len(tier_data) > 0:
                    avg_ops = tier_data['mlb_ops'].mean()
                    count = len(tier_data)
                    print(f"{label:25s}: {count:4d} players, Avg OPS: {avg_ops:.3f}")

    def prepare_features(self, df):
        """Prepare features for modeling."""

        # Create composite features
        df['hit_tool'] = df['hit_future'].fillna(45)
        df['power_tool'] = (df['game_power_future'].fillna(45) +
                           df['raw_power_future'].fillna(45)) / 2
        df['speed_tool'] = df['speed_future'].fillna(45)
        df['field_tool'] = df['field_future'].fillna(45)

        # Physical attributes
        df['physical_score'] = (df['frame'].fillna(0) * 0.3 +
                               df['athleticism'].fillna(0) * 0.3 +
                               df['arm_strength'].fillna(45) * 0.4 / 80)

        # Tool counts
        df['plus_tools'] = ((df['hit_future'] >= 60).astype(int) +
                           (df['game_power_future'] >= 60).astype(int) +
                           (df['speed_future'] >= 60).astype(int) +
                           (df['field_future'] >= 60).astype(int))

        df['elite_tools'] = ((df['hit_future'] >= 70).astype(int) +
                            (df['game_power_future'] >= 70).astype(int) +
                            (df['speed_future'] >= 70).astype(int) +
                            (df['field_future'] >= 70).astype(int))

        # Upside adjustment
        df['has_upside'] = df['has_upside'].fillna(False).astype(int)
        df['fv_adjusted'] = df['fv'] * (1 + df['has_upside'] * 0.1)

        # Position groups (simplified)
        df['is_pitcher'] = df['position'].str.contains('P', na=False).astype(int)
        df['is_catcher'] = (df['position'] == 'C').astype(int)
        df['is_infielder'] = df['position'].isin(['SS', '2B', '3B', '1B']).astype(int)
        df['is_outfielder'] = df['position'].isin(['CF', 'LF', 'RF', 'OF']).astype(int)

        return df

    def train_models(self, X_train, X_test, y_train, y_test):
        """Train multiple models and evaluate."""

        models = {
            'xgboost': xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42),
            'random_forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
            'gradient_boost': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        }

        print("\n" + "="*80)
        print("MODEL PERFORMANCE (FanGraphs Grades → MLB OPS)")
        print("="*80)

        for name, model in models.items():
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            r2 = r2_score(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)

            self.models[name] = model
            print(f"{name:15s} - R²: {r2:.3f}, RMSE: {rmse:.3f}, MAE: {mae:.3f}")

        # Feature importance from best model
        best_model = self.models['gradient_boost']
        feature_importance = pd.DataFrame({
            'feature': X_train.columns,
            'importance': best_model.feature_importances_
        }).sort_values('importance', ascending=False)

        print("\n" + "="*80)
        print("TOP FEATURES FOR PREDICTING MLB SUCCESS")
        print("="*80)
        print(feature_importance.head(15))

        return feature_importance

    async def run_validation(self):
        """Run the complete validation pipeline."""

        # Load data
        logger.info("Loading FanGraphs prospects with MLB outcomes...")
        mlb_df = await self.load_fangraphs_with_mlb()

        if len(mlb_df) == 0:
            logger.warning("No FanGraphs prospects found with MLB outcomes")
            return

        # Analyze correlations
        self.analyze_grade_correlations(mlb_df)

        # Prepare features
        mlb_df = self.prepare_features(mlb_df)

        # Select features for modeling
        feature_cols = [
            'fv', 'hit_tool', 'power_tool', 'speed_tool', 'field_tool',
            'physical_score', 'plus_tools', 'elite_tools', 'fv_adjusted',
            'has_upside', 'is_pitcher', 'is_catcher', 'is_infielder', 'is_outfielder'
        ]

        if 'fb_grade' in mlb_df.columns:
            feature_cols.extend(['fb_grade', 'cmd_grade'])

        # Prepare data
        X = mlb_df[feature_cols].fillna(45)
        y = mlb_df['mlb_ops'].fillna(0.700)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train models
        feature_importance = self.train_models(
            pd.DataFrame(X_train_scaled, columns=X_train.columns),
            pd.DataFrame(X_test_scaled, columns=X_test.columns),
            y_train, y_test
        )

        # Now predict for current prospects
        logger.info("Loading current prospects for prediction...")
        current_df = await self.load_current_prospects()

        if len(current_df) > 0:
            current_df = self.prepare_features(current_df)

            # Prepare features
            X_current = current_df[feature_cols].fillna(45)
            X_current_scaled = self.scaler.transform(X_current)

            # Generate predictions
            predictions = {}
            for name, model in self.models.items():
                predictions[name] = model.predict(X_current_scaled)

            # Average predictions
            current_df['predicted_mlb_ops'] = np.mean(list(predictions.values()), axis=0)

            # Create rankings
            rankings = current_df[['player_name', 'fv', 'has_upside', 'predicted_mlb_ops', 'position']]
            rankings = rankings.sort_values('predicted_mlb_ops', ascending=False)

            # Save results
            rankings.to_csv('fangraphs_mlb_predictions.csv', index=False)

            print("\n" + "="*80)
            print("TOP 30 PROSPECTS BY PREDICTED MLB OPS")
            print("="*80)
            print(rankings.head(30).to_string(index=False))

            # Analyze by FV tier
            print("\n" + "="*80)
            print("PREDICTED MLB OPS BY FV TIER (Current Prospects)")
            print("="*80)

            fv_tiers = [
                (60, 80, '60-80 (Elite)'),
                (50, 60, '50-55 (Above Average)'),
                (45, 50, '45 (Average)'),
                (40, 45, '40 (Below Average)'),
                (0, 40, 'Below 40')
            ]

            for min_fv, max_fv, label in fv_tiers:
                tier_data = rankings[(rankings['fv'] >= min_fv) & (rankings['fv'] < max_fv)]
                if len(tier_data) > 0:
                    avg_pred = tier_data['predicted_mlb_ops'].mean()
                    count = len(tier_data)
                    print(f"{label:25s}: {count:4d} prospects, Avg Predicted OPS: {avg_pred:.3f}")

        # Save models
        with open('fangraphs_mlb_validator.pkl', 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scaler': self.scaler,
                'correlations': self.grade_correlations,
                'feature_importance': feature_importance.to_dict()
            }, f)

        logger.info("Validation complete!")
        return self


async def main():
    validator = FanGraphsToMLBValidator()
    await validator.run_validation()


if __name__ == "__main__":
    asyncio.run(main())