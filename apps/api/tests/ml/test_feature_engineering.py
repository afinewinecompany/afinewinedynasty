"""
Unit tests for feature engineering pipeline.
Tests age adjustments, rate statistics, level progression, scaling, and feature selection.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.ml.feature_engineering import (
    AgeAdjustmentCalculator,
    LevelProgressionCalculator,
    RateStatisticsCalculator,
    FeatureScalingPipeline,
    FeatureSelector,
    FeatureEngineeringPipeline
)


class TestAgeAdjustmentCalculator:
    """Test age adjustment calculations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = AgeAdjustmentCalculator()
        self.sample_data = pd.DataFrame({
            'age': [18, 20, 22, 24, 26],
            'level': ['Low-A', 'High-A', 'Double-A', 'Triple-A', 'MLB'],
            'batting_avg': [0.250, 0.275, 0.300, 0.285, 0.270],
            'era': [4.50, 4.20, 3.80, 3.95, 4.10]
        })

    def test_level_age_baselines_defined(self):
        """Test that age baselines are properly defined."""
        assert 'MLB' in self.calculator.level_age_baselines
        assert 'Triple-A' in self.calculator.level_age_baselines
        assert 'Double-A' in self.calculator.level_age_baselines
        assert self.calculator.level_age_baselines['MLB'] > self.calculator.level_age_baselines['Triple-A']

    def test_age_adjusted_stats_calculation(self):
        """Test age-adjusted statistics calculation."""
        result = self.calculator.calculate_age_adjusted_stats(self.sample_data)

        # Check that age-adjusted columns are created
        assert 'age_differential' in result.columns
        assert 'age_adjustment_factor' in result.columns
        assert 'batting_avg_age_adj' in result.columns
        assert 'era_age_adj' in result.columns

        # Check that adjustments are reasonable
        assert all(result['age_adjustment_factor'] > 0)
        assert len(result) == len(self.sample_data)

    def test_young_player_bonus(self):
        """Test that younger players get performance bonus."""
        young_player_data = pd.DataFrame({
            'age': [18],
            'level': ['Low-A'],
            'batting_avg': [0.250]
        })

        result = self.calculator.calculate_age_adjusted_stats(young_player_data)

        # Young player should have adjustment factor > 1 (bonus)
        assert result['age_adjustment_factor'].iloc[0] > 1.0
        assert result['batting_avg_age_adj'].iloc[0] > result['batting_avg'].iloc[0]

    def test_old_player_penalty(self):
        """Test that older players get performance penalty."""
        old_player_data = pd.DataFrame({
            'age': [28],
            'level': ['Low-A'],
            'batting_avg': [0.250]
        })

        result = self.calculator.calculate_age_adjusted_stats(old_player_data)

        # Old player should have adjustment factor < 1 (penalty)
        assert result['age_adjustment_factor'].iloc[0] < 1.0
        assert result['batting_avg_age_adj'].iloc[0] < result['batting_avg'].iloc[0]

    def test_missing_level_handling(self):
        """Test handling of missing level data."""
        data_with_missing = pd.DataFrame({
            'age': [20, 22],
            'level': ['High-A', None],
            'batting_avg': [0.275, 0.300]
        })

        result = self.calculator.calculate_age_adjusted_stats(data_with_missing)

        # Should not raise error and should use default baseline
        assert len(result) == 2
        assert 'age_adjustment_factor' in result.columns


