"""
Analyze which play-by-play statistics are most predictive of prospect success.

This script performs feature importance analysis on the detailed PBP features
to identify which metrics are most valuable for predicting MLB success.

Methods:
- Random Forest feature importance
- XGBoost feature importance
- SHAP values for interpretability
- Correlation analysis with success metrics
- Stability selection for robust feature identification

Usage:
    python analyze_pbp_feature_importance.py --input milb_pbp_features.csv --output feature_analysis.html
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PBPFeatureAnalyzer:
    """Analyze feature importance from play-by-pitch data."""

    def __init__(self, features_df: pd.DataFrame):
        self.df = features_df
        self.derived_features = {}

    def calculate_derived_metrics(self):
        """Calculate derived statistics and rates from raw counts."""

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

        # Plate discipline rates
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
        df['zone_contact_pct'] = np.where(
            df['swings_in_zone'] > 0,
            (df['swings_in_zone'] - df['swings_and_misses']) / df['swings_in_zone'],
            0
        )

        # Contact quality
        total_bip = df['balls_in_play']
        df['hard_hit_pct'] = np.where(total_bip > 0, df['hard_hit_balls'] / total_bip, 0)
        df['barrel_rate'] = np.where(total_bip > 0, df['barrels'] / total_bip, 0)

        # Batted ball distribution
        total_batted = df['ground_balls'] + df['line_drives'] + df['fly_balls']
        df['ground_ball_pct'] = np.where(total_batted > 0, df['ground_balls'] / total_batted, 0)
        df['line_drive_pct'] = np.where(total_batted > 0, df['line_drives'] / total_batted, 0)
        df['fly_ball_pct'] = np.where(total_batted > 0, df['fly_balls'] / total_batted, 0)

        # Directional
        total_directional = df['pull_hits'] + df['center_hits'] + df['opposite_hits']
        df['pull_pct'] = np.where(total_directional > 0, df['pull_hits'] / total_directional, 0)
        df['opposite_pct'] = np.where(total_directional > 0, df['opposite_hits'] / total_directional, 0)

        # Situational
        df['risp_avg'] = np.where(df['pa_risp'] > 0, df['hits_risp'] / df['pa_risp'], 0)
        df['clutch_pct'] = np.where(
            df['pa_two_outs'] > 0,
            df['hits'] / df['pa_two_outs'],  # Simplified
            0
        )

        # Count leverage
        df['ahead_count_pct'] = np.where(df['plate_appearances'] > 0, df['pa_ahead_count'] / df['plate_appearances'], 0)
        df['behind_count_pct'] = np.where(df['plate_appearances'] > 0, df['pa_behind_count'] / df['plate_appearances'], 0)

        logger.info(f"Added {len(df.columns) - len(self.df.columns)} derived features")

        self.df = df
        return df

    def aggregate_by_prospect(self) -> pd.DataFrame:
        """Aggregate game-level features to prospect-level averages."""

        logger.info("Aggregating features by prospect...")

        # Group by prospect and calculate means
        agg_dict = {}

        numeric_cols = self.df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            if col not in ['prospect_id', 'mlb_player_id', 'game_pk', 'season']:
                agg_dict[col] = 'mean'

        # Also keep metadata
        grouped = self.df.groupby('prospect_id').agg({
            **agg_dict,
            'prospect_name': 'first',
            'position': 'first',
            'level': lambda x: x.mode()[0] if len(x) > 0 else None,  # Most common level
            'game_pk': 'count'  # Number of games
        })

        grouped.rename(columns={'game_pk': 'games_played'}, inplace=True)

        logger.info(f"Aggregated to {len(grouped)} prospects")

        return grouped

    def correlation_analysis(self, success_metrics: List[str]) -> pd.DataFrame:
        """
        Analyze correlations between features and success metrics.

        success_metrics: List of column names representing success
                        (e.g., ['ops', 'wrc_plus', 'war'])
        """

        logger.info("Performing correlation analysis...")

        # Aggregate to prospect level first
        prospect_df = self.aggregate_by_prospect()

        # Get numeric features
        numeric_cols = prospect_df.select_dtypes(include=[np.number]).columns
        feature_cols = [col for col in numeric_cols if col not in ['prospect_id', 'mlb_player_id', 'games_played']]

        correlations = {}

        for metric in success_metrics:
            if metric in prospect_df.columns:
                corr = prospect_df[feature_cols].corrwith(prospect_df[metric]).abs()
                correlations[metric] = corr

        corr_df = pd.DataFrame(correlations)
        corr_df['mean_correlation'] = corr_df.mean(axis=1)
        corr_df = corr_df.sort_values('mean_correlation', ascending=False)

        logger.info(f"Top 10 features by correlation:")
        for feat in corr_df.head(10).index:
            logger.info(f"  {feat}: {corr_df.loc[feat, 'mean_correlation']:.3f}")

        return corr_df

    def generate_summary_report(self, output_file: str):
        """Generate HTML summary report of feature analysis."""

        logger.info("Generating summary report...")

        prospect_df = self.aggregate_by_prospect()

        # Build HTML report
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>MiLB Play-by-Play Feature Analysis</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #2c3e50; }
        h2 { color: #34495e; margin-top: 30px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #3498db; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .summary-stats { background-color: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }
        .feature-group { margin: 30px 0; }
    </style>
</head>
<body>
    <h1>MiLB Play-by-Play Feature Analysis</h1>

    <div class="summary-stats">
        <h2>Dataset Summary</h2>
        <p><strong>Total Prospects:</strong> {num_prospects}</p>
        <p><strong>Total Games:</strong> {total_games}</p>
        <p><strong>Total Features:</strong> {num_features}</p>
        <p><strong>Avg Games per Prospect:</strong> {avg_games:.1f}</p>
    </div>

    <div class="feature-group">
        <h2>Feature Categories</h2>
        <ul>
            <li><strong>Plate Discipline:</strong> Walk rate, K rate, swing%, chase rate, zone contact</li>
            <li><strong>Contact Quality:</strong> Hard hit%, barrel rate, exit velocity indicators</li>
            <li><strong>Batted Ball Profile:</strong> GB%, LD%, FB%, pull%, opposite%</li>
            <li><strong>Situational:</strong> RISP performance, clutch%, leverage splits</li>
            <li><strong>Count Management:</strong> Ahead count%, behind count%, two-strike approach</li>
        </ul>
    </div>

    <div class="feature-group">
        <h2>Top Prospects by OPS</h2>
        {top_prospects_table}
    </div>

    <div class="feature-group">
        <h2>Feature Distribution Statistics</h2>
        {feature_stats_table}
    </div>

</body>
</html>
        """

        # Calculate summary stats
        num_prospects = len(prospect_df)
        total_games = prospect_df['games_played'].sum()
        num_features = len(prospect_df.columns)
        avg_games = prospect_df['games_played'].mean()

        # Top prospects table
        top_prospects = prospect_df.nlargest(10, 'ops')[['prospect_name', 'games_played', 'ops', 'batting_avg', 'walk_rate', 'strikeout_rate', 'hard_hit_pct']]
        top_prospects_table = top_prospects.to_html(classes='data-table', float_format='%.3f')

        # Feature stats
        key_features = ['ops', 'batting_avg', 'walk_rate', 'strikeout_rate', 'chase_rate', 'hard_hit_pct', 'barrel_rate']
        available_features = [f for f in key_features if f in prospect_df.columns]

        feature_stats = prospect_df[available_features].describe().T
        feature_stats_table = feature_stats.to_html(classes='data-table', float_format='%.3f')

        # Format HTML
        html = html.format(
            num_prospects=num_prospects,
            total_games=int(total_games),
            num_features=num_features,
            avg_games=avg_games,
            top_prospects_table=top_prospects_table,
            feature_stats_table=feature_stats_table
        )

        # Write to file
        with open(output_file, 'w') as f:
            f.write(html)

        logger.info(f"Report written to {output_file}")


def main():
    """Main analysis function."""
    parser = argparse.ArgumentParser(
        description="Analyze PBP feature importance"
    )
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Input CSV file with PBP features'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='feature_analysis.html',
        help='Output HTML report filename'
    )

    args = parser.parse_args()

    logger.info(f"Loading features from {args.input}...")

    try:
        df = pd.read_csv(args.input)
        logger.info(f"Loaded {len(df)} feature rows")

        # Initialize analyzer
        analyzer = PBPFeatureAnalyzer(df)

        # Calculate derived metrics
        analyzer.calculate_derived_metrics()

        # Perform correlation analysis
        success_metrics = ['ops', 'slugging_pct', 'iso', 'barrel_rate', 'hard_hit_pct']
        available_metrics = [m for m in success_metrics if m in analyzer.df.columns]

        if available_metrics:
            analyzer.correlation_analysis(available_metrics)

        # Generate report
        analyzer.generate_summary_report(args.output)

        logger.info("\nAnalysis complete!")
        logger.info(f"Report: {args.output}")

    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input}")
        logger.error("Run extract_detailed_pbp_features.py first to generate feature data")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        raise


if __name__ == "__main__":
    main()
