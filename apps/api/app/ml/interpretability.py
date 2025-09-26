"""
SHAP-based model interpretability and feature importance analysis.
Provides comprehensive model explanations and feature contribution insights.
"""

import logging
import numpy as np
import pandas as pd
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# SHAP imports
import shap
shap.initjs()

# ML model imports
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


class SHAPAnalyzer:
    """SHAP-based feature importance and model interpretability analyzer."""

    def __init__(self):
        self.explainer = None
        self.shap_values = None
        self.expected_value = None
        self.feature_names = None
        self.model_type = None
        self.analysis_results = {}

    def create_explainer(self, model, X_train: pd.DataFrame,
                        explainer_type: str = 'auto') -> None:
        """
        Create SHAP explainer for the given model.

        Args:
            model: Trained ML model
            X_train: Training data for background distribution
            explainer_type: Type of explainer ('auto', 'tree', 'linear', 'kernel')
        """
        logger.info(f"Creating SHAP explainer (type: {explainer_type})")

        self.feature_names = list(X_train.columns)
        self.model_type = type(model).__name__

        if explainer_type == 'auto':
            # Auto-detect explainer type based on model
            if isinstance(model, (xgb.XGBClassifier, xgb.XGBRegressor)):
                explainer_type = 'tree'
            elif isinstance(model, RandomForestClassifier):
                explainer_type = 'tree'
            elif isinstance(model, LogisticRegression):
                explainer_type = 'linear'
            else:
                explainer_type = 'kernel'

        # Create appropriate explainer
        if explainer_type == 'tree':
            self.explainer = shap.TreeExplainer(model)
        elif explainer_type == 'linear':
            self.explainer = shap.LinearExplainer(model, X_train)
        elif explainer_type == 'kernel':
            # Use a sample for kernel explainer to reduce computation time
            background = shap.sample(X_train, min(100, len(X_train)))
            self.explainer = shap.KernelExplainer(model.predict_proba, background)
        else:
            raise ValueError(f"Unsupported explainer type: {explainer_type}")

        logger.info(f"SHAP {explainer_type} explainer created successfully")

    def calculate_shap_values(self, X: pd.DataFrame,
                             max_samples: Optional[int] = None) -> np.ndarray:
        """
        Calculate SHAP values for the given dataset.

        Args:
            X: Input features
            max_samples: Maximum number of samples to analyze (for performance)

        Returns:
            SHAP values array
        """
        if self.explainer is None:
            raise ValueError("SHAP explainer must be created first")

        logger.info(f"Calculating SHAP values for {len(X)} samples")

        # Limit samples for performance if needed
        if max_samples and len(X) > max_samples:
            sample_indices = np.random.choice(len(X), max_samples, replace=False)
            X_sample = X.iloc[sample_indices]
        else:
            X_sample = X

        # Calculate SHAP values
        self.shap_values = self.explainer.shap_values(X_sample)

        # Handle binary classification case (XGBoost returns single array)
        if isinstance(self.shap_values, list) and len(self.shap_values) == 2:
            # Use positive class SHAP values for binary classification
            self.shap_values = self.shap_values[1]
        elif isinstance(self.shap_values, list) and len(self.shap_values) == 1:
            self.shap_values = self.shap_values[0]

        # Store expected value
        if hasattr(self.explainer, 'expected_value'):
            if isinstance(self.explainer.expected_value, (list, np.ndarray)):
                self.expected_value = self.explainer.expected_value[1] if len(self.explainer.expected_value) > 1 else self.explainer.expected_value[0]
            else:
                self.expected_value = self.explainer.expected_value
        else:
            self.expected_value = 0.0

        logger.info(f"SHAP values calculated for {len(X_sample)} samples")
        return self.shap_values

    def get_feature_importance_rankings(self) -> Dict[str, Any]:
        """
        Get feature importance rankings based on SHAP values.

        Returns:
            Dictionary with feature importance rankings and scores
        """
        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        logger.info("Calculating feature importance rankings")

        # Calculate mean absolute SHAP values for each feature
        mean_abs_shap = np.abs(self.shap_values).mean(axis=0)

        # Create importance DataFrame
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'mean_abs_shap': mean_abs_shap,
            'rank': range(1, len(self.feature_names) + 1)
        }).sort_values('mean_abs_shap', ascending=False).reset_index(drop=True)

        # Update ranks
        importance_df['rank'] = range(1, len(importance_df) + 1)

        # Calculate relative importance (percentage)
        total_importance = importance_df['mean_abs_shap'].sum()
        importance_df['relative_importance'] = (
            importance_df['mean_abs_shap'] / total_importance * 100
        )

        # Create results dictionary
        results = {
            'rankings': importance_df.to_dict('records'),
            'top_10_features': importance_df.head(10)['feature'].tolist(),
            'top_feature': importance_df.iloc[0]['feature'],
            'top_feature_importance': importance_df.iloc[0]['mean_abs_shap'],
            'cumulative_importance_top_10': importance_df.head(10)['relative_importance'].sum(),
            'total_features': len(self.feature_names),
            'analysis_timestamp': datetime.now().isoformat()
        }

        self.analysis_results['feature_importance'] = results

        logger.info(f"Feature importance calculated. Top feature: {results['top_feature']} "
                   f"(importance: {results['top_feature_importance']:.4f})")

        return results

    def analyze_individual_predictions(self, X: pd.DataFrame,
                                     sample_indices: Optional[List[int]] = None,
                                     top_n_features: int = 10) -> Dict[str, Any]:
        """
        Analyze SHAP explanations for individual predictions.

        Args:
            X: Input features
            sample_indices: Specific sample indices to analyze (if None, analyze all)
            top_n_features: Number of top features to include in analysis

        Returns:
            Dictionary with individual prediction explanations
        """
        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        logger.info("Analyzing individual prediction explanations")

        if sample_indices is None:
            sample_indices = list(range(len(self.shap_values)))

        individual_explanations = []

        for idx in sample_indices:
            if idx >= len(self.shap_values):
                continue

            sample_shap = self.shap_values[idx]
            sample_features = X.iloc[idx] if idx < len(X) else None

            # Get top contributing features for this prediction
            feature_contributions = pd.DataFrame({
                'feature': self.feature_names,
                'shap_value': sample_shap,
                'abs_shap_value': np.abs(sample_shap)
            }).sort_values('abs_shap_value', ascending=False)

            top_features = feature_contributions.head(top_n_features)

            explanation = {
                'sample_index': idx,
                'expected_value': self.expected_value,
                'prediction_score': self.expected_value + sample_shap.sum(),
                'total_shap_contribution': sample_shap.sum(),
                'top_positive_features': top_features[top_features['shap_value'] > 0][['feature', 'shap_value']].to_dict('records'),
                'top_negative_features': top_features[top_features['shap_value'] < 0][['feature', 'shap_value']].to_dict('records'),
                'feature_values': sample_features.to_dict() if sample_features is not None else {}
            }

            individual_explanations.append(explanation)

        results = {
            'individual_explanations': individual_explanations,
            'total_samples_analyzed': len(individual_explanations),
            'analysis_timestamp': datetime.now().isoformat()
        }

        self.analysis_results['individual_predictions'] = results

        logger.info(f"Individual prediction analysis completed for {len(individual_explanations)} samples")
        return results

    def generate_global_feature_insights(self) -> Dict[str, Any]:
        """
        Generate global insights about feature contributions across all predictions.

        Returns:
            Dictionary with global feature insights
        """
        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        logger.info("Generating global feature insights")

        # Feature statistics
        feature_stats = {}
        for i, feature in enumerate(self.feature_names):
            feature_shap = self.shap_values[:, i]
            feature_stats[feature] = {
                'mean_shap': float(np.mean(feature_shap)),
                'std_shap': float(np.std(feature_shap)),
                'mean_abs_shap': float(np.mean(np.abs(feature_shap))),
                'max_shap': float(np.max(feature_shap)),
                'min_shap': float(np.min(feature_shap)),
                'positive_impact_frequency': float(np.mean(feature_shap > 0)),
                'negative_impact_frequency': float(np.mean(feature_shap < 0)),
                'high_impact_frequency': float(np.mean(np.abs(feature_shap) > np.percentile(np.abs(feature_shap), 75)))
            }

        # Identify feature patterns
        patterns = {
            'most_consistently_positive': max(feature_stats.items(),
                                            key=lambda x: x[1]['positive_impact_frequency'])[0],
            'most_consistently_negative': max(feature_stats.items(),
                                            key=lambda x: x[1]['negative_impact_frequency'])[0],
            'highest_variability': max(feature_stats.items(),
                                     key=lambda x: x[1]['std_shap'])[0],
            'most_impactful_overall': max(feature_stats.items(),
                                        key=lambda x: x[1]['mean_abs_shap'])[0]
        }

        # Feature interaction insights
        interaction_insights = self._analyze_feature_interactions()

        results = {
            'feature_statistics': feature_stats,
            'feature_patterns': patterns,
            'interaction_insights': interaction_insights,
            'model_complexity': {
                'active_features': sum(1 for stats in feature_stats.values()
                                     if stats['mean_abs_shap'] > 0.001),
                'dominant_features': sum(1 for stats in feature_stats.values()
                                       if stats['mean_abs_shap'] > np.mean([s['mean_abs_shap']
                                                                          for s in feature_stats.values()])),
                'total_features': len(self.feature_names)
            },
            'analysis_timestamp': datetime.now().isoformat()
        }

        self.analysis_results['global_insights'] = results

        logger.info("Global feature insights generated successfully")
        return results

    def _analyze_feature_interactions(self) -> Dict[str, Any]:
        """Analyze feature interactions using SHAP values."""

        # Calculate feature correlation in SHAP space
        shap_df = pd.DataFrame(self.shap_values, columns=self.feature_names)
        shap_correlation = shap_df.corr()

        # Find high-correlation feature pairs
        high_correlation_pairs = []
        for i in range(len(self.feature_names)):
            for j in range(i + 1, len(self.feature_names)):
                corr_value = shap_correlation.iloc[i, j]
                if abs(corr_value) > 0.5:  # Threshold for significant correlation
                    high_correlation_pairs.append({
                        'feature_1': self.feature_names[i],
                        'feature_2': self.feature_names[j],
                        'correlation': float(corr_value)
                    })

        return {
            'high_correlation_pairs': high_correlation_pairs,
            'max_correlation': float(shap_correlation.abs().max().max()),
            'mean_correlation': float(shap_correlation.abs().mean().mean())
        }

    def create_feature_importance_plot(self, top_n: int = 20,
                                     save_path: Optional[str] = None) -> plt.Figure:
        """
        Create feature importance visualization.

        Args:
            top_n: Number of top features to display
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        # Get feature importance rankings
        importance_results = self.get_feature_importance_rankings()
        importance_df = pd.DataFrame(importance_results['rankings']).head(top_n)

        # Create plot
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

        # Bar plot of feature importance
        bars = ax1.barh(range(len(importance_df)), importance_df['mean_abs_shap'])
        ax1.set_yticks(range(len(importance_df)))
        ax1.set_yticklabels(importance_df['feature'])
        ax1.set_xlabel('Mean |SHAP Value|')
        ax1.set_title(f'Top {top_n} Feature Importance (SHAP)')
        ax1.invert_yaxis()

        # Color bars by importance
        colors = plt.cm.viridis(importance_df['mean_abs_shap'] / importance_df['mean_abs_shap'].max())
        for bar, color in zip(bars, colors):
            bar.set_color(color)

        # Cumulative importance plot
        ax2.plot(range(1, len(importance_df) + 1),
                importance_df['relative_importance'].cumsum(),
                marker='o', linewidth=2, markersize=6)
        ax2.axhline(y=80, color='red', linestyle='--', alpha=0.7, label='80% threshold')
        ax2.set_xlabel('Number of Features')
        ax2.set_ylabel('Cumulative Importance (%)')
        ax2.set_title('Cumulative Feature Importance')
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Feature importance plot saved to {save_path}")

        return fig

    def create_shap_summary_plot(self, X: pd.DataFrame,
                                max_display: int = 20,
                                save_path: Optional[str] = None) -> plt.Figure:
        """
        Create SHAP summary plot showing feature effects.

        Args:
            X: Feature data for color mapping
            max_display: Maximum number of features to display
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        fig, ax = plt.subplots(figsize=(12, 8))

        # Create SHAP summary plot
        shap.summary_plot(
            self.shap_values,
            X,
            feature_names=self.feature_names,
            max_display=max_display,
            show=False
        )

        plt.title('SHAP Summary Plot - Feature Impact on Model Output')

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"SHAP summary plot saved to {save_path}")

        return fig

    def create_waterfall_plot(self, X: pd.DataFrame, sample_index: int,
                             save_path: Optional[str] = None) -> plt.Figure:
        """
        Create SHAP waterfall plot for individual prediction explanation.

        Args:
            X: Feature data
            sample_index: Index of sample to explain
            save_path: Path to save the plot

        Returns:
            matplotlib Figure object
        """
        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        if sample_index >= len(self.shap_values):
            raise ValueError(f"Sample index {sample_index} out of range")

        fig, ax = plt.subplots(figsize=(12, 8))

        # Create waterfall plot
        shap.waterfall_plot(
            shap.Explanation(
                values=self.shap_values[sample_index],
                base_values=self.expected_value,
                data=X.iloc[sample_index] if sample_index < len(X) else None,
                feature_names=self.feature_names
            ),
            show=False
        )

        plt.title(f'SHAP Waterfall Plot - Sample {sample_index}')

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"SHAP waterfall plot saved to {save_path}")

        return fig

    def export_shap_analysis(self, filepath: str) -> None:
        """
        Export complete SHAP analysis results to JSON.

        Args:
            filepath: Path to save JSON file
        """
        if not self.analysis_results:
            logger.warning("No analysis results to export")
            return

        export_data = {
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'expected_value': float(self.expected_value) if self.expected_value is not None else None,
            'analysis_results': self.analysis_results,
            'export_timestamp': datetime.now().isoformat()
        }

        # Convert numpy types for JSON serialization
        def convert_numpy(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        def process_dict(d):
            if isinstance(d, dict):
                return {k: process_dict(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [process_dict(item) for item in d]
            else:
                return convert_numpy(d)

        processed_data = process_dict(export_data)

        with open(filepath, 'w') as f:
            json.dump(processed_data, f, indent=2)

        logger.info(f"SHAP analysis exported to {filepath}")

    def get_feature_contribution_summary(self, feature_name: str) -> Dict[str, Any]:
        """
        Get detailed summary for a specific feature's contributions.

        Args:
            feature_name: Name of the feature to analyze

        Returns:
            Dictionary with feature contribution summary
        """
        if feature_name not in self.feature_names:
            raise ValueError(f"Feature '{feature_name}' not found in model features")

        if self.shap_values is None:
            raise ValueError("SHAP values must be calculated first")

        feature_idx = self.feature_names.index(feature_name)
        feature_shap = self.shap_values[:, feature_idx]

        summary = {
            'feature_name': feature_name,
            'statistics': {
                'mean_contribution': float(np.mean(feature_shap)),
                'std_contribution': float(np.std(feature_shap)),
                'min_contribution': float(np.min(feature_shap)),
                'max_contribution': float(np.max(feature_shap)),
                'median_contribution': float(np.median(feature_shap)),
                'percentile_25': float(np.percentile(feature_shap, 25)),
                'percentile_75': float(np.percentile(feature_shap, 75))
            },
            'impact_analysis': {
                'positive_contributions': int(np.sum(feature_shap > 0)),
                'negative_contributions': int(np.sum(feature_shap < 0)),
                'neutral_contributions': int(np.sum(feature_shap == 0)),
                'high_impact_threshold': float(np.percentile(np.abs(feature_shap), 90)),
                'high_impact_count': int(np.sum(np.abs(feature_shap) > np.percentile(np.abs(feature_shap), 90)))
            },
            'rank_info': self._get_feature_rank(feature_name),
            'analysis_timestamp': datetime.now().isoformat()
        }

        return summary

    def _get_feature_rank(self, feature_name: str) -> Dict[str, Any]:
        """Get ranking information for a specific feature."""
        if 'feature_importance' in self.analysis_results:
            rankings = self.analysis_results['feature_importance']['rankings']
            for rank_info in rankings:
                if rank_info['feature'] == feature_name:
                    return {
                        'rank': rank_info['rank'],
                        'relative_importance': rank_info['relative_importance'],
                        'mean_abs_shap': rank_info['mean_abs_shap']
                    }
        return {'rank': None, 'relative_importance': None, 'mean_abs_shap': None}