class TestLevelProgressionCalculator:
    """Test level progression calculations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = LevelProgressionCalculator()
        self.sample_data = pd.DataFrame({
            'mlb_id': [1, 1, 1, 2, 2],
            'level': ['Low-A', 'High-A', 'Double-A', 'Low-A', 'Low-A'],
            'date_recorded': [
                datetime(2020, 1, 1),
                datetime(2020, 6, 1),
                datetime(2021, 1, 1),
                datetime(2020, 1, 1),
                datetime(2020, 6, 1)
            ]
        })

    def test_level_hierarchy_defined(self):
        """Test that level hierarchy is properly defined."""
        assert 'MLB' in self.calculator.level_hierarchy
        assert 'Triple-A' in self.calculator.level_hierarchy
        assert self.calculator.level_hierarchy['MLB'] > self.calculator.level_hierarchy['Triple-A']

    def test_progression_metrics_calculation(self):
        """Test progression metrics calculation."""
        result = self.calculator.calculate_progression_metrics(self.sample_data)

        # Check that progression metrics are added
        assert 'levels_played_count' in result.columns
        assert 'max_level_reached' in result.columns
        assert 'advancement_rate_per_year' in result.columns
        assert 'regression_count' in result.columns

        # Check specific values for player 1 (progressed)
        player1_data = result[result['mlb_id'] == 1].iloc[0]
        assert player1_data['levels_played_count'] == 3  # Low-A, High-A, Double-A
        assert player1_data['level_advancement_total'] > 0

    def test_single_player_progression(self):
        """Test progression calculation for single player."""
        single_player_data = self.sample_data[self.sample_data['mlb_id'] == 1].copy()

        # Test internal method
        player_metrics = self.calculator._calculate_player_progression(single_player_data)

        assert player_metrics['mlb_id'] == 1
        assert player_metrics['levels_played_count'] == 3
        assert player_metrics['level_advancement_total'] == 2  # From Low-A (4) to Double-A (6)
        assert player_metrics['advancement_rate_per_year'] > 0

    def test_regression_detection(self):
        """Test regression detection in level progression."""
        regression_data = pd.DataFrame({
            'mlb_id': [3],
            'level': ['Double-A', 'High-A'],  # Regression
            'level_numeric': [6, 5],
            'date_recorded': [datetime(2020, 1, 1), datetime(2020, 6, 1)]
        })

        player_metrics = self.calculator._calculate_player_progression(regression_data)
        assert player_metrics['regression_count'] == 1


class TestRateStatisticsCalculator:
    """Test rate statistics calculations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.calculator = RateStatisticsCalculator()
        self.sample_data = pd.DataFrame({
            'hits': [150, 120],
            'at_bats': [500, 400],
            'plate_appearances': [550, 450],
            'walks': [50, 40],
            'strikeouts': [100, 80],
            'home_runs': [20, 15],
            'games_played': [140, 120],
            'innings_pitched': [180, 160],
            'hits_allowed': [160, 140],
            'walks': [60, 50],
            'home_runs_allowed': [18, 16]
        })

    def test_offensive_rate_stats(self):
        """Test offensive rate statistics calculation."""
        result = self.calculator.calculate_rate_statistics(self.sample_data)

        # Check that rate stats are calculated
        assert 'contact_rate' in result.columns
        assert 'walk_rate' in result.columns
        assert 'strikeout_rate' in result.columns
        assert 'power_rate' in result.columns

        # Check calculations
        assert result['contact_rate'].iloc[0] == pytest.approx(150/500, rel=1e-3)
        assert result['walk_rate'].iloc[0] == pytest.approx(50/550, rel=1e-3)

    def test_pitching_rate_stats(self):
        """Test pitching rate statistics calculation."""
        result = self.calculator.calculate_rate_statistics(self.sample_data)

        # Check pitching rate stats
        assert 'k_per_9' in result.columns
        assert 'bb_per_9' in result.columns
        assert 'hr_per_9' in result.columns
        assert 'hits_per_9' in result.columns

        # Check calculations (strikeouts per 9 innings)
        expected_k_per_9 = (100 * 9) / 180
        assert result['k_per_9'].iloc[0] == pytest.approx(expected_k_per_9, rel=1e-3)

    def test_per_game_rates(self):
        """Test per-game rate calculations."""
        result = self.calculator.calculate_rate_statistics(self.sample_data)

        assert 'hits_per_game' in result.columns
        assert 'rbi_per_game' in result.columns
        assert 'runs_per_game' in result.columns

    def test_advanced_metrics(self):
        """Test advanced rate metrics calculation."""
        # Add required columns for advanced metrics
        data_with_advanced = self.sample_data.copy()
        data_with_advanced['slugging_pct'] = [0.450, 0.425]
        data_with_advanced['batting_avg'] = [0.300, 0.300]

        result = self.calculator.calculate_rate_statistics(data_with_advanced)

        # Check ISO calculation
        assert 'iso' in result.columns
        assert result['iso'].iloc[0] == pytest.approx(0.450 - 0.300, rel=1e-3)

    def test_zero_division_handling(self):
        """Test handling of zero division cases."""
        zero_data = pd.DataFrame({
            'hits': [0],
            'at_bats': [0],
            'plate_appearances': [0],
            'walks': [0]
        })

        result = self.calculator.calculate_rate_statistics(zero_data)

        # Should not raise errors and should handle NaN appropriately
        assert len(result) == 1


