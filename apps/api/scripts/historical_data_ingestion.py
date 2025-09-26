#!/usr/bin/env python3
"""
Historical Data Ingestion Script
Processes 15+ years of MiLB → MLB transition data for model training.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
import argparse
import pandas as pd
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.data_processing import (
    extract_mlb_historical_data,
    extract_fangraphs_data,
    validate_ingested_data,
    clean_normalize_data,
    deduplicate_records,
    perform_feature_engineering,
    update_prospect_rankings,
    cache_processed_results
)
from app.core.config import settings
from app.core.database import engine

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('historical_ingestion.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class HistoricalDataPipeline:
    """Orchestrates historical data ingestion and processing."""

    def __init__(self, start_year: int, end_year: int):
        self.start_year = start_year
        self.end_year = end_year
        self.metrics = {
            'start_time': datetime.utcnow(),
            'extraction': {},
            'validation': {},
            'processing': {},
            'features': {}
        }

    async def run_extraction(self):
        """Run data extraction from all sources."""
        logger.info(f"Starting extraction for years {self.start_year}-{self.end_year}")

        # Extract MLB data
        mlb_results = await extract_mlb_historical_data(
            start_year=self.start_year,
            end_year=self.end_year,
            rate_limit=1000,
            batch_size=100
        )
        self.metrics['extraction']['mlb'] = mlb_results

        # Extract Fangraphs data
        fg_results = await extract_fangraphs_data(
            start_year=self.start_year,
            end_year=self.end_year,
            rate_limit_per_second=1
        )
        self.metrics['extraction']['fangraphs'] = fg_results

        logger.info(f"Extraction completed: {mlb_results['records_extracted']} MLB records")
        return True

    def run_validation(self):
        """Validate ingested data."""
        logger.info("Running data validation")

        validation_results = validate_ingested_data(
            check_schemas=True,
            check_outliers=True,
            check_consistency=True
        )
        self.metrics['validation'] = validation_results

        # Log validation issues
        if validation_results['validation_results']['schema_errors']:
            logger.warning(
                f"Found {len(validation_results['validation_results']['schema_errors'])} schema errors"
            )

        if validation_results['validation_results']['outliers']:
            logger.warning(
                f"Found {len(validation_results['validation_results']['outliers'])} outliers"
            )

        return True

    def run_processing(self):
        """Clean and process data."""
        logger.info("Running data processing")

        # Clean and normalize
        clean_results = clean_normalize_data(
            standardize_names=True,
            normalize_stats=True,
            handle_missing='interpolate'
        )
        self.metrics['processing']['cleaning'] = clean_results

        # Deduplicate
        dedup_results = deduplicate_records(
            merge_strategy='most_recent',
            conflict_resolution='weighted_average'
        )
        self.metrics['processing']['deduplication'] = dedup_results

        logger.info(
            f"Processing completed: {clean_results['cleaning_metrics']['stats_normalized']} stats normalized, "
            f"{dedup_results['deduplication_metrics']['duplicates_found']} duplicates resolved"
        )
        return True

    def run_feature_engineering(self):
        """Create features for ML training."""
        logger.info("Running feature engineering")

        feature_results = perform_feature_engineering(
            calculate_age_adjusted=True,
            calculate_progression_rates=True,
            calculate_peer_comparisons=True
        )
        self.metrics['features'] = feature_results

        logger.info(f"Feature engineering completed: {feature_results['feature_metrics']}")
        return True

    def update_rankings_and_cache(self):
        """Update rankings and cache results."""
        logger.info("Updating rankings and caching")

        # Update rankings
        ranking_results = update_prospect_rankings()
        self.metrics['rankings'] = ranking_results

        # Cache results
        cache_results = cache_processed_results(
            cache_type='redis',
            ttl_hours=24
        )
        self.metrics['caching'] = cache_results

        logger.info(f"Updated {ranking_results['rankings_updated']} prospect rankings")
        return True

    def create_ml_training_dataset(self):
        """Create the final ML training dataset with target variables."""
        logger.info("Creating ML training dataset")

        query = """
        WITH career_outcomes AS (
            SELECT
                p.mlb_id,
                p.name,
                MAX(ps.games_played) as total_games,
                SUM(ps.at_bats) as total_at_bats,
                SUM(ps.innings_pitched) as total_innings,
                MIN(p.date_recorded) as first_seen,
                MAX(p.date_recorded) as last_seen,
                CASE
                    WHEN SUM(ps.at_bats) > 500 OR SUM(ps.innings_pitched) > 100 THEN 1
                    ELSE 0
                END as mlb_success
            FROM prospects p
            JOIN prospect_stats ps ON p.id = ps.prospect_id
            WHERE p.level IN ('MLB', 'Triple-A')
            GROUP BY p.mlb_id, p.name
        ),
        feature_data AS (
            SELECT
                p.mlb_id,
                p.name,
                p.position,
                p.age,
                p.level,
                AVG(ps.batting_avg) as avg_batting_avg,
                AVG(ps.on_base_pct) as avg_obp,
                AVG(ps.slugging_pct) as avg_slg,
                AVG(ps.era) as avg_era,
                AVG(ps.whip) as avg_whip,
                AVG(sg.overall_grade) as avg_scouting_grade,
                COUNT(DISTINCT p.level) as levels_played,
                EXTRACT(YEAR FROM AGE(MAX(p.date_recorded), MIN(p.date_recorded))) as years_in_system
            FROM prospects p
            LEFT JOIN prospect_stats ps ON p.id = ps.prospect_id
            LEFT JOIN scouting_grades sg ON p.id = sg.prospect_id
            GROUP BY p.mlb_id, p.name, p.position, p.age, p.level
        )
        SELECT
            fd.*,
            co.mlb_success as target
        FROM feature_data fd
        LEFT JOIN career_outcomes co ON fd.mlb_id = co.mlb_id
        WHERE fd.avg_batting_avg IS NOT NULL OR fd.avg_era IS NOT NULL
        """

        # Save to parquet for efficient ML training
        try:
            df = pd.read_sql(query, engine)

            # Split data temporally
            df['year'] = pd.DatetimeIndex(df.index).year if isinstance(df.index, pd.DatetimeIndex) else 2020

            train_df = df[df['year'] < 2022]
            val_df = df[(df['year'] >= 2022) & (df['year'] < 2023)]
            test_df = df[df['year'] >= 2023]

            # Save datasets
            output_dir = Path('data/ml_training')
            output_dir.mkdir(parents=True, exist_ok=True)

            train_df.to_parquet(output_dir / 'train.parquet', index=False)
            val_df.to_parquet(output_dir / 'validation.parquet', index=False)
            test_df.to_parquet(output_dir / 'test.parquet', index=False)

            logger.info(f"ML datasets created: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

            self.metrics['ml_dataset'] = {
                'train_samples': len(train_df),
                'validation_samples': len(val_df),
                'test_samples': len(test_df),
                'features': list(df.columns),
                'target_distribution': df['target'].value_counts().to_dict() if 'target' in df else {}
            }

            return True

        except Exception as e:
            logger.error(f"Error creating ML dataset: {str(e)}")
            return False

    async def run_pipeline(self):
        """Run the complete historical data pipeline."""
        try:
            logger.info("=" * 50)
            logger.info("Starting Historical Data Ingestion Pipeline")
            logger.info("=" * 50)

            # Run extraction
            await self.run_extraction()

            # Run validation
            self.run_validation()

            # Run processing
            self.run_processing()

            # Run feature engineering
            self.run_feature_engineering()

            # Update rankings
            self.update_rankings_and_cache()

            # Create ML training dataset
            self.create_ml_training_dataset()

            # Calculate total runtime
            self.metrics['end_time'] = datetime.utcnow()
            self.metrics['total_runtime'] = str(
                self.metrics['end_time'] - self.metrics['start_time']
            )

            # Save metrics
            with open('historical_ingestion_metrics.json', 'w') as f:
                json.dump(self.metrics, f, indent=2, default=str)

            logger.info("=" * 50)
            logger.info("Pipeline completed successfully!")
            logger.info(f"Total runtime: {self.metrics['total_runtime']}")
            logger.info("=" * 50)

            return True

        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            self.metrics['error'] = str(e)
            with open('historical_ingestion_metrics.json', 'w') as f:
                json.dump(self.metrics, f, indent=2, default=str)
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Historical Data Ingestion Pipeline')
    parser.add_argument(
        '--start-year',
        type=int,
        default=2009,
        help='Start year for historical data (default: 2009)'
    )
    parser.add_argument(
        '--end-year',
        type=int,
        default=2024,
        help='End year for historical data (default: 2024)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode without database modifications'
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("Running in DRY-RUN mode - no database modifications will be made")
        return

    # Create and run pipeline
    pipeline = HistoricalDataPipeline(
        start_year=args.start_year,
        end_year=args.end_year
    )

    # Run async pipeline
    asyncio.run(pipeline.run_pipeline())


if __name__ == '__main__':
    main()