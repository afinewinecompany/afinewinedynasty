"""
APScheduler configuration and initialization.

This module configures and manages the background job scheduler for
the application using APScheduler with AsyncIOScheduler.

@module scheduler
@since 1.0.0
"""

import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def _job_listener(event):
    """
    Listen to job execution events for logging and monitoring.

    @param event - APScheduler job event
    @since 1.0.0
    """
    if event.exception:
        logger.error(
            f"Job {event.job_id} failed with exception: {event.exception}",
            exc_info=event.exception
        )
    else:
        logger.info(f"Job {event.job_id} executed successfully")


def get_scheduler() -> AsyncIOScheduler:
    """
    Get or create the global scheduler instance.

    @returns APScheduler instance
    @since 1.0.0
    """
    global _scheduler

    if _scheduler is None:
        # Configure job stores
        jobstores = {
            'default': MemoryJobStore()
            # Can be upgraded to RedisJobStore for persistence:
            # 'default': RedisJobStore(
            #     host='localhost',
            #     port=6379,
            #     db=0
            # )
        }

        # Configure executors
        executors = {
            'default': AsyncIOExecutor()
        }

        # Job defaults
        job_defaults = {
            'coalesce': True,  # Combine missed runs into one
            'max_instances': 1,  # Prevent job overlap
            'misfire_grace_time': 300  # Allow 5 minutes of grace for missed jobs
        }

        # Create scheduler instance
        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Add event listeners
        _scheduler.add_listener(
            _job_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

        logger.info("APScheduler initialized with AsyncIOScheduler")

    return _scheduler


def start_scheduler() -> None:
    """
    Initialize and start the background job scheduler.

    Imports all job scheduling functions and starts the scheduler.
    Should be called once during application startup.

    @throws Exception - If scheduler fails to start

    @since 1.0.0
    """
    try:
        scheduler = get_scheduler()

        # Import all schedule functions from jobs
        from app.jobs import (
            schedule_email_digests,
            schedule_analytics_aggregation,
            schedule_churn_prediction
        )

        logger.info("Scheduling background jobs...")

        # Schedule all jobs
        schedule_email_digests(scheduler)
        schedule_analytics_aggregation(scheduler)
        schedule_churn_prediction(scheduler)

        # Start the scheduler
        scheduler.start()

        logger.info("Background job scheduler started successfully")

        # Log scheduled jobs
        jobs = scheduler.get_jobs()
        logger.info(f"Total jobs scheduled: {len(jobs)}")
        for job in jobs:
            logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {job.next_run_time}")

    except Exception as e:
        logger.error(f"Failed to start scheduler: {str(e)}")
        raise


def shutdown_scheduler() -> None:
    """
    Gracefully shutdown the background job scheduler.

    Waits for running jobs to complete before shutting down.
    Should be called during application shutdown.

    @since 1.0.0
    """
    global _scheduler

    if _scheduler is not None:
        try:
            logger.info("Shutting down background job scheduler...")

            # Shutdown scheduler (wait=True ensures running jobs complete)
            _scheduler.shutdown(wait=True)

            _scheduler = None

            logger.info("Background job scheduler shut down successfully")

        except Exception as e:
            logger.error(f"Error during scheduler shutdown: {str(e)}")
            raise


def get_scheduled_jobs() -> list:
    """
    Get list of all scheduled jobs.

    Useful for monitoring and debugging.

    @returns List of scheduled job details
    @since 1.0.0
    """
    scheduler = get_scheduler()

    jobs = scheduler.get_jobs()
    job_list = []

    for job in jobs:
        job_list.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })

    return job_list


def pause_scheduler() -> None:
    """
    Pause the scheduler temporarily.

    Jobs will not execute while paused.

    @since 1.0.0
    """
    scheduler = get_scheduler()
    scheduler.pause()
    logger.info("Scheduler paused")


def resume_scheduler() -> None:
    """
    Resume the scheduler after pausing.

    @since 1.0.0
    """
    scheduler = get_scheduler()
    scheduler.resume()
    logger.info("Scheduler resumed")
