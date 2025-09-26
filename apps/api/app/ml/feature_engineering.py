"""
Feature engineering pipeline for ML model training.
Implements age adjustments, rate statistics, and level progression metrics.
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.feature_selection import SelectKBest, f_regression, mutual_info_regression
import warnings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class AgeAdjustmentCalculator:
    """Calculate age-adjusted performance metrics."""

    def __init__(self):
        # Standard league age baselines for different levels
        self.level_age_baselines = {
            'MLB': 28.0,
            'Triple-A': 26.0,
            'Double-A': 24.0,
            'High-A': 22.0,
            'Low-A': 20.0,
            'Rookie': 19.0,
            'Complex': 18.5,
            'DSL': 18.0,
            'FCL': 18.0
        }

    def calculate_age_adjusted_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate age-adjusted performance metrics.

        Args:
            df: DataFrame with age, level, and performance stats

        Returns:
            DataFrame with age-adjusted metrics
        """
        logger.info("Calculating age-adjusted performance metrics")

        df_adjusted = df.copy()

        # Get baseline age for each player's level
        df_adjusted['level_age_baseline'] = df_adjusted['level'].map(
            self.level_age_baselines
        ).fillna(22.0)  # Default baseline

        # Calculate age differential
        df_adjusted['age_differential'] = df_adjusted['age'] - df_adjusted['level_age_baseline']

        # Age adjustment factor (younger players get bonus, older get penalty)
        # Using logarithmic scaling to avoid extreme adjustments
        df_adjusted['age_adjustment_factor'] = np.exp(-df_adjusted['age_differential'] * 0.1)

        # Apply age adjustments to key offensive stats
        offensive_stats = ['batting_avg', 'on_base_pct', 'slugging_pct', 'ops',
                          'iso', 'woba', 'wrc_plus', 'babip']
        for stat in offensive_stats:
            if stat in df_adjusted.columns:
                df_adjusted[f'{stat}_age_adj'] = (
                    df_adjusted[stat] * df_adjusted['age_adjustment_factor']
                )

        # Apply age adjustments to pitching stats (lower ERA/WHIP is better)
        pitching_stats = ['era', 'whip', 'fip', 'xfip']
        for stat in pitching_stats:
            if stat in df_adjusted.columns:
                # For pitching stats, younger age should reduce the stat value
                df_adjusted[f'{stat}_age_adj'] = (
                    df_adjusted[stat] / df_adjusted['age_adjustment_factor']
                )

        # Apply age adjustments to rate stats
        rate_stats = ['k_rate', 'bb_rate', 'contact_rate', 'swing_strike_rate']
        for stat in rate_stats:
            if stat in df_adjusted.columns:
                df_adjusted[f'{stat}_age_adj'] = (
                    df_adjusted[stat] * df_adjusted['age_adjustment_factor']
                )

        logger.info(f"Applied age adjustments to {len(df_adjusted)} player records")
        return df_adjusted


