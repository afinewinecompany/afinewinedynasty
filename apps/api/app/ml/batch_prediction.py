"""Batch Prediction Service

Efficient bulk processing for ML predictions with job queuing,
progress tracking, and optimized database operations.
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..core.database import get_db
from ..core.cache_manager import CacheManager
from ..models.prospect import Prospect
from ..schemas.ml_predictions import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionResponse,
    ConfidenceLevel
)
from .model_serving import ModelServer
from .confidence_scoring import ConfidenceScorer
from ..services.prospect_feature_extraction import ProspectFeatureExtractor

logger = logging.getLogger(__name__)


class BatchJobStatus(str, Enum):
    """Status tracking for batch prediction jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BatchJob:
    """Batch prediction job tracking."""
    job_id: str
    user_id: int
    prospect_ids: List[int]
    total_prospects: int
    processed_count: int
    failed_count: int
    status: BatchJobStatus
    model_version: str
    include_explanations: bool
    chunk_size: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    results: List[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
        return data


class BatchPredictionService:
    """
    Service for handling bulk ML predictions with efficient processing,
    job queuing, and progress tracking.
    """

    def __init__(self):
        self.active_jobs: Dict[str, BatchJob] = {}
        self.job_queue: asyncio.Queue = asyncio.Queue()
        self.max_concurrent_jobs = 3
        self.max_batch_size = 1000
        self.worker_tasks: List[asyncio.Task] = []

    async def initialize(self):
        """Initialize batch prediction service and start worker tasks."""
        try:
            # Start worker tasks for processing jobs
            for i in range(self.max_concurrent_jobs):
                task = asyncio.create_task(self._worker_task(f"worker-{i}"))
                self.worker_tasks.append(task)

            logger.info(f"Batch prediction service initialized with {self.max_concurrent_jobs} workers")

        except Exception as e:
            logger.error(f"Failed to initialize batch prediction service: {e}")
            raise

    async def shutdown(self):
        """Shutdown batch prediction service and cleanup resources."""
        try:
            # Cancel all worker tasks
            for task in self.worker_tasks:
                task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

            logger.info("Batch prediction service shutdown complete")

        except Exception as e:
            logger.error(f"Error during batch service shutdown: {e}")

    async def submit_batch_job(
        self,
        request: BatchPredictionRequest,
        user_id: int,
        model_version: str
    ) -> str:
        """
        Submit a new batch prediction job to the queue.

        Returns:
            str: Unique job ID for tracking
        """
        try:
            # Validate batch size
            if len(request.prospect_ids) > self.max_batch_size:
                raise ValueError(f"Batch size {len(request.prospect_ids)} exceeds maximum {self.max_batch_size}")

            # Create batch job
            job_id = str(uuid.uuid4())
            job = BatchJob(
                job_id=job_id,
                user_id=user_id,
                prospect_ids=request.prospect_ids.copy(),
                total_prospects=len(request.prospect_ids),
                processed_count=0,
                failed_count=0,
                status=BatchJobStatus.PENDING,
                model_version=model_version,
                include_explanations=request.include_explanations,
                chunk_size=request.chunk_size,
                created_at=datetime.utcnow(),
                results=[]
            )

            # Store job and add to queue
            self.active_jobs[job_id] = job
            await self.job_queue.put(job_id)

            logger.info(f"Batch job {job_id} submitted for {len(request.prospect_ids)} prospects")
            return job_id

        except Exception as e:
            logger.error(f"Failed to submit batch job: {e}")
            raise

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a batch job."""
        job = self.active_jobs.get(job_id)
        if not job:
            return None

        return {
            "job_id": job.job_id,
            "status": job.status.value,
            "total_prospects": job.total_prospects,
            "processed_count": job.processed_count,
            "failed_count": job.failed_count,
            "progress_percentage": (job.processed_count / job.total_prospects * 100) if job.total_prospects > 0 else 0,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message
        }

    async def get_job_results(self, job_id: str) -> Optional[BatchPredictionResponse]:
        """Get results of a completed batch job."""
        job = self.active_jobs.get(job_id)
        if not job or job.status != BatchJobStatus.COMPLETED:
            return None

        # Convert results to PredictionResponse objects
        predictions = []
        for result_data in job.results:
            prediction = PredictionResponse(**result_data)
            predictions.append(prediction)

        failed_prospects = [
            prospect_id for prospect_id in job.prospect_ids
            if not any(p.prospect_id == prospect_id for p in predictions)
        ]

        processing_time = 0.0
        if job.started_at and job.completed_at:
            processing_time = (job.completed_at - job.started_at).total_seconds()

        return BatchPredictionResponse(
            predictions=predictions,
            batch_id=job_id,
            processed_count=job.processed_count,
            failed_count=job.failed_count,
            failed_prospects=failed_prospects,
            model_version=job.model_version,
            processing_time=processing_time,
            created_at=job.created_at
        )

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running batch job."""
        job = self.active_jobs.get(job_id)
        if not job:
            return False

        if job.status in [BatchJobStatus.PENDING, BatchJobStatus.RUNNING]:
            job.status = BatchJobStatus.CANCELLED
            job.completed_at = datetime.utcnow()
            logger.info(f"Batch job {job_id} cancelled")
            return True

        return False

    async def _worker_task(self, worker_name: str):
        """Worker task for processing batch jobs from the queue."""
        logger.info(f"Batch worker {worker_name} started")

        try:
            while True:
                # Get next job from queue
                job_id = await self.job_queue.get()

                job = self.active_jobs.get(job_id)
                if not job or job.status != BatchJobStatus.PENDING:
                    continue

                logger.info(f"Worker {worker_name} processing batch job {job_id}")

                try:
                    await self._process_batch_job(job)
                except Exception as e:
                    logger.error(f"Worker {worker_name} failed to process job {job_id}: {e}")
                    job.status = BatchJobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = datetime.utcnow()

                finally:
                    self.job_queue.task_done()

        except asyncio.CancelledError:
            logger.info(f"Batch worker {worker_name} cancelled")
        except Exception as e:
            logger.error(f"Batch worker {worker_name} error: {e}")

    async def _process_batch_job(self, job: BatchJob):
        """Process a single batch job."""
        try:
            job.status = BatchJobStatus.RUNNING
            job.started_at = datetime.utcnow()

            # Initialize services
            model_server = ModelServer()
            cache_manager = CacheManager()
            confidence_scorer = ConfidenceScorer()
            feature_extractor = ProspectFeatureExtractor()

            # Process prospects in chunks
            for i in range(0, len(job.prospect_ids), job.chunk_size):
                # Check if job was cancelled
                if job.status == BatchJobStatus.CANCELLED:
                    return

                chunk = job.prospect_ids[i:i + job.chunk_size]
                logger.debug(f"Processing chunk {i//job.chunk_size + 1} with {len(chunk)} prospects")

                # Process chunk concurrently
                chunk_tasks = []
                for prospect_id in chunk:
                    task = asyncio.create_task(
                        self._process_single_prospect(
                            prospect_id=prospect_id,
                            job=job,
                            model_server=model_server,
                            cache_manager=cache_manager,
                            confidence_scorer=confidence_scorer,
                            feature_extractor=feature_extractor
                        )
                    )
                    chunk_tasks.append(task)

                # Wait for chunk completion
                chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

                # Process results
                for result in chunk_results:
                    if isinstance(result, Exception):
                        job.failed_count += 1
                        logger.warning(f"Prospect prediction failed: {result}")
                    else:
                        job.results.append(result)
                        job.processed_count += 1

                # Optional: Add small delay between chunks to avoid overwhelming the system
                await asyncio.sleep(0.1)

            # Mark job as completed
            job.status = BatchJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()

            processing_time = (job.completed_at - job.started_at).total_seconds()
            logger.info(
                f"Batch job {job.job_id} completed: "
                f"{job.processed_count}/{job.total_prospects} successful, "
                f"{job.failed_count} failed, "
                f"{processing_time:.2f}s total"
            )

        except Exception as e:
            logger.error(f"Batch job processing failed: {e}")
            job.status = BatchJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            raise

    async def _process_single_prospect(
        self,
        prospect_id: int,
        job: BatchJob,
        model_server: ModelServer,
        cache_manager: CacheManager,
        confidence_scorer: ConfidenceScorer,
        feature_extractor: ProspectFeatureExtractor
    ) -> Dict[str, Any]:
        """Process ML prediction for a single prospect in batch job."""

        try:
            # Check cache first for performance
            cached_prediction = await cache_manager.get_cached_prediction(
                prospect_id, job.model_version
            )

            if cached_prediction and not job.include_explanations:
                # Return cached result
                cached_prediction["cache_hit"] = True
                return cached_prediction

            # Get database session (simplified for batch processing)
            # In production, this would use connection pooling
            db = next(get_db())

            # Extract prospect features
            features = await feature_extractor.get_prospect_features(
                prospect_id, db, cache_manager
            )

            if not features:
                raise ValueError(f"Prospect {prospect_id} not found or insufficient data")

            # Generate prediction
            prediction_result = await model_server.predict(
                features=features,
                include_explanation=job.include_explanations,
                model_version=job.model_version
            )

            # Calculate confidence score
            confidence_level = await confidence_scorer.calculate_confidence(
                prediction_result["probability"],
                prediction_result.get("shap_values"),
                features
            )

            # Build response data
            response_data = {
                "prospect_id": prospect_id,
                "success_probability": prediction_result["probability"],
                "confidence_level": confidence_level.value,
                "model_version": job.model_version,
                "explanation": prediction_result.get("explanation"),
                "prediction_time": datetime.utcnow().isoformat(),
                "cache_hit": False
            }

            # Cache the result for future use
            await cache_manager.cache_prediction(
                prospect_id=prospect_id,
                model_version=job.model_version,
                prediction_data=response_data
            )

            return response_data

        except Exception as e:
            logger.error(f"Failed to process prospect {prospect_id} in batch job: {e}")
            raise

    async def cleanup_old_jobs(self, retention_days: int = 7):
        """Clean up old completed/failed jobs to free memory."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        jobs_to_remove = []
        for job_id, job in self.active_jobs.items():
            if (job.status in [BatchJobStatus.COMPLETED, BatchJobStatus.FAILED, BatchJobStatus.CANCELLED] and
                job.completed_at and job.completed_at < cutoff_date):
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.active_jobs[job_id]

        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old batch jobs")

    async def get_active_jobs_count(self) -> Dict[str, int]:
        """Get count of jobs by status."""
        status_counts = {status.value: 0 for status in BatchJobStatus}

        for job in self.active_jobs.values():
            status_counts[job.status.value] += 1

        return status_counts

    async def get_job_metrics(self) -> Dict[str, Any]:
        """Get batch processing performance metrics."""
        total_jobs = len(self.active_jobs)
        if total_jobs == 0:
            return {
                "total_jobs": 0,
                "average_processing_time": 0.0,
                "success_rate": 0.0,
                "throughput_per_hour": 0.0
            }

        completed_jobs = [
            job for job in self.active_jobs.values()
            if job.status == BatchJobStatus.COMPLETED and job.started_at and job.completed_at
        ]

        if not completed_jobs:
            return {
                "total_jobs": total_jobs,
                "average_processing_time": 0.0,
                "success_rate": 0.0,
                "throughput_per_hour": 0.0
            }

        # Calculate metrics
        processing_times = [
            (job.completed_at - job.started_at).total_seconds()
            for job in completed_jobs
        ]
        average_processing_time = sum(processing_times) / len(processing_times)

        total_prospects_processed = sum(job.processed_count for job in completed_jobs)
        total_prospects_requested = sum(job.total_prospects for job in completed_jobs)
        success_rate = total_prospects_processed / total_prospects_requested if total_prospects_requested > 0 else 0

        # Calculate throughput (prospects per hour)
        total_processing_hours = sum(processing_times) / 3600
        throughput_per_hour = total_prospects_processed / total_processing_hours if total_processing_hours > 0 else 0

        return {
            "total_jobs": total_jobs,
            "completed_jobs": len(completed_jobs),
            "average_processing_time": average_processing_time,
            "success_rate": success_rate,
            "throughput_per_hour": throughput_per_hour,
            "status_breakdown": await self.get_active_jobs_count()
        }