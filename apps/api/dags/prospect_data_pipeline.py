"""
Daily Prospect Data Pipeline DAG
Orchestrates daily collection of prospect data from MLB API and Fangraphs.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.utils.task_group import TaskGroup
from airflow.sensors.time_sensor import TimeSensor
from airflow.models import Variable
import logging
import os
import sys

# Add app directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.data_processing import (
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
    'retry_delay': timedelta(minutes=15),
    'max_active_runs': 1,
}

# Create the DAG
dag = DAG(
    'prospect_data_pipeline',
    default_args=default_args,
    description='Daily prospect data collection and processing pipeline',
    schedule_interval='0 6 * * *',  # 6:00 AM ET daily
    catchup=False,
    tags=['data-pipeline', 'daily', 'prospects', 'fangraphs', 'mlb'],
)


def extract_mlb_daily_data(**context):
    """Extract daily MLB prospect data."""
    from app.services.mlb_api_service import MLBAPIService
    from app.services.pipeline_monitoring import PipelineMonitor
    import asyncio

    async def fetch_data():
        monitor = PipelineMonitor()
        await monitor.start_pipeline_run("prospect_data_pipeline")

        try:
            service = MLBAPIService()
            prospects = await service.get_top_prospects(limit=500)

            # Store in XCom for downstream tasks
            context['task_instance'].xcom_push(key='mlb_prospects', value=prospects)

            await monitor.record_successful_fetch("mlb_api", f"fetched {len(prospects)} prospects")
            return prospects
        except Exception as e:
            await monitor.record_fetch_error("mlb_api", "daily_prospects", str(e))
            raise

    return asyncio.run(fetch_data())


def extract_fangraphs_daily_data(**context):
    """Extract daily Fangraphs prospect data."""
    from app.services.fangraphs_service import FangraphsService
    from app.services.pipeline_monitoring import PipelineMonitor
    import asyncio

    async def fetch_data():
        monitor = PipelineMonitor()

        try:
            # Get MLB prospects from previous task
            mlb_prospects = context['task_instance'].xcom_pull(
                task_ids='data_extraction.extract_mlb_daily',
                key='mlb_prospects'
            )

            if not mlb_prospects:
                logger.warning("No MLB prospects found in XCom")
                return []

            # Extract prospect names for Fangraphs lookup
            prospect_names = [p.get('fullName', p.get('name', '')) for p in mlb_prospects[:100]]

            async with FangraphsService() as service:
                # Fetch top prospects list first
                top_list = await service.get_top_prospects_list(limit=100)

                # Batch fetch detailed data for prospects
                detailed_data = await service.batch_fetch_prospects(prospect_names)

                # Store in XCom
                context['task_instance'].xcom_push(key='fangraphs_prospects', value=detailed_data)
                context['task_instance'].xcom_push(key='fangraphs_rankings', value=top_list)

                await monitor.record_successful_fetch("fangraphs", f"fetched {len(detailed_data)} prospects")
                return detailed_data

        except Exception as e:
            await monitor.record_fetch_error("fangraphs", "daily_prospects", str(e))
            raise

    return asyncio.run(fetch_data())


def merge_prospect_sources(**context):
    """Merge and reconcile data from multiple sources."""
    from app.services.data_integration_service import DataIntegrationService
    import asyncio

    async def merge_data():
        # Get data from both sources
        mlb_data = context['task_instance'].xcom_pull(
            task_ids='data_extraction.extract_mlb_daily',
            key='mlb_prospects'
        )

        fangraphs_data = context['task_instance'].xcom_pull(
            task_ids='data_extraction.extract_fangraphs_daily',
            key='fangraphs_prospects'
        )

        service = DataIntegrationService()
        merged_data = await service.merge_prospect_data(
            mlb_data=mlb_data,
            fangraphs_data=fangraphs_data,
            precedence_order=['mlb', 'fangraphs']
        )

        context['task_instance'].xcom_push(key='merged_prospects', value=merged_data)
        logger.info(f"Merged {len(merged_data)} prospect records")
        return merged_data

    return asyncio.run(merge_data())


def check_data_freshness(**context):
    """Monitor data freshness and alert on stale data."""
    from app.services.pipeline_monitoring import PipelineMonitor
    import asyncio

    async def check_freshness():
        monitor = PipelineMonitor()

        # Check freshness for both sources
        mlb_freshness = await monitor.check_data_freshness('mlb_api', max_age_hours=24)
        fangraphs_freshness = await monitor.check_data_freshness('fangraphs', max_age_hours=24)

        if not mlb_freshness['is_fresh']:
            await monitor.send_alert(
                level='warning',
                message=f"MLB data is stale: {mlb_freshness['age_hours']} hours old"
            )

        if not fangraphs_freshness['is_fresh']:
            await monitor.send_alert(
                level='warning',
                message=f"Fangraphs data is stale: {fangraphs_freshness['age_hours']} hours old"
            )

        return {
            'mlb': mlb_freshness,
            'fangraphs': fangraphs_freshness
        }

    return asyncio.run(check_freshness())


def store_in_database(**context):
    """Store processed prospect data in database."""
    from app.db.session import get_db
    from app.models.prospect import Prospect
    from app.models.scouting_grades import ScoutingGrades
    from datetime import datetime
    import asyncio

    async def store_data():
        merged_data = context['task_instance'].xcom_pull(
            task_ids='data_processing.merge_sources',
            key='merged_prospects'
        )

        if not merged_data:
            logger.warning("No merged data to store")
            return

        async with get_db() as db:
            stored_count = 0

            for prospect_data in merged_data:
                try:
                    # Upsert prospect
                    prospect = await Prospect.upsert(
                        db,
                        mlb_id=prospect_data.get('mlb_id'),
                        name=prospect_data.get('name'),
                        position=prospect_data.get('position'),
                        organization=prospect_data.get('organization'),
                        level=prospect_data.get('level'),
                        age=prospect_data.get('age'),
                        eta_year=prospect_data.get('eta_year'),
                        last_fangraphs_update=datetime.utcnow() if prospect_data.get('source') == 'fangraphs' else None
                    )

                    # Store scouting grades if available
                    if prospect_data.get('scouting_grades'):
                        await ScoutingGrades.create(
                            db,
                            prospect_id=prospect.id,
                            source=prospect_data.get('source', 'unknown'),
                            **prospect_data['scouting_grades']
                        )

                    stored_count += 1

                except Exception as e:
                    logger.error(f"Error storing prospect {prospect_data.get('name')}: {str(e)}")
                    continue

            await db.commit()
            logger.info(f"Stored {stored_count} prospects in database")
            return stored_count

    return asyncio.run(store_data())


with dag:
    # Start task
    start = DummyOperator(
        task_id='start',
        dag=dag,
    )

    # Wait for optimal time (6 AM ET)
    wait_for_time = TimeSensor(
        task_id='wait_for_collection_time',
        target_time=timedelta(hours=6),
        dag=dag,
    )

    # Task Group for Data Extraction
    with TaskGroup('data_extraction', tooltip='Extract data from multiple sources') as extraction_group:

        # Extract MLB daily data
        extract_mlb_task = PythonOperator(
            task_id='extract_mlb_daily',
            python_callable=extract_mlb_daily_data,
            provide_context=True,
            execution_timeout=timedelta(minutes=30),
            dag=dag,
        )

        # Extract Fangraphs daily data with rate limiting
        extract_fangraphs_task = PythonOperator(
            task_id='extract_fangraphs_daily',
            python_callable=extract_fangraphs_daily_data,
            provide_context=True,
            execution_timeout=timedelta(hours=2),
            trigger_rule='all_done',  # Run even if MLB fails
            dag=dag,
        )

        # Set task dependencies within group
        extract_mlb_task >> extract_fangraphs_task

    # Task Group for Data Processing
    with TaskGroup('data_processing', tooltip='Process and merge data') as processing_group:

        # Merge data from multiple sources
        merge_task = PythonOperator(
            task_id='merge_sources',
            python_callable=merge_prospect_sources,
            provide_context=True,
            dag=dag,
        )

        # Validate merged data
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
                'standardize_positions': True,
                'normalize_stats': True,
            },
            dag=dag,
        )

        # Deduplicate records
        dedupe_task = PythonOperator(
            task_id='deduplicate',
            python_callable=deduplicate_records,
            op_kwargs={
                'match_threshold': 0.9,
                'precedence': ['mlb', 'fangraphs'],
            },
            dag=dag,
        )

        # Set task dependencies within group
        merge_task >> validate_task >> clean_task >> dedupe_task

    # Task Group for Feature Engineering
    with TaskGroup('feature_engineering', tooltip='Generate ML features') as feature_group:

        # Perform feature engineering
        features_task = PythonOperator(
            task_id='generate_features',
            python_callable=perform_feature_engineering,
            dag=dag,
        )

        # Update prospect rankings
        rankings_task = PythonOperator(
            task_id='update_rankings',
            python_callable=update_prospect_rankings,
            dag=dag,
        )

        features_task >> rankings_task

    # Task Group for Storage and Monitoring
    with TaskGroup('storage_monitoring', tooltip='Store data and monitor pipeline') as storage_group:

        # Store in database
        store_task = PythonOperator(
            task_id='store_database',
            python_callable=store_in_database,
            provide_context=True,
            dag=dag,
        )

        # Cache processed results
        cache_task = PythonOperator(
            task_id='cache_results',
            python_callable=cache_processed_results,
            dag=dag,
        )

        # Check data freshness
        freshness_task = PythonOperator(
            task_id='check_freshness',
            python_callable=check_data_freshness,
            provide_context=True,
            dag=dag,
        )

        store_task >> [cache_task, freshness_task]

    # End task
    end = DummyOperator(
        task_id='end',
        dag=dag,
        trigger_rule='none_failed_min_one_success',
    )

    # Define DAG dependencies
    start >> wait_for_time >> extraction_group >> processing_group >> feature_group >> storage_group >> end