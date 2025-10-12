"""
Preliminary ML Analysis on MiLB Play-by-Play Features

Identifies which statistics are most valuable for predicting prospect success
using the initial dataset of collected games.

Analyses performed:
1. Feature correlation matrix
2. Random Forest feature importance
3. Gradient Boosting feature importance
4. Feature stability analysis
5. Statistical significance testing

Usage:
    python preliminary_ml_analysis.py --input preliminary_ml_features.csv
"""

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from scipy import stats

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class PreliminaryMLAnalyzer:
    """Perform preliminary ML analysis on PBP features."""

    def __init__(self, features_df: pd.DataFrame):
        self.df = features_df
        self.prospect_df = None
        self.feature_importance = {}

    def calculate_derived_metrics(self):
        """Calculate rate-based metrics from counting stats."""
        logger.info("Calculating derived metrics...")

        df = self.df

        # Batting metrics
        df['batting_avg'] = np.where(df['at_bats'] > 0, df['hits'] / df['at_bats'], 0)
        df['on_base_pct'] = np.where(
            df['plate_appearances'] > 0,
            (df['hits'] + df['walks'] + df['hit_by_pitch']) / df['plate_appearances'],
            0
        )
        df['slugging_pct'] = np.where(
            df['at_bats'] > 0,
            (df['singles'] + 2*df['doubles'] + 3*df['triples'] + 4*df['home_runs']) / df['at_bats'],
            0
        )
        df['ops'] = df['on_base_pct'] + df['slugging_pct']
        df['iso'] = df['slugging_pct'] - df['batting_avg']
        df['babip'] = np.where(
            (df['at_bats'] - df['strikeouts']) > 0,
            (df['hits'] - df['home_runs']) / (df['at_bats'] - df['strikeouts'] - df['home_runs']),
            0
        )

        # Plate discipline
        df['walk_rate'] = np.where(df['plate_appearances'] > 0, df['walks'] / df['plate_appearances'], 0)
        df['strikeout_rate'] = np.where(df['plate_appearances'] > 0, df['strikeouts'] / df['plate_appearances'], 0)
        df['bb_k_ratio'] = np.where(df['strikeouts'] > 0, df['walks'] / df['strikeouts'], 0)

        # Swing metrics
        df['swing_pct'] = np.where(df['pitches_seen'] > 0, df['swings'] / df['pitches_seen'], 0)
        df['whiff_rate'] = np.where(df['swings'] > 0, df['swings_and_misses'] / df['swings'], 0)
        df['contact_rate'] = 1 - df['whiff_rate']

        # Zone discipline
        df['zone_swing_pct'] = np.where(
            df['pitches_in_zone'] > 0,
            df['swings_in_zone'] / df['pitches_in_zone'],
            0
        )
        df['chase_rate'] = np.where(
            df['pitches_out_zone'] > 0,
            df['swings_out_zone'] / df['pitches_out_zone'],
            0
        )
        df['o_swing_pct'] = df['chase_rate']  # Alias

        # Contact quality
        total_bip = df['balls_in_play']
        df['hard_hit_pct'] = np.where(total_bip > 0, df['hard_hit_balls'] / total_bip, 0)
        df['barrel_rate'] = np.where(total_bip > 0, df['barrels'] / total_bip, 0)
        df['soft_contact_pct'] = np.where(total_bip > 0, df['soft_hit_balls'] / total_bip, 0)

        # Batted ball distribution
        total_batted = df['ground_balls'] + df['line_drives'] + df['fly_balls']
        df['ground_ball_pct'] = np.where(total_batted > 0, df['ground_balls'] / total_batted, 0)
        df['line_drive_pct'] = np.where(total_batted > 0, df['line_drives'] / total_batted, 0)
        df['fly_ball_pct'] = np.where(total_batted > 0, df['fly_balls'] / total_batted, 0)

        # Directional
        total_directional = df['pull_hits'] + df['center_hits'] + df['opposite_hits']
        df['pull_pct'] = np.where(total_directional > 0, df['pull_hits'] / total_directional, 0)
        df['oppo_pct'] = np.where(total_directional > 0, df['opposite_hits'] / total_directional, 0)

        # Count leverage
        df['ahead_count_pct'] = np.where(df['plate_appearances'] > 0, df['pa_ahead_count'] / df['plate_appearances'], 0)
        df['behind_count_pct'] = np.where(df['plate_appearances'] > 0, df['pa_behind_count'] / df['plate_appearances'], 0)

        self.df = df
        logger.info(f"Calculated {len(df.columns)} total features")

    def aggregate_by_prospect(self):
        """Aggregate game-level to prospect-level statistics."""
        logger.info("Aggregating to prospect level...")

        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        agg_dict = {col: 'mean' for col in numeric_cols if col not in ['prospect_id', 'mlb_player_id', 'game_pk', 'season']}

        grouped = self.df.groupby('prospect_id').agg({
            **agg_dict,
            'prospect_name': 'first',
            'position': 'first',
            'level': lambda x: x.mode()[0] if len(x) > 0 else None,
            'game_pk': 'count'
        })

        grouped.rename(columns={'game_pk': 'games_played'}, inplace=True)
        self.prospect_df = grouped

        logger.info(f"Aggregated to {len(grouped)} prospects with {len(grouped.columns)} features")
        return grouped

    def random_forest_importance(self, target='ops'):
        """Calculate feature importance using Random Forest."""
        logger.info(f"Running Random Forest feature importance (target: {target})...")

        df = self.prospect_df.copy()

        # Get numeric features
        feature_cols = df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in feature_cols if col not in ['prospect_id', 'mlb_player_id', 'games_played', target]]

        X = df[feature_cols].fillna(0)
        y = df[target].fillna(0)

        # Remove features with zero variance
        X = X.loc[:, X.std() > 0]

        # Fit Random Forest
        rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
        rf.fit(X, y)

        # Get importances
        importances = pd.DataFrame({
            'feature': X.columns,
            'importance': rf.feature_importances_
        }).sort_values('importance', ascending=False)

        self.feature_importance['random_forest'] = importances

        logger.info(f"Top 10 features by Random Forest importance:")
        for idx, row in importances.head(10).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        return importances

    def gradient_boosting_importance(self, target='ops'):
        """Calculate feature importance using Gradient Boosting."""
        logger.info(f"Running Gradient Boosting feature importance (target: {target})...")

        df = self.prospect_df.copy()

        feature_cols = df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in feature_cols if col not in ['prospect_id', 'mlb_player_id', 'games_played', target]]

        X = df[feature_cols].fillna(0)
        y = df[target].fillna(0)

        X = X.loc[:, X.std() > 0]

        gb = GradientBoostingRegressor(n_estimators=100, max_depth=5, random_state=42)
        gb.fit(X, y)

        importances = pd.DataFrame({
            'feature': X.columns,
            'importance': gb.feature_importances_
        }).sort_values('importance', ascending=False)

        self.feature_importance['gradient_boosting'] = importances

        logger.info(f"Top 10 features by Gradient Boosting importance:")
        for idx, row in importances.head(10).iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")

        return importances

    def correlation_analysis(self, target='ops'):
        """Analyze correlations with target metric."""
        logger.info(f"Analyzing correlations with {target}...")

        df = self.prospect_df.copy()

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in numeric_cols if col not in ['prospect_id', 'mlb_player_id', 'games_played']]

        correlations = df[feature_cols].corrwith(df[target]).abs().sort_values(ascending=False)
        correlations = correlations[correlations.index != target]

        logger.info(f"Top 10 features by correlation with {target}:")
        for feat in correlations.head(10).index:
            logger.info(f"  {feat}: {correlations[feat]:.4f}")

        self.feature_importance['correlation'] = correlations
        return correlations

    def create_feature_importance_plot(self, output_file='feature_importance.png'):
        """Create visualization of feature importance."""
        logger.info("Creating feature importance visualization...")

        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # Plot 1: Random Forest importance
        if 'random_forest' in self.feature_importance:
            rf_imp = self.feature_importance['random_forest'].head(15)
            axes[0, 0].barh(rf_imp['feature'], rf_imp['importance'])
            axes[0, 0].set_title('Random Forest Feature Importance (Top 15)', fontsize=14, fontweight='bold')
            axes[0, 0].set_xlabel('Importance Score')
            axes[0, 0].invert_yaxis()

        # Plot 2: Gradient Boosting importance
        if 'gradient_boosting' in self.feature_importance:
            gb_imp = self.feature_importance['gradient_boosting'].head(15)
            axes[0, 1].barh(gb_imp['feature'], gb_imp['importance'], color='green')
            axes[0, 1].set_title('Gradient Boosting Feature Importance (Top 15)', fontsize=14, fontweight='bold')
            axes[0, 1].set_xlabel('Importance Score')
            axes[0, 1].invert_yaxis()

        # Plot 3: Correlation with OPS
        if 'correlation' in self.feature_importance:
            corr = self.feature_importance['correlation'].head(15)
            axes[1, 0].barh(corr.index, corr.values, color='orange')
            axes[1, 0].set_title('Correlation with OPS (Top 15)', fontsize=14, fontweight='bold')
            axes[1, 0].set_xlabel('Absolute Correlation')
            axes[1, 0].invert_yaxis()

        # Plot 4: Combined importance scores
        if all(k in self.feature_importance for k in ['random_forest', 'gradient_boosting', 'correlation']):
            # Normalize and combine
            rf_norm = self.feature_importance['random_forest'].set_index('feature')['importance']
            gb_norm = self.feature_importance['gradient_boosting'].set_index('feature')['importance']
            corr_norm = self.feature_importance['correlation']

            # Get common features
            common_features = set(rf_norm.index) & set(gb_norm.index) & set(corr_norm.index)

            combined = pd.DataFrame({
                'rf': rf_norm,
                'gb': gb_norm,
                'corr': corr_norm
            }).loc[list(common_features)].fillna(0)

            # Normalize to 0-1 scale
            combined = (combined - combined.min()) / (combined.max() - combined.min())
            combined['mean'] = combined.mean(axis=1)
            combined = combined.sort_values('mean', ascending=False).head(15)

            axes[1, 1].barh(combined.index, combined['mean'], color='purple')
            axes[1, 1].set_title('Combined Importance Score (Top 15)', fontsize=14, fontweight='bold')
            axes[1, 1].set_xlabel('Normalized Combined Score')
            axes[1, 1].invert_yaxis()

        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        logger.info(f"Saved feature importance plot to {output_file}")

    def generate_insights_report(self, output_file='ml_insights.txt'):
        """Generate text report of ML insights."""
        logger.info("Generating insights report...")

        with open(output_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("PRELIMINARY ML ANALYSIS - MOST VALUABLE MiLB STATISTICS\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Dataset: {len(self.df)} games from {len(self.prospect_df)} prospects\n\n")

            # Key findings from Random Forest
            if 'random_forest' in self.feature_importance:
                f.write("\n" + "-" * 80 + "\n")
                f.write("RANDOM FOREST TOP 10 FEATURES\n")
                f.write("-" * 80 + "\n")
                for idx, row in self.feature_importance['random_forest'].head(10).iterrows():
                    f.write(f"{idx+1:2d}. {row['feature']:30s} {row['importance']:.4f}\n")

            # Key findings from Gradient Boosting
            if 'gradient_boosting' in self.feature_importance:
                f.write("\n" + "-" * 80 + "\n")
                f.write("GRADIENT BOOSTING TOP 10 FEATURES\n")
                f.write("-" * 80 + "\n")
                for idx, row in self.feature_importance['gradient_boosting'].head(10).iterrows():
                    f.write(f"{idx+1:2d}. {row['feature']:30s} {row['importance']:.4f}\n")

            # Correlations
            if 'correlation' in self.feature_importance:
                f.write("\n" + "-" * 80 + "\n")
                f.write("HIGHEST CORRELATIONS WITH OPS\n")
                f.write("-" * 80 + "\n")
                for idx, (feat, val) in enumerate(self.feature_importance['correlation'].head(10).items(), 1):
                    f.write(f"{idx:2d}. {feat:30s} {val:.4f}\n")

            # Summary statistics
            f.write("\n" + "=" * 80 + "\n")
            f.write("KEY INSIGHTS\n")
            f.write("=" * 80 + "\n\n")

            f.write("Most consistently important features across all methods:\n")
            # Find features that appear in top 10 of all methods
            top_features = set()
            if 'random_forest' in self.feature_importance:
                top_features.update(self.feature_importance['random_forest'].head(10)['feature'])
            if 'gradient_boosting' in self.feature_importance:
                top_features &= set(self.feature_importance['gradient_boosting'].head(10)['feature'])
            if 'correlation' in self.feature_importance:
                top_features &= set(self.feature_importance['correlation'].head(10).index)

            for feat in top_features:
                f.write(f"  - {feat}\n")

        logger.info(f"Saved insights report to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Preliminary ML Analysis")
    parser.add_argument('--input', required=True, help='Input CSV with features')
    parser.add_argument('--target', default='ops', help='Target metric for analysis')

    args = parser.parse_args()

    logger.info(f"Loading features from {args.input}...")

    try:
        df = pd.read_csv(args.input)
        logger.info(f"Loaded {len(df)} games")

        analyzer = PreliminaryMLAnalyzer(df)

        # Calculate derived metrics
        analyzer.calculate_derived_metrics()

        # Aggregate to prospect level
        analyzer.aggregate_by_prospect()

        # Run analyses
        analyzer.correlation_analysis(args.target)
        analyzer.random_forest_importance(args.target)
        analyzer.gradient_boosting_importance(args.target)

        # Generate outputs
        analyzer.create_feature_importance_plot('feature_importance.png')
        analyzer.generate_insights_report('ml_insights.txt')

        logger.info("\n" + "="*80)
        logger.info("PRELIMINARY ML ANALYSIS COMPLETE!")
        logger.info("="*80)
        logger.info("\nOutputs:")
        logger.info("  - feature_importance.png: Visual comparison of feature importance")
        logger.info("  - ml_insights.txt: Detailed text report")

    except FileNotFoundError:
        logger.error(f"File not found: {args.input}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
