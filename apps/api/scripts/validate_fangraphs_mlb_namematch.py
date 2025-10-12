"""
Validate FanGraphs grades against MLB outcomes using name-based matching.
Handles fuzzy matching, nicknames, and name variations.
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
from difflib import SequenceMatcher
import re
import pickle
import logging

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FanGraphsNameMatcher:
    """Match FanGraphs prospects to MLB players using name matching."""

    def __init__(self):
        self.models = {}
        self.scaler = StandardScaler()
        self.matched_data = None

    def normalize_name(self, name):
        """Normalize a name for matching."""
        if pd.isna(name):
            return ""

        # Convert to string and lowercase
        name = str(name).lower()

        # Remove common suffixes
        name = re.sub(r'\b(jr\.?|sr\.?|iii|ii|iv|v)\b', '', name)

        # Remove accents and special characters
        replacements = {
            'á': 'a', 'à': 'a', 'ä': 'a', 'â': 'a', 'ã': 'a',
            'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
            'í': 'i', 'ì': 'i', 'ï': 'i', 'î': 'i',
            'ó': 'o', 'ò': 'o', 'ö': 'o', 'ô': 'o', 'õ': 'o',
            'ú': 'u', 'ù': 'u', 'ü': 'u', 'û': 'u',
            'ñ': 'n', 'ç': 'c'
        }
        for old, new in replacements.items():
            name = name.replace(old, new)

        # Remove non-alphanumeric characters
        name = re.sub(r'[^a-z0-9\s]', '', name)

        # Remove extra whitespace
        name = ' '.join(name.split())

        return name

    def name_similarity(self, name1, name2):
        """Calculate similarity between two names."""
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)

        if not norm1 or not norm2:
            return 0.0

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Check if last names match (important for baseball)
        parts1 = norm1.split()
        parts2 = norm2.split()

        if len(parts1) > 0 and len(parts2) > 0:
            # If last names match exactly, boost score
            if parts1[-1] == parts2[-1]:
                # Check first name similarity
                if len(parts1) > 1 and len(parts2) > 1:
                    first_sim = SequenceMatcher(None, parts1[0], parts2[0]).ratio()
                    return 0.7 + (0.3 * first_sim)  # 70% for last name, 30% for first

        # General sequence matching
        return SequenceMatcher(None, norm1, norm2).ratio()

    async def load_fangraphs_prospects(self):
        """Load FanGraphs prospects with grades."""

        query = """
        WITH latest_grades AS (
            SELECT DISTINCT ON (player_name)
                player_name,
                organization,
                position,
                age,
                fv,
                fb_grade,
                sl_grade,
                cb_grade,
                ch_grade,
                cmd_grade,
                import_date
            FROM fangraphs_prospect_grades
            WHERE fv IS NOT NULL
              AND player_name IS NOT NULL
            ORDER BY player_name, import_date DESC
        )
        SELECT * FROM latest_grades
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} FanGraphs prospects")
        return df

    async def load_mlb_players(self):
        """Load MLB players with outcomes."""

        query = """
        WITH mlb_stats AS (
            SELECT
                mlb.mlb_player_id,
                AVG(NULLIF(mlb.ops, 0)) as mlb_ops,
                AVG(NULLIF(mlb.batting_avg, 0)) as mlb_avg,
                SUM(mlb.home_runs) as total_hr,
                SUM(mlb.stolen_bases) as total_sb,
                COUNT(DISTINCT mlb.season) as mlb_seasons,
                SUM(mlb.games_played) as mlb_games,
                MAX(mlb.season) as latest_season,
                MIN(mlb.season) as first_season
            FROM mlb_game_logs mlb
            WHERE mlb.games_played > 0
            GROUP BY mlb.mlb_player_id
            HAVING SUM(mlb.games_played) >= 30
        ),
        player_names AS (
            -- Get player names from ID mapping
            SELECT DISTINCT
                mlb_id as mlb_player_id,
                player_name
            FROM player_id_mapping
            WHERE player_name IS NOT NULL
              AND mlb_id IS NOT NULL
        )
        SELECT
            ms.*,
            COALESCE(pn.player_name, 'Player_' || ms.mlb_player_id) as player_name
        FROM mlb_stats ms
        LEFT JOIN player_names pn ON ms.mlb_player_id = pn.mlb_player_id
        WHERE ms.first_season >= 2018  -- Focus on recent players
        """

        async with engine.begin() as conn:
            result = await conn.execute(text(query))
            df = pd.DataFrame(result.fetchall(), columns=result.keys())

        logger.info(f"Loaded {len(df)} MLB players with outcomes")
        return df

    def match_players(self, fg_df, mlb_df, threshold=0.85):
        """Match FanGraphs prospects to MLB players."""

        matches = []
        unmatched_fg = []

        logger.info(f"Matching {len(fg_df)} FanGraphs prospects to {len(mlb_df)} MLB players...")

        for idx, fg_player in fg_df.iterrows():
            if idx % 100 == 0:
                logger.info(f"Processing player {idx}/{len(fg_df)}")

            fg_name = fg_player['player_name']

            # Calculate similarity for all MLB players
            similarities = []
            for _, mlb_player in mlb_df.iterrows():
                sim = self.name_similarity(fg_name, mlb_player['player_name'])
                if sim >= threshold:
                    similarities.append({
                        'fg_name': fg_name,
                        'mlb_name': mlb_player['player_name'],
                        'mlb_player_id': mlb_player['mlb_player_id'],
                        'similarity': sim,
                        'mlb_ops': mlb_player['mlb_ops'],
                        'mlb_avg': mlb_player['mlb_avg'],
                        'total_hr': mlb_player['total_hr'],
                        'total_sb': mlb_player['total_sb'],
                        'mlb_games': mlb_player['mlb_games'],
                        'mlb_seasons': mlb_player['mlb_seasons']
                    })

            if similarities:
                # Take the best match
                best_match = max(similarities, key=lambda x: x['similarity'])

                # Combine with FanGraphs data
                match = {**fg_player.to_dict(), **best_match}
                matches.append(match)
            else:
                unmatched_fg.append(fg_player.to_dict())

        matches_df = pd.DataFrame(matches)
        unmatched_df = pd.DataFrame(unmatched_fg)

        logger.info(f"Matched {len(matches_df)} players, {len(unmatched_df)} unmatched")

        if len(matches_df) > 0:
            # Show sample matches
            print("\n" + "="*80)
            print("SAMPLE NAME MATCHES")
            print("="*80)
            sample = matches_df.nlargest(10, 'similarity')[['fg_name', 'mlb_name', 'similarity', 'fv', 'mlb_ops']]
            print(sample.to_string(index=False))

        return matches_df, unmatched_df

    async def analyze_matched_outcomes(self, matches_df):
        """Analyze how FV grades correlate with MLB outcomes."""

        print("\n" + "="*80)
        print("FANGRAPHS GRADE VALIDATION (NAME-MATCHED)")
        print("="*80)

        # Convert numeric columns
        numeric_cols = ['fv', 'age', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade',
                       'cmd_grade', 'mlb_ops', 'mlb_avg', 'total_hr', 'mlb_games']
        for col in numeric_cols:
            if col in matches_df.columns:
                matches_df[col] = pd.to_numeric(matches_df[col], errors='coerce')

        # FV tier analysis
        fv_tiers = [
            (60, 80, "60-80 (Elite)"),
            (55, 60, "55 (Plus)"),
            (50, 55, "50 (Above Average)"),
            (45, 50, "45 (Average)"),
            (40, 45, "40 (Below Average)"),
            (35, 40, "35 (Fringe)")
        ]

        print("\nFV Tier | Count | Avg OPS | Avg HR | Success Rate | Avg Games")
        print("-" * 70)

        for min_fv, max_fv, label in fv_tiers:
            tier_data = matches_df[(matches_df['fv'] >= min_fv) & (matches_df['fv'] < max_fv)]
            if len(tier_data) > 0:
                avg_ops = tier_data['mlb_ops'].mean()
                avg_hr = tier_data['total_hr'].mean()
                avg_games = tier_data['mlb_games'].mean()
                success_rate = (tier_data['mlb_ops'] > 0.700).mean() * 100

                print(f"{label:20s} | {len(tier_data):5d} | {avg_ops:.3f} | {avg_hr:6.1f} | "
                      f"{success_rate:5.1f}% | {avg_games:8.1f}")

        # Correlation analysis
        print("\n" + "="*80)
        print("GRADE CORRELATIONS WITH MLB OPS")
        print("="*80)

        correlations = {}
        grade_cols = ['fv', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade']

        for col in grade_cols:
            if col in matches_df.columns and matches_df[col].notna().sum() > 10:
                corr = matches_df[[col, 'mlb_ops']].corr().iloc[0, 1]
                correlations[col] = corr
                print(f"{col:15s}: {corr:+.3f}")

        return correlations

    async def train_prediction_model(self, matches_df):
        """Train model to predict MLB OPS from FanGraphs grades."""

        # Prepare features
        matches_df['is_pitcher'] = matches_df['position'].str.contains('P', na=False).astype(int)

        # Fill missing grades
        grade_cols = ['fv', 'fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade', 'age']
        for col in grade_cols:
            if col in matches_df.columns:
                if col == 'age':
                    matches_df[col] = matches_df[col].fillna(22)
                else:
                    matches_df[col] = matches_df[col].fillna(45 if col == 'fv' else 0)

        # Select features
        feature_cols = ['fv', 'age', 'is_pitcher']
        if 'fb_grade' in matches_df.columns:
            feature_cols.extend(['fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade'])

        X = matches_df[feature_cols]
        y = matches_df['mlb_ops'].fillna(0.700)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        print("\n" + "="*80)
        print("MODEL PERFORMANCE (NAME-MATCHED DATA)")
        print("="*80)

        models = {
            'xgboost': xgb.XGBRegressor(n_estimators=100, max_depth=5, random_state=42),
            'random_forest': RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42),
            'gradient_boost': GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        }

        best_model = None
        best_r2 = -1

        for name, model in models.items():
            model.fit(X_train_scaled, y_train)
            y_pred = model.predict(X_test_scaled)

            r2 = r2_score(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            mae = mean_absolute_error(y_test, y_pred)

            self.models[name] = model

            if r2 > best_r2:
                best_r2 = r2
                best_model = model

            print(f"{name:15s} - R²: {r2:.3f}, RMSE: {rmse:.3f}, MAE: {mae:.3f}")

        # Feature importance
        if hasattr(best_model, 'feature_importances_'):
            print("\n" + "="*80)
            print("FEATURE IMPORTANCE")
            print("="*80)

            importance_df = pd.DataFrame({
                'feature': feature_cols,
                'importance': best_model.feature_importances_
            }).sort_values('importance', ascending=False)

            print(importance_df.to_string(index=False))

        return best_model

    async def predict_current_prospects(self, fg_df):
        """Generate predictions for all current FanGraphs prospects."""

        # Prepare features
        fg_df['is_pitcher'] = fg_df['position'].str.contains('P', na=False).astype(int)

        # Fill missing values
        feature_cols = ['fv', 'age', 'is_pitcher']
        for col in ['fb_grade', 'sl_grade', 'cb_grade', 'ch_grade', 'cmd_grade']:
            if col in fg_df.columns:
                fg_df[col] = pd.to_numeric(fg_df[col], errors='coerce').fillna(0)
                feature_cols.append(col)

        fg_df['fv'] = pd.to_numeric(fg_df['fv'], errors='coerce').fillna(45)
        fg_df['age'] = pd.to_numeric(fg_df['age'], errors='coerce').fillna(22)

        X = fg_df[feature_cols]
        X_scaled = self.scaler.transform(X)

        # Generate predictions
        predictions = []
        for name, model in self.models.items():
            predictions.append(model.predict(X_scaled))

        # Average predictions
        fg_df['predicted_ops'] = np.mean(predictions, axis=0)

        # Sort by prediction
        fg_df = fg_df.sort_values('predicted_ops', ascending=False)

        print("\n" + "="*80)
        print("TOP 30 PROSPECTS BY PREDICTED MLB OPS")
        print("="*80)

        display_cols = ['player_name', 'organization', 'position', 'fv', 'age', 'predicted_ops']
        print(fg_df[display_cols].head(30).to_string(index=False))

        # Save results
        fg_df.to_csv('fangraphs_namematched_predictions.csv', index=False)
        logger.info("Predictions saved to fangraphs_namematched_predictions.csv")

        return fg_df

    async def run_validation(self):
        """Run complete name-matching validation pipeline."""

        # Load data
        logger.info("Loading FanGraphs prospects...")
        fg_df = await self.load_fangraphs_prospects()

        logger.info("Loading MLB players...")
        mlb_df = await self.load_mlb_players()

        # Match players
        logger.info("Matching players by name...")
        matches_df, unmatched_df = self.match_players(fg_df, mlb_df, threshold=0.80)

        if len(matches_df) == 0:
            logger.warning("No matches found!")
            return

        # Save matched data
        self.matched_data = matches_df
        matches_df.to_csv('fangraphs_mlb_namematches.csv', index=False)
        logger.info(f"Saved {len(matches_df)} matches to fangraphs_mlb_namematches.csv")

        # Analyze outcomes
        correlations = await self.analyze_matched_outcomes(matches_df)

        # Train model
        logger.info("Training prediction model...")
        model = await self.train_prediction_model(matches_df)

        # Generate predictions
        logger.info("Generating predictions for all prospects...")
        predictions = await self.predict_current_prospects(fg_df)

        # Save model and results
        with open('fangraphs_namematch_model.pkl', 'wb') as f:
            pickle.dump({
                'models': self.models,
                'scaler': self.scaler,
                'correlations': correlations,
                'matched_count': len(matches_df),
                'match_rate': len(matches_df) / len(fg_df) * 100
            }, f)

        print("\n" + "="*80)
        print("VALIDATION SUMMARY")
        print("="*80)
        print(f"FanGraphs Prospects:    {len(fg_df):,}")
        print(f"MLB Players:            {len(mlb_df):,}")
        print(f"Successful Matches:     {len(matches_df):,}")
        print(f"Match Rate:             {len(matches_df)/len(fg_df)*100:.1f}%")
        print(f"Unmatched Prospects:    {len(unmatched_df):,}")

        logger.info("Validation complete!")
        return self


async def main():
    matcher = FanGraphsNameMatcher()
    await matcher.run_validation()


if __name__ == "__main__":
    asyncio.run(main())