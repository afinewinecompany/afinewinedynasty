"""
Historical Data Ingestion DAG for MLB prospect data processing.
Orchestrates the collection of 15+ years of MiLB → MLB transition data.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.task_group import TaskGroup
import logging
import os
import sys

# Add app directory to path for imports
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

logger = logging.getLogger(__name__)

# Default arguments for the DAG
default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'max_active_runs': 1,
}

# Create the DAG
dag = DAG(
    'historical_data_ingestion',
    default_args=default_args,
    description='Historical minor league data ingestion and processing pipeline',
    schedule_interval='@daily',
    catchup=False,
    tags=['data-pipeline', 'historical', 'ml-training'],
)

with dag:
    # Start task
    start = DummyOperator(
        task_id='start',
        dag=dag,
    )

    # Task Group for Data Extraction
    with TaskGroup('data_extraction', tooltip='Extract data from multiple sources') as extraction_group:

        # Extract MLB historical data with rate limiting
        extract_mlb_task = PythonOperator(
            task_id='extract_mlb_historical',
            python_callable=extract_mlb_historical_data,
            op_kwargs={
                'start_year': 2009,
                'end_year': 2024,
                'rate_limit': 1000,  # Daily limit
                'batch_size': 100,
            },
            execution_timeout=timedelta(hours=2),
            dag=dag,
        )

        # Extract Fangraphs historical data
        extract_fangraphs_task = PythonOperator(
            task_id='extract_fangraphs_historical',
            python_callable=extract_fangraphs_data,
            op_kwargs={
                'start_year': 2009,
                'end_year': 2024,
                'rate_limit_per_second': 1,
            },
            execution_timeout=timedelta(hours=1),
            dag=dag,
        )

    # Task Group for Data Validation and Cleaning
    with TaskGroup('data_processing', tooltip='Validate and clean ingested data') as processing_group:

        # Validate ingested data
        validate_task = PythonOperator(
            task_id='validate_data',
            python_callable=validate_ingested_data,
            op_kwargs={
                'check_schemas': True,
                'check_outliers': True,
                'check_consistency': True,
            },
            dag=dag,
        )

        # Clean and normalize data
        clean_task = PythonOperator(
            task_id='clean_normalize',
            python_callable=clean_normalize_data,
            op_kwargs={
                'standardize_names': True,
                'normalize_stats': True,
                'handle_missing': 'interpolate',
            },
            dag=dag,
        )

        # Deduplicate records
        dedupe_task = PythonOperator(
            task_id='deduplicate',
            python_callable=deduplicate_records,
            op_kwargs={
                'merge_strategy': 'most_recent',
                'conflict_resolution': 'weighted_average',
            },
            dag=dag,
        )

        validate_task >> clean_task >> dedupe_task

    # Feature engineering task
    feature_eng_task = PythonOperator(
        task_id='feature_engineering',
        python_callable=perform_feature_engineering,
        op_kwargs={
            'calculate_age_adjusted': True,
            'calculate_progression_rates': True,
            'calculate_peer_comparisons': True,
        },
        execution_timeout=timedelta(hours=1),
        dag=dag,
    )

    # Update rankings based on processed data
    update_rankings_task = PythonOperator(
        task_id='update_rankings',
        python_callable=update_prospect_rankings,
        dag=dag,
    )

    # Cache results for faster access
    cache_task = PythonOperator(
        task_id='cache_results',
        python_callable=cache_processed_results,
        op_kwargs={
            'cache_type': 'redis',
            'ttl_hours': 24,
        },
        dag=dag,
    )

    # End task
    end = DummyOperator(
        task_id='end',
        dag=dag,
        trigger_rule='none_failed_or_skipped',
    )

    # Define task dependencies
    start >> extraction_group >> processing_group >> feature_eng_task >> update_rankings_task >> cache_task >> end