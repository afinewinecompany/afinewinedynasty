import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass
import json

from app.services.data_ingestion_service import data_ingestion_service

logger = logging.getLogger(__name__)


@dataclass
class ScheduledJob:
    """Represents a scheduled job."""
    id: str
    name: str
    cron_expression: Optional[str] = None
    scheduled_time: Optional[time] = None
    interval_minutes: Optional[int] = None
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    is_active: bool = True
    job_function: Optional[Callable] = None
    results: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.results is None:
            self.results = []


class SchedulerService:
    """Background job scheduler for data ingestion and other tasks."""

    def __init__(self):
        self.jobs: Dict[str, ScheduledJob] = {}
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._setup_default_jobs()

    def _setup_default_jobs(self) -> None:
        """Setup default scheduled jobs."""
        # Daily data ingestion at 6:00 AM ET
        self.schedule_job(
            job_id="daily_data_ingestion",
            name="Daily MLB Data Ingestion",
            scheduled_time=time(6, 0),  # 6:00 AM
            job_function=self._run_daily_ingestion
        )

        # Hourly health check
        self.schedule_job(
            job_id="hourly_health_check",
            name="Hourly Health Check",
            interval_minutes=60,
            job_function=self._run_health_check
        )

    def schedule_job(
        self,
        job_id: str,
        name: str,
        job_function: Callable,
        scheduled_time: Optional[time] = None,
        interval_minutes: Optional[int] = None,
        cron_expression: Optional[str] = None
    ) -> None:
        """
        Schedule a new job.

        Args:
            job_id: Unique job identifier
            name: Human readable job name
            job_function: Function to execute
            scheduled_time: Daily time to run (for daily jobs)
            interval_minutes: Interval in minutes (for recurring jobs)
            cron_expression: Cron expression (future enhancement)
        """
        job = ScheduledJob(
            id=job_id,
            name=name,
            scheduled_time=scheduled_time,
            interval_minutes=interval_minutes,
            cron_expression=cron_expression,
            job_function=job_function
        )

        # Calculate next run time
        job.next_run = self._calculate_next_run(job)

        self.jobs[job_id] = job
        logger.info(f"Scheduled job '{name}' with ID '{job_id}', next run: {job.next_run}")

    def _calculate_next_run(self, job: ScheduledJob) -> datetime:
        """Calculate the next run time for a job."""
        now = datetime.now()

        if job.scheduled_time:
            # Daily job at specific time
            next_run = datetime.combine(now.date(), job.scheduled_time)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run

        elif job.interval_minutes:
            # Recurring job with interval
            if job.last_run:
                return job.last_run + timedelta(minutes=job.interval_minutes)
            else:
                return now + timedelta(minutes=job.interval_minutes)

        else:
            # Default to 1 hour from now
            return now + timedelta(hours=1)

    async def start_scheduler(self) -> None:
        """Start the background scheduler."""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return

        self.is_running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")

    async def stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        if not self.is_running:
            return

        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info("Scheduler loop started")

        while self.is_running:
            try:
                now = datetime.now()

                # Check each job
                for job in self.jobs.values():
                    if not job.is_active:
                        continue

                    if job.next_run and now >= job.next_run:
                        await self._execute_job(job)

                # Sleep for 60 seconds before next check
                await asyncio.sleep(60)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                await asyncio.sleep(60)

        logger.info("Scheduler loop ended")

    async def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a scheduled job."""
        if not job.job_function:
            logger.error(f"No job function defined for job {job.id}")
            return

        logger.info(f"Executing job: {job.name}")
        start_time = datetime.now()

        try:
            # Execute the job function
            result = await job.job_function()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Record job execution result
            execution_result = {
                "job_id": job.id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "status": "success",
                "result": result if isinstance(result, (dict, list, str, int, float, bool)) else str(result)
            }

            job.results.append(execution_result)
            # Keep only last 10 results
            if len(job.results) > 10:
                job.results = job.results[-10:]

            logger.info(f"Job {job.name} completed successfully in {duration:.2f}s")

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            execution_result = {
                "job_id": job.id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "status": "error",
                "error": str(e)
            }

            job.results.append(execution_result)
            if len(job.results) > 10:
                job.results = job.results[-10:]

            logger.error(f"Job {job.name} failed after {duration:.2f}s: {str(e)}")

        finally:
            # Update job timing
            job.last_run = start_time
            job.next_run = self._calculate_next_run(job)
            logger.debug(f"Next run for {job.name}: {job.next_run}")

    async def _run_daily_ingestion(self) -> Dict[str, Any]:
        """Execute daily data ingestion."""
        try:
            result = await data_ingestion_service.run_daily_ingestion()
            return result
        except Exception as e:
            logger.error(f"Daily ingestion job failed: {str(e)}")
            raise

    async def _run_health_check(self) -> Dict[str, Any]:
        """Execute health check."""
        return {
            "scheduler_status": "running",
            "active_jobs": len([j for j in self.jobs.values() if j.is_active]),
            "total_jobs": len(self.jobs),
            "timestamp": datetime.now().isoformat()
        }

    async def trigger_job(self, job_id: str) -> Dict[str, Any]:
        """Manually trigger a job execution."""
        if job_id not in self.jobs:
            raise ValueError(f"Job with ID '{job_id}' not found")

        job = self.jobs[job_id]
        logger.info(f"Manually triggering job: {job.name}")

        await self._execute_job(job)

        if job.results:
            return job.results[-1]  # Return latest result
        else:
            return {"status": "triggered", "message": "Job execution started"}

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job."""
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        return {
            "id": job.id,
            "name": job.name,
            "is_active": job.is_active,
            "last_run": job.last_run.isoformat() if job.last_run else None,
            "next_run": job.next_run.isoformat() if job.next_run else None,
            "recent_results": job.results[-3:] if job.results else []
        }

    def get_all_jobs_status(self) -> Dict[str, Any]:
        """Get status of all jobs."""
        return {
            "scheduler_running": self.is_running,
            "jobs": {
                job_id: self.get_job_status(job_id)
                for job_id in self.jobs.keys()
            }
        }

    def activate_job(self, job_id: str) -> bool:
        """Activate a job."""
        if job_id in self.jobs:
            self.jobs[job_id].is_active = True
            logger.info(f"Activated job: {job_id}")
            return True
        return False

    def deactivate_job(self, job_id: str) -> bool:
        """Deactivate a job."""
        if job_id in self.jobs:
            self.jobs[job_id].is_active = False
            logger.info(f"Deactivated job: {job_id}")
            return True
        return False


# Singleton instance
scheduler_service = SchedulerService()