class LevelProgressionCalculator:
    """Calculate level progression rate metrics."""

    def __init__(self):
        # Level hierarchy for progression calculation
        self.level_hierarchy = {
            'DSL': 1,
            'FCL': 1,
            'Complex': 2,
            'Rookie': 3,
            'Low-A': 4,
            'High-A': 5,
            'Double-A': 6,
            'Triple-A': 7,
            'MLB': 8
        }

    def calculate_progression_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate level progression rate metrics.

        Args:
            df: DataFrame with player level progression data

        Returns:
            DataFrame with progression metrics
        """
        logger.info("Calculating level progression metrics")

        # Sort by player and date to track progression
        df_sorted = df.sort_values(['mlb_id', 'date_recorded'])

        progression_metrics = []

        for mlb_id, player_data in df_sorted.groupby('mlb_id'):
            player_metrics = self._calculate_player_progression(player_data)
            progression_metrics.append(player_metrics)

        progression_df = pd.DataFrame(progression_metrics)

        # Merge back with original data
        df_with_progression = df.merge(
            progression_df, on='mlb_id', how='left'
        )

        logger.info(f"Calculated progression metrics for {len(progression_df)} players")
        return df_with_progression

    def _calculate_player_progression(self, player_data: pd.DataFrame) -> Dict[str, Any]:
        """Calculate progression metrics for a single player."""

        # Get level numeric values
        player_data = player_data.copy()
        player_data['level_numeric'] = player_data['level'].map(
            self.level_hierarchy
        ).fillna(0)

        mlb_id = player_data['mlb_id'].iloc[0]

        # Basic progression metrics
        levels_played = player_data['level_numeric'].nunique()
        max_level_reached = player_data['level_numeric'].max()
        min_level = player_data['level_numeric'].min()

        # Time-based progression
        total_time_span = (
            player_data['date_recorded'].max() -
            player_data['date_recorded'].min()
        ).days

        # Level advancement rate
        level_advancement = max_level_reached - min_level
        advancement_rate = level_advancement / max(total_time_span / 365, 0.1)  # levels per year

        # Time spent at each level
        level_durations = {}
        for level in player_data['level'].unique():
            level_data = player_data[player_data['level'] == level]
            if len(level_data) > 1:
                duration = (level_data['date_recorded'].max() -
                           level_data['date_recorded'].min()).days
                level_durations[f'days_at_{level.lower().replace("-", "_")}'] = duration

        # Regression detection (moving to lower levels)
        level_changes = player_data['level_numeric'].diff().fillna(0)
        regressions = (level_changes < 0).sum()
        regression_rate = regressions / max(len(player_data) - 1, 1)

        return {
            'mlb_id': mlb_id,
            'levels_played_count': levels_played,
            'max_level_reached': max_level_reached,
            'level_advancement_total': level_advancement,
            'advancement_rate_per_year': advancement_rate,
            'regression_count': regressions,
            'regression_rate': regression_rate,
            'total_time_span_days': total_time_span,
            **level_durations
        }


class RateStatisticsCalculator:
    """Calculate per-inning and per-game rate statistics."""

    def calculate_rate_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate comprehensive rate statistics.

        Args:
            df: DataFrame with counting stats and playing time

        Returns:
            DataFrame with rate statistics
        """
        logger.info("Calculating rate statistics")

        df_rates = df.copy()

        # Offensive rate stats (per plate appearance/at bat)
        if 'plate_appearances' in df_rates.columns and 'at_bats' in df_rates.columns:
            # Contact and discipline rates
            df_rates['contact_rate'] = (
                df_rates.get('hits', 0) / df_rates['at_bats'].replace(0, np.nan)
            )
            df_rates['walk_rate'] = (
                df_rates.get('walks', 0) / df_rates['plate_appearances'].replace(0, np.nan)
            )
            df_rates['strikeout_rate'] = (
                df_rates.get('strikeouts', 0) / df_rates['plate_appearances'].replace(0, np.nan)
            )
            df_rates['power_rate'] = (
                df_rates.get('home_runs', 0) / df_rates['at_bats'].replace(0, np.nan)
            )

        # Pitching rate stats (per inning)
        if 'innings_pitched' in df_rates.columns:
            df_rates['k_per_9'] = (
                df_rates.get('strikeouts', 0) * 9 /
                df_rates['innings_pitched'].replace(0, np.nan)
            )
            df_rates['bb_per_9'] = (
                df_rates.get('walks', 0) * 9 /
                df_rates['innings_pitched'].replace(0, np.nan)
            )
            df_rates['hr_per_9'] = (
                df_rates.get('home_runs_allowed', 0) * 9 /
                df_rates['innings_pitched'].replace(0, np.nan)
            )
            df_rates['hits_per_9'] = (
                df_rates.get('hits_allowed', 0) * 9 /
                df_rates['innings_pitched'].replace(0, np.nan)
            )

        # Per-game rates
        if 'games_played' in df_rates.columns:
            df_rates['hits_per_game'] = (
                df_rates.get('hits', 0) / df_rates['games_played'].replace(0, np.nan)
            )
            df_rates['rbi_per_game'] = (
                df_rates.get('rbi', 0) / df_rates['games_played'].replace(0, np.nan)
            )
            df_rates['runs_per_game'] = (
                df_rates.get('runs', 0) / df_rates['games_played'].replace(0, np.nan)
            )

        # Advanced rate metrics
        self._calculate_advanced_rates(df_rates)

        logger.info("Rate statistics calculation completed")
        return df_rates

    def _calculate_advanced_rates(self, df: pd.DataFrame) -> None:
        """Calculate advanced rate statistics."""

        # ISO (Isolated Power)
        if all(col in df.columns for col in ['slugging_pct', 'batting_avg']):
            df['iso'] = df['slugging_pct'] - df['batting_avg']

        # BABIP (Batting Average on Balls in Play)
        if all(col in df.columns for col in ['hits', 'home_runs', 'at_bats', 'strikeouts']):
            df['babip'] = (
                (df['hits'] - df['home_runs']) /
                (df['at_bats'] - df['strikeouts'] - df['home_runs']).replace(0, np.nan)
            )

        # K/BB ratio for pitchers
        if all(col in df.columns for col in ['strikeouts', 'walks']):
            df['k_bb_ratio'] = df['strikeouts'] / df['walks'].replace(0, np.nan)