class TestFeatureScalingPipeline:
    """Test feature scaling pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.scaler = FeatureScalingPipeline()
        self.sample_data = pd.DataFrame({
            'feature1': [1, 2, 3, 4, 5],
            'feature2': [10, 20, 30, 40, 50],
            'feature3': [0.1, 0.2, 0.3, 0.4, 0.5],
            'non_numeric': ['a', 'b', 'c', 'd', 'e']
        })

    def test_standard_scaling(self):
        """Test standard scaling."""
        features = ['feature1', 'feature2', 'feature3']
        result = self.scaler.fit_transform_features(self.sample_data, features, 'standard')

        # Check that scaled columns are created
        assert 'feature1_scaled' in result.columns
        assert 'feature2_scaled' in result.columns
        assert 'feature3_scaled' in result.columns

        # Check that scaling is approximately correct (mean ~0, std ~1)
        assert abs(result['feature1_scaled'].mean()) < 1e-10
        assert abs(result['feature1_scaled'].std() - 1.0) < 1e-10

    def test_minmax_scaling(self):
        """Test min-max scaling."""
        features = ['feature1', 'feature2']
        result = self.scaler.fit_transform_features(self.sample_data, features, 'minmax')

        # Check that values are scaled to [0, 1] range
        assert result['feature1_scaled'].min() == pytest.approx(0.0, abs=1e-10)
        assert result['feature1_scaled'].max() == pytest.approx(1.0, abs=1e-10)

    def test_non_numeric_feature_filtering(self):
        """Test that non-numeric features are filtered out."""
        features = ['feature1', 'non_numeric']
        result = self.scaler.fit_transform_features(self.sample_data, features, 'standard')

        # Only numeric feature should be scaled
        assert 'feature1_scaled' in result.columns
        assert 'non_numeric_scaled' not in result.columns

    def test_transform_with_fitted_scaler(self):
        """Test transform using previously fitted scaler."""
        features = ['feature1', 'feature2']

        # Fit scaler
        self.scaler.fit_transform_features(self.sample_data, features, 'standard')

        # Transform new data
        new_data = pd.DataFrame({
            'feature1': [6, 7],
            'feature2': [60, 70]
        })

        result = self.scaler.transform_features(new_data, 'standard')

        assert 'feature1_scaled' in result.columns
        assert 'feature2_scaled' in result.columns


class TestFeatureSelector:
    """Test feature selection."""

    def setup_method(self):
        """Set up test fixtures."""
        self.selector = FeatureSelector()

        # Create data with clear relationships
        np.random.seed(42)
        n_samples = 100

        # Create features with different relationships to target
        self.X = pd.DataFrame({
            'important_feature1': np.random.randn(n_samples),
            'important_feature2': np.random.randn(n_samples),
            'noise_feature1': np.random.randn(n_samples),
            'noise_feature2': np.random.randn(n_samples),
        })

        # Create target with clear relationship to important features
        self.y = (
            2 * self.X['important_feature1'] +
            1.5 * self.X['important_feature2'] +
            0.1 * np.random.randn(n_samples)
        )

    def test_feature_selection_f_regression(self):
        """Test feature selection using f_regression."""
        X_selected, selected_features = self.selector.select_features(
            self.X, self.y, method='f_regression', k=2
        )

        assert len(selected_features) == 2
        assert X_selected.shape[1] == 2
        assert X_selected.shape[0] == len(self.X)

        # Important features should be selected
        assert any('important' in feature for feature in selected_features)

    def test_feature_selection_mutual_info(self):
        """Test feature selection using mutual information."""
        X_selected, selected_features = self.selector.select_features(
            self.X, self.y, method='mutual_info', k=2
        )

        assert len(selected_features) == 2
        assert X_selected.shape[1] == 2

    def test_get_feature_scores(self):
        """Test getting feature scores."""
        self.selector.select_features(self.X, self.y, method='f_regression', k=2)
        scores = self.selector.get_feature_scores()

        assert len(scores) == 2  # k=2 features selected
        assert all(isinstance(score, (int, float)) for score in scores.values())

    def test_k_larger_than_features(self):
        """Test when k is larger than number of features."""
        X_selected, selected_features = self.selector.select_features(
            self.X, self.y, method='f_regression', k=10
        )

        # Should select all available features
        assert len(selected_features) == len(self.X.columns)


class TestFeatureEngineeringPipeline:
    """Test complete feature engineering pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.pipeline = FeatureEngineeringPipeline()
        self.sample_data = pd.DataFrame({
            'mlb_id': [1, 1, 2, 2],
            'age': [20, 21, 22, 23],
            'level': ['Low-A', 'High-A', 'Double-A', 'Triple-A'],
            'date_recorded': [
                datetime(2020, 1, 1),
                datetime(2020, 6, 1),
                datetime(2021, 1, 1),
                datetime(2021, 6, 1)
            ],
            'batting_avg': [0.250, 0.275, 0.300, 0.285],
            'hits': [100, 110, 120, 115],
            'at_bats': [400, 400, 400, 400],
            'target_variable': [0, 0, 1, 1]
        })

    def test_complete_pipeline_processing(self):
        """Test complete pipeline execution."""
        results = self.pipeline.process_features(
            self.sample_data,
            target_column='target_variable',
            scale_features=True,
            select_features=True,
            k_features=10
        )

        # Check that all expected components are present
        assert 'processed_data' in results
        assert 'feature_columns' in results
        assert 'selected_features' in results
        assert 'feature_scores' in results
        assert 'pipeline_metadata' in results

        # Check metadata
        metadata = results['pipeline_metadata']
        assert metadata['age_adjustments_applied'] is True
        assert metadata['progression_metrics_calculated'] is True
        assert metadata['rate_statistics_calculated'] is True
        assert metadata['features_scaled'] is True
        assert metadata['feature_selection_applied'] is True

    def test_pipeline_without_scaling(self):
        """Test pipeline without feature scaling."""
        results = self.pipeline.process_features(
            self.sample_data,
            scale_features=False,
            select_features=False
        )

        metadata = results['pipeline_metadata']
        assert metadata['features_scaled'] is False
        assert metadata['feature_selection_applied'] is False

    def test_pipeline_with_missing_target(self):
        """Test pipeline when target column is missing."""
        results = self.pipeline.process_features(
            self.sample_data,
            target_column='nonexistent_column',
            select_features=True
        )

        # Should still process other steps
        assert 'processed_data' in results
        metadata = results['pipeline_metadata']
        assert metadata['feature_selection_applied'] is False

    def test_pipeline_feature_creation(self):
        """Test that pipeline creates expected features."""
        results = self.pipeline.process_features(self.sample_data)
        processed_data = results['processed_data']

        # Check for age-adjusted features
        age_adj_features = [col for col in processed_data.columns if '_age_adj' in col]
        assert len(age_adj_features) > 0

        # Check for progression features
        progression_features = [col for col in processed_data.columns
                              if 'progression' in col or 'advancement' in col or 'level' in col]
        assert len(progression_features) > 0

        # Check for rate statistics
        rate_features = [col for col in processed_data.columns if '_rate' in col or '_per_' in col]
        assert len(rate_features) > 0


