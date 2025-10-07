"""
Preliminary ML Analysis - Direct from Database

Analyzes MiLB game log data directly from the database to identify
which statistics are most valuable for predicting prospect success.

Uses the existing milb_game_logs table with comprehensive stats.

Analyses performed:
1. Feature correlation matrix
2. Random Forest feature importance
3. Gradient Boosting feature importance
4. Feature stability analysis

Usage:
    python preliminary_ml_analysis_direct.py
"""

import asyncio
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
from sqlalchemy import text

from app.db.database import engine

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class DirectMLAnalyzer:
    """Perform preliminary ML analysis on MiLB game logs from database."""

    def __init__(self):
        self.df = None
        self.prospect_df = None
        self.feature_importance = {}

    async def load_data_from_db(self):
        """Load game log data directly from database."""
        logger.info("Loading data from database...")

        query = text("""
            SELECT
                p.name as prospect_name,
                p.position as prospect_position,
                mgl.*
            FROM milb_game_logs mgl
            JOIN prospects p ON mgl.prospect_id = p.id
            WHERE mgl.at_bats > 0  -- Focus on hitting stats
            ORDER BY mgl.prospect_id, mgl.game_date
        """)

        async with engine.begin() as conn:
            result = await conn.execute(query)
            rows = result.fetchall()
            columns = result.keys()

        self.df = pd.DataFrame(rows, columns=columns)

        # Convert numeric-like columns that may be stored as strings
        numeric_cols_to_convert = ['ops', 'obp', 'slg', 'batting_avg', 'babip']
        for col in numeric_cols_to_convert:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors='coerce')

        logger.info(f"Loaded {len(self.df)} games from {self.df['prospect_id'].nunique()} prospects")

        return self.df

    def calculate_derived_metrics(self):
        """Calculate rate-based metrics from counting stats."""
        logger.info("Calculating derived metrics...")

        df = self.df

        # Batting metrics (skip if already calculated)
        if 'batting_avg' not in df.columns or df['batting_avg'].isna().all():
            df['batting_avg'] = np.where(df['at_bats'] > 0, df['hits'] / df['at_bats'], 0)

        if 'on_base_pct' not in df.columns or df['on_base_pct'].isna().all():
            df['on_base_pct'] = np.where(
                df['plate_appearances'] > 0,
                (df['hits'] + df['walks'] + df['hit_by_pitch']) / df['plate_appearances'],
                0
            )

        if 'slugging_pct' not in df.columns or df['slugging_pct'].isna().all():
            # Calculate singles
            df['singles'] = df['hits'] - (df['doubles'] + df['triples'] + df['home_runs'])
            df['slugging_pct'] = np.where(
                df['at_bats'] > 0,
                (df['singles'] + 2*df['doubles'] + 3*df['triples'] + 4*df['home_runs']) / df['at_bats'],
                0
            )

        if 'ops' not in df.columns or df['ops'].isna().all():
            df['ops'] = df['on_base_pct'] + df['slugging_pct']

        # ISO (Isolated Power)
        df['iso'] = df['slugging_pct'] - df['batting_avg']

        # BABIP (Batting Average on Balls In Play)
        df['babip'] = np.where(
            (df['at_bats'] - df['strikeouts']) > 0,
            (df['hits'] - df['home_runs']) / (df['at_bats'] - df['strikeouts'] - df['home_runs']),
            0
        )

        # Plate discipline
        df['walk_rate'] = np.where(df['plate_appearances'] > 0, df['walks'] / df['plate_appearances'], 0)
        df['strikeout_rate'] = np.where(df['plate_appearances'] > 0, df['strikeouts'] / df['plate_appearances'], 0)
        df['bb_k_ratio'] = np.where(df['strikeouts'] > 0, df['walks'] / df['strikeouts'], 0)

        # Power metrics
        df['hr_rate'] = np.where(df['plate_appearances'] > 0, df['home_runs'] / df['plate_appearances'], 0)
        df['extra_base_hit_rate'] = np.where(
            df['at_bats'] > 0,
            (df['doubles'] + df['triples'] + df['home_runs']) / df['at_bats'],
            0
        )

        # Baserunning
        df['sb_rate'] = np.where(df['plate_appearances'] > 0, df['stolen_bases'] / df['plate_appearances'], 0)
        df['sb_success_rate'] = np.where(
            (df['stolen_bases'] + df['caught_stealing']) > 0,
            df['stolen_bases'] / (df['stolen_bases'] + df['caught_stealing']),
            0
        )

        # Batted ball distribution
        total_batted = df['ground_outs'] + df['fly_outs']
        df['ground_ball_rate'] = np.where(total_batted > 0, df['ground_outs'] / total_batted, 0)
        df['fly_ball_rate'] = np.where(total_batted > 0, df['fly_outs'] / total_batted, 0)

        self.df = df
        logger.info(f"Calculated derived metrics, now have {len(df.columns)} total features")

    def aggregate_by_prospect(self):
        """Aggregate game-level to prospect-level statistics."""
        logger.info("Aggregating to prospect level...")

        # Select numeric columns for aggregation
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns

        # Exclude IDs and game-specific fields
        exclude_cols = ['id', 'prospect_id', 'mlb_player_id', 'game_pk', 'team_id',
                       'opponent_id', 'season', 'games_played']
        agg_cols = [col for col in numeric_cols if col not in exclude_cols]

        # Build aggregation dictionary
        agg_dict = {col: 'mean' for col in agg_cols}
        agg_dict.update({
            'prospect_name': 'first',
            'prospect_position': 'first',
            'level': lambda x: x.mode()[0] if len(x) > 0 else None,
            'game_pk': 'count'  # Count of games
        })

        grouped = self.df.groupby('prospect_id').agg(agg_dict)
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
        feature_cols = [col for col in feature_cols if col not in ['games_played', target]]

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
        feature_cols = [col for col in feature_cols if col not in ['games_played', target]]

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
        feature_cols = [col for col in numeric_cols if col not in ['games_played']]

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
            # Find features that appear in top 10 of multiple methods
            top_features = set()
            if 'random_forest' in self.feature_importance:
                rf_top = set(self.feature_importance['random_forest'].head(10)['feature'])
                top_features.update(rf_top)

            if 'gradient_boosting' in self.feature_importance:
                gb_top = set(self.feature_importance['gradient_boosting'].head(10)['feature'])
                if top_features:
                    top_features &= gb_top
                else:
                    top_features = gb_top

            if 'correlation' in self.feature_importance:
                corr_top = set(self.feature_importance['correlation'].head(10).index)
                if top_features:
                    top_features &= corr_top
                else:
                    top_features = corr_top

            for feat in sorted(top_features):
                f.write(f"  - {feat}\n")

        logger.info(f"Saved insights report to {output_file}")


async def main():
    logger.info("Starting preliminary ML analysis from database...")

    try:
        analyzer = DirectMLAnalyzer()

        # Load data from database
        await analyzer.load_data_from_db()

        # Calculate derived metrics
        analyzer.calculate_derived_metrics()

        # Aggregate to prospect level
        analyzer.aggregate_by_prospect()

        # Run analyses
        analyzer.correlation_analysis('ops')
        analyzer.random_forest_importance('ops')
        analyzer.gradient_boosting_importance('ops')

        # Generate outputs
        analyzer.create_feature_importance_plot('feature_importance_direct.png')
        analyzer.generate_insights_report('ml_insights_direct.txt')

        logger.info("\n" + "="*80)
        logger.info("PRELIMINARY ML ANALYSIS COMPLETE!")
        logger.info("="*80)
        logger.info("\nOutputs:")
        logger.info("  - feature_importance_direct.png: Visual comparison of feature importance")
        logger.info("  - ml_insights_direct.txt: Detailed text report")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