class FeatureScalingPipeline:
    """Handle feature scaling and normalization."""

    def __init__(self):
        self.scalers = {}

    def fit_transform_features(self, df: pd.DataFrame,
                              features: List[str],
                              scaling_method: str = 'standard') -> pd.DataFrame:
        """
        Fit and transform features using specified scaling method.

        Args:
            df: DataFrame with features to scale
            features: List of feature column names
            scaling_method: 'standard', 'minmax', or 'robust'

        Returns:
            DataFrame with scaled features
        """
        logger.info(f"Scaling {len(features)} features using {scaling_method} method")

        df_scaled = df.copy()

        # Select only numeric features that exist in the dataframe
        numeric_features = [f for f in features if f in df.columns and
                           pd.api.types.is_numeric_dtype(df[f])]

        if not numeric_features:
            logger.warning("No numeric features found for scaling")
            return df_scaled

        # Choose scaler
        if scaling_method == 'standard':
            scaler = StandardScaler()
        elif scaling_method == 'minmax':
            scaler = MinMaxScaler()
        else:
            raise ValueError(f"Unsupported scaling method: {scaling_method}")

        # Fit and transform
        scaled_values = scaler.fit_transform(df[numeric_features].fillna(0))

        # Update dataframe with scaled values
        for i, feature in enumerate(numeric_features):
            df_scaled[f'{feature}_scaled'] = scaled_values[:, i]

        # Store scaler for future use
        self.scalers[scaling_method] = scaler
        self.scalers[f'{scaling_method}_features'] = numeric_features

        logger.info(f"Successfully scaled {len(numeric_features)} features")
        return df_scaled

    def transform_features(self, df: pd.DataFrame,
                          scaling_method: str = 'standard') -> pd.DataFrame:
        """Transform features using previously fitted scaler."""

        if scaling_method not in self.scalers:
            raise ValueError(f"Scaler for {scaling_method} not fitted yet")

        scaler = self.scalers[scaling_method]
        features = self.scalers[f'{scaling_method}_features']

        df_scaled = df.copy()
        scaled_values = scaler.transform(df[features].fillna(0))

        for i, feature in enumerate(features):
            df_scaled[f'{feature}_scaled'] = scaled_values[:, i]

        return df_scaled