# Integration tests
class TestFeatureEngineeringIntegration:
    """Integration tests for the complete feature engineering system."""

    def test_end_to_end_pipeline(self):
        """Test end-to-end feature engineering pipeline."""
        # Create realistic prospect data
        np.random.seed(42)
        n_samples = 200

        data = pd.DataFrame({
            'mlb_id': np.repeat(range(50), 4),
            'age': np.random.randint(18, 26, n_samples),
            'level': np.random.choice(['Low-A', 'High-A', 'Double-A', 'Triple-A'], n_samples),
            'date_recorded': [datetime(2020, 1, 1) + timedelta(days=i*30) for i in range(n_samples)],
            'batting_avg': np.random.uniform(0.200, 0.350, n_samples),
            'on_base_pct': np.random.uniform(0.250, 0.450, n_samples),
            'slugging_pct': np.random.uniform(0.300, 0.600, n_samples),
            'hits': np.random.randint(50, 150, n_samples),
            'at_bats': np.random.randint(300, 500, n_samples),
            'plate_appearances': np.random.randint(350, 550, n_samples),
            'walks': np.random.randint(20, 80, n_samples),
            'strikeouts': np.random.randint(50, 150, n_samples),
            'games_played': np.random.randint(100, 140, n_samples),
            'mlb_success': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])
        })

        pipeline = FeatureEngineeringPipeline()
        results = pipeline.process_features(
            data,
            target_column='mlb_success',
            scale_features=True,
            select_features=True,
            k_features=20
        )

        # Verify pipeline execution
        assert len(results['processed_data']) == n_samples
        assert len(results['selected_features']) <= 20
        assert results['pipeline_metadata']['total_features_created'] > 10

        # Verify no data leakage (target not in features)
        assert 'mlb_success' not in results['selected_features']

    def test_pipeline_performance(self):
        """Test pipeline performance with larger dataset."""
        # Create larger dataset
        n_samples = 1000
        np.random.seed(42)

        large_data = pd.DataFrame({
            'mlb_id': np.repeat(range(250), 4),
            'age': np.random.randint(18, 30, n_samples),
            'level': np.random.choice(['Low-A', 'High-A', 'Double-A', 'Triple-A', 'MLB'], n_samples),
            'date_recorded': [datetime(2018, 1, 1) + timedelta(days=i) for i in range(n_samples)],
            **{f'stat_{i}': np.random.randn(n_samples) for i in range(20)},
            'target': np.random.choice([0, 1], n_samples)
        })

        pipeline = FeatureEngineeringPipeline()

        # Time the pipeline execution
        start_time = datetime.now()
        results = pipeline.process_features(large_data, target_column='target')
        end_time = datetime.now()

        execution_time = (end_time - start_time).total_seconds()

        # Should complete in reasonable time (adjust threshold as needed)
        assert execution_time < 30  # 30 seconds threshold
        assert len(results['processed_data']) == n_samples


if __name__ == "__main__":
    pytest.main([__file__])