class FeatureSelector:
    """Feature selection based on importance scores."""

    def __init__(self):
        self.selector = None
        self.selected_features = None

    def select_features(self, X: pd.DataFrame, y: pd.Series,
                       method: str = 'f_regression',
                       k: int = 50) -> Tuple[pd.DataFrame, List[str]]:
        """
        Select top k features based on statistical tests.

        Args:
            X: Feature DataFrame
            y: Target variable
            method: Feature selection method
            k: Number of features to select

        Returns:
            Tuple of (selected features DataFrame, feature names list)
        """
        logger.info(f"Selecting top {k} features using {method}")

        # Handle missing values
        X_clean = X.fillna(0)
        y_clean = y.fillna(0)

        # Choose selection method
        if method == 'f_regression':
            selector = SelectKBest(score_func=f_regression, k=min(k, X_clean.shape[1]))
        elif method == 'mutual_info':
            selector = SelectKBest(score_func=mutual_info_regression, k=min(k, X_clean.shape[1]))
        else:
            raise ValueError(f"Unsupported feature selection method: {method}")

        # Fit and transform
        X_selected = selector.fit_transform(X_clean, y_clean)

        # Get selected feature names
        selected_mask = selector.get_support()
        selected_features = X.columns[selected_mask].tolist()

        # Create DataFrame with selected features
        X_selected_df = pd.DataFrame(
            X_selected,
            columns=selected_features,
            index=X.index
        )

        # Store for future use
        self.selector = selector
        self.selected_features = selected_features

        logger.info(f"Selected {len(selected_features)} features")
        return X_selected_df, selected_features

    def get_feature_scores(self) -> Dict[str, float]:
        """Get feature importance scores from last selection."""

        if self.selector is None or self.selected_features is None:
            return {}

        scores = self.selector.scores_
        return dict(zip(self.selected_features, scores))


class FeatureEngineeringPipeline:
    """Main feature engineering pipeline coordinator."""

    def __init__(self):
        self.age_calculator = AgeAdjustmentCalculator()
        self.progression_calculator = LevelProgressionCalculator()
        self.rate_calculator = RateStatisticsCalculator()
        self.scaler = FeatureScalingPipeline()
        self.selector = FeatureSelector()

    def process_features(self, df: pd.DataFrame,
                        target_column: str = None,
                        scale_features: bool = True,
                        select_features: bool = True,
                        k_features: int = 50) -> Dict[str, Any]:
        """
        Execute complete feature engineering pipeline.

        Args:
            df: Input DataFrame
            target_column: Target variable column name
            scale_features: Whether to scale features
            select_features: Whether to perform feature selection
            k_features: Number of features to select

        Returns:
            Dictionary with processed data and metadata
        """
        logger.info("Starting comprehensive feature engineering pipeline")

        # Step 1: Age-adjusted metrics
        df_processed = self.age_calculator.calculate_age_adjusted_stats(df)

        # Step 2: Level progression metrics
        df_processed = self.progression_calculator.calculate_progression_metrics(df_processed)

        # Step 3: Rate statistics
        df_processed = self.rate_calculator.calculate_rate_statistics(df_processed)

        # Identify all feature columns (exclude ID and target columns)
        exclude_columns = ['mlb_id', 'date_recorded', 'created_at', 'updated_at']
        if target_column:
            exclude_columns.append(target_column)

        feature_columns = [col for col in df_processed.columns
                          if col not in exclude_columns and
                          pd.api.types.is_numeric_dtype(df_processed[col])]

        # Step 4: Feature scaling
        if scale_features:
            df_processed = self.scaler.fit_transform_features(
                df_processed, feature_columns, 'standard'
            )
            # Update feature columns to include scaled versions
            scaled_features = [f'{col}_scaled' for col in feature_columns
                             if f'{col}_scaled' in df_processed.columns]
            feature_columns.extend(scaled_features)

        # Step 5: Feature selection
        selected_features = feature_columns
        X_selected = None
        feature_scores = {}

        if select_features and target_column and target_column in df_processed.columns:
            X = df_processed[feature_columns]
            y = df_processed[target_column]

            X_selected, selected_features = self.selector.select_features(
                X, y, method='f_regression', k=k_features
            )
            feature_scores = self.selector.get_feature_scores()

        # Prepare results
        results = {
            'processed_data': df_processed,
            'feature_columns': feature_columns,
            'selected_features': selected_features,
            'feature_scores': feature_scores,
            'X_selected': X_selected,
            'pipeline_metadata': {
                'total_features_created': len(feature_columns),
                'features_selected': len(selected_features),
                'age_adjustments_applied': True,
                'progression_metrics_calculated': True,
                'rate_statistics_calculated': True,
                'features_scaled': scale_features,
                'feature_selection_applied': select_features
            }
        }

        logger.info(f"Feature engineering pipeline completed. "
                   f"Created {len(feature_columns)} features, "
                   f"selected {len(selected_features)} for training")

        return results