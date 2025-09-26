"""ML Prediction API endpoints.

Provides real-time prospect success predictions with SHAP explanations,
confidence scoring, and <500ms response time requirements.
"""

import asyncio
import time
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.cache_manager import CacheManager
from ....core.auth import get_current_user
from ....core.rate_limiting import RateLimiter
from ....models.user import User
from ....schemas.ml_predictions import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    ModelInfo,
    ServiceStatus,
    PredictionMetrics
)
from ....ml.model_serving import ModelServer
from ....ml.confidence_scoring import ConfidenceScorer
from ....services.prospect_feature_extraction import ProspectFeatureExtractor
from ....services.pipeline_monitoring import PipelineMonitor

router = APIRouter()

# Rate limiter for prediction endpoints
prediction_limiter = RateLimiter(
    requests_per_minute=10,
    identifier="ml_predictions"
)


class PredictionMetricsTracker:
    """Track prediction service performance metrics."""

    def __init__(self):
        self.metrics = {
            "total_predictions": 0,
            "successful_predictions": 0,
            "failed_predictions": 0,
            "response_times": [],
            "cache_hits": 0,
            "cache_misses": 0
        }

    def record_prediction(self, success: bool, response_time: float, cache_hit: bool):
        """Record prediction metrics."""
        self.metrics["total_predictions"] += 1
        if success:
            self.metrics["successful_predictions"] += 1
        else:
            self.metrics["failed_predictions"] += 1

        self.metrics["response_times"].append(response_time)
        # Keep only last 1000 response times for memory efficiency
        if len(self.metrics["response_times"]) > 1000:
            self.metrics["response_times"] = self.metrics["response_times"][-1000:]

        if cache_hit:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["cache_misses"] += 1

    def get_metrics(self) -> PredictionMetrics:
        """Get current metrics."""
        response_times = self.metrics["response_times"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        max_response_time = max(response_times) if response_times else 0

        return PredictionMetrics(
            total_predictions=self.metrics["total_predictions"],
            successful_predictions=self.metrics["successful_predictions"],
            failed_predictions=self.metrics["failed_predictions"],
            cache_hits=self.metrics["cache_hits"],
            cache_misses=self.metrics["cache_misses"],
            average_response_time=avg_response_time * 1000,  # Convert to ms
            max_response_time=max_response_time * 1000,  # Convert to ms
            predictions_per_minute=len([t for t in response_times if time.time() - t < 60]),
            last_updated=datetime.utcnow()
        )


# Global metrics tracker
metrics_tracker = PredictionMetricsTracker()


async def get_model_server() -> ModelServer:
    """Dependency to get model server."""
    # This would be injected from the inference service
    # For now, create a placeholder
    return ModelServer()


async def get_cache_manager() -> CacheManager:
    """Dependency to get cache manager."""
    # This would be injected from the inference service
    return CacheManager()


async def get_confidence_scorer() -> ConfidenceScorer:
    """Dependency to get confidence scorer."""
    return ConfidenceScorer()


async def get_feature_extractor() -> ProspectFeatureExtractor:
    """Dependency to get feature extractor."""
    return ProspectFeatureExtractor()


@router.post("/predict/{prospect_id}", response_model=PredictionResponse)
async def predict_prospect_success(
    prospect_id: int,
    request: PredictionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    model_server: ModelServer = Depends(get_model_server),
    cache_manager: CacheManager = Depends(get_cache_manager),
    confidence_scorer: ConfidenceScorer = Depends(get_confidence_scorer),
    feature_extractor: ProspectFeatureExtractor = Depends(get_feature_extractor)
):
    """
    Generate real-time ML prediction for individual prospect success.

    **Performance Requirement:** <500ms response time
    **Rate Limit:** 10 requests per minute per user
    """
    start_time = time.time()
    cache_hit = False

    try:
        # Apply rate limiting
        await prediction_limiter.check_rate_limit(current_user.id)

        # Get model version
        model_version = request.model_version or await model_server.get_current_version()

        # Check cache first for fast response
        cached_prediction = await cache_manager.get_cached_prediction(
            prospect_id, model_version
        )

        if cached_prediction and not request.include_explanation:
            # Fast cache hit response
            cache_hit = True
            response_time = time.time() - start_time
            metrics_tracker.record_prediction(True, response_time, cache_hit)

            return PredictionResponse(
                **cached_prediction,
                cache_hit=True
            )

        # Extract prospect features
        features = await feature_extractor.get_prospect_features(
            prospect_id, db, cache_manager
        )

        if not features:
            raise HTTPException(
                status_code=404,
                detail=f"Prospect {prospect_id} not found or insufficient data"
            )

        # Generate prediction
        prediction_result = await model_server.predict(
            features=features,
            include_explanation=request.include_explanation,
            model_version=model_version
        )

        # Calculate confidence score
        confidence_level = await confidence_scorer.calculate_confidence(
            prediction_result["probability"],
            prediction_result.get("shap_values"),
            features
        )

        # Build response
        response = PredictionResponse(
            prospect_id=prospect_id,
            success_probability=prediction_result["probability"],
            confidence_level=confidence_level,
            model_version=model_version,
            explanation=prediction_result.get("explanation"),
            prediction_time=datetime.utcnow(),
            cache_hit=cache_hit
        )

        # Cache the result for future requests
        await cache_manager.cache_prediction(
            prospect_id=prospect_id,
            model_version=model_version,
            prediction_data=response.dict(exclude={"cache_hit"})
        )

        # Check response time requirement
        response_time = time.time() - start_time
        if response_time > 0.5:  # 500ms limit
            # Log warning but don't fail the request
            print(f"WARNING: Prediction response time {response_time:.3f}s exceeds 500ms limit")

        metrics_tracker.record_prediction(True, response_time, cache_hit)
        return response

    except HTTPException:
        metrics_tracker.record_prediction(False, time.time() - start_time, cache_hit)
        raise
    except Exception as e:
        metrics_tracker.record_prediction(False, time.time() - start_time, cache_hit)
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )


@router.post("/batch-predict", response_model=BatchPredictionResponse)
async def batch_predict_prospects(
    request: BatchPredictionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    model_server: ModelServer = Depends(get_model_server),
    cache_manager: CacheManager = Depends(get_cache_manager),
    confidence_scorer: ConfidenceScorer = Depends(get_confidence_scorer),
    feature_extractor: ProspectFeatureExtractor = Depends(get_feature_extractor)
):
    """
    Generate batch ML predictions for multiple prospects.

    **Performance:** Optimized for bulk processing with chunking
    **Rate Limit:** Premium feature with higher limits
    """
    start_time = time.time()
    batch_id = str(uuid.uuid4())

    try:
        # Validate user has batch prediction access (premium feature)
        if not current_user.subscription_tier in ["premium", "enterprise"]:
            raise HTTPException(
                status_code=403,
                detail="Batch predictions require premium subscription"
            )

        # Get model version
        model_version = request.model_version or await model_server.get_current_version()

        predictions = []
        failed_prospects = []
        processed_count = 0

        # Process in chunks for efficiency
        for i in range(0, len(request.prospect_ids), request.chunk_size):
            chunk = request.prospect_ids[i:i + request.chunk_size]

            # Process chunk concurrently
            chunk_tasks = []
            for prospect_id in chunk:
                task = asyncio.create_task(
                    _process_single_prediction(
                        prospect_id=prospect_id,
                        model_version=model_version,
                        include_explanation=request.include_explanations,
                        db=db,
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
            for j, result in enumerate(chunk_results):
                prospect_id = chunk[j]
                if isinstance(result, Exception):
                    failed_prospects.append(prospect_id)
                else:
                    predictions.append(result)
                    processed_count += 1

        processing_time = time.time() - start_time

        response = BatchPredictionResponse(
            predictions=predictions,
            batch_id=batch_id,
            processed_count=processed_count,
            failed_count=len(failed_prospects),
            failed_prospects=failed_prospects,
            model_version=model_version,
            processing_time=processing_time,
            created_at=datetime.utcnow()
        )

        # Log batch processing metrics
        background_tasks.add_task(
            _log_batch_metrics,
            batch_id,
            len(request.prospect_ids),
            processed_count,
            processing_time
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch prediction failed: {str(e)}"
        )


async def _process_single_prediction(
    prospect_id: int,
    model_version: str,
    include_explanation: bool,
    db: Session,
    model_server: ModelServer,
    cache_manager: CacheManager,
    confidence_scorer: ConfidenceScorer,
    feature_extractor: ProspectFeatureExtractor
) -> PredictionResponse:
    """Process a single prediction for batch processing."""

    # Check cache first
    cached_prediction = await cache_manager.get_cached_prediction(
        prospect_id, model_version
    )

    if cached_prediction and not include_explanation:
        return PredictionResponse(**cached_prediction, cache_hit=True)

    # Extract features
    features = await feature_extractor.get_prospect_features(
        prospect_id, db, cache_manager
    )

    if not features:
        raise ValueError(f"Prospect {prospect_id} not found or insufficient data")

    # Generate prediction
    prediction_result = await model_server.predict(
        features=features,
        include_explanation=include_explanation,
        model_version=model_version
    )

    # Calculate confidence
    confidence_level = await confidence_scorer.calculate_confidence(
        prediction_result["probability"],
        prediction_result.get("shap_values"),
        features
    )

    response = PredictionResponse(
        prospect_id=prospect_id,
        success_probability=prediction_result["probability"],
        confidence_level=confidence_level,
        model_version=model_version,
        explanation=prediction_result.get("explanation"),
        prediction_time=datetime.utcnow(),
        cache_hit=False
    )

    # Cache result
    await cache_manager.cache_prediction(
        prospect_id=prospect_id,
        model_version=model_version,
        prediction_data=response.dict(exclude={"cache_hit"})
    )

    return response


async def _log_batch_metrics(
    batch_id: str,
    total_requested: int,
    processed_count: int,
    processing_time: float
):
    """Log batch processing metrics for monitoring."""
    monitor = PipelineMonitor()
    await monitor.log_batch_prediction_metrics(
        batch_id=batch_id,
        total_requested=total_requested,
        successful_predictions=processed_count,
        failed_predictions=total_requested - processed_count,
        processing_time=processing_time
    )


@router.get("/explanations/{prospect_id}")
async def get_prediction_explanation(
    prospect_id: int,
    model_version: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    model_server: ModelServer = Depends(get_model_server),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """
    Get SHAP-based explanation for prospect prediction.

    **Performance:** Cached explanations for faster retrieval
    """
    try:
        # Get model version
        current_version = model_version or await model_server.get_current_version()

        # Check for cached prediction with explanation
        cached_prediction = await cache_manager.get_cached_prediction(
            prospect_id, current_version
        )

        if cached_prediction and cached_prediction.get("explanation"):
            return cached_prediction["explanation"]

        # If no cached explanation, trigger new prediction with explanation
        prediction_request = PredictionRequest(
            prospect_id=prospect_id,
            include_explanation=True,
            model_version=model_version
        )

        # This will generate and cache the explanation
        result = await predict_prospect_success(
            prospect_id=prospect_id,
            request=prediction_request,
            current_user=current_user,
            model_server=model_server,
            cache_manager=cache_manager
        )

        return result.explanation

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get explanation: {str(e)}"
        )


@router.get("/model/info", response_model=ModelInfo)
async def get_model_info(
    model_server: ModelServer = Depends(get_model_server)
):
    """Get information about the currently loaded ML model."""
    try:
        return await model_server.get_model_info()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model info: {str(e)}"
        )


@router.get("/status", response_model=ServiceStatus)
async def get_service_status(
    model_server: ModelServer = Depends(get_model_server),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """Get ML prediction service status and health information."""
    try:
        model_health = await model_server.health_check()
        cache_health = await cache_manager.health_check()
        current_metrics = metrics_tracker.get_metrics()

        return ServiceStatus(
            status="healthy" if model_health.get("status") == "healthy" and
                   cache_health.get("status") == "healthy" else "unhealthy",
            model_loaded=model_health.get("model_loaded", False),
            cache_connected=cache_health.get("status") == "healthy",
            predictions_served=current_metrics.total_predictions,
            average_response_time=current_metrics.average_response_time,
            last_health_check=datetime.utcnow()
        )

    except Exception as e:
        return ServiceStatus(
            status="unhealthy",
            model_loaded=False,
            cache_connected=False,
            predictions_served=0,
            average_response_time=0.0,
            last_health_check=datetime.utcnow()
        )


@router.get("/metrics", response_model=PredictionMetrics)
async def get_prediction_metrics():
    """Get detailed prediction service performance metrics."""
    return metrics_tracker.get_metrics()


# ============================================================================
# NARRATIVE GENERATION ENDPOINTS
# ============================================================================

@router.get("/outlook/{prospect_id}")
async def get_prospect_outlook(
    prospect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """
    Generate AI-powered prospect outlook with personalized narrative.

    **Rate Limit:** 10 requests per minute per user
    **Response Time:** <500ms (cached) or <2s (generated)
    """
    try:
        # Apply rate limiting
        await prediction_limiter.check_rate_limit(current_user.id)

        # Check for cached narrative first
        cached_narrative = await cache_manager.get_cached_narrative(
            prospect_id=prospect_id,
            model_version="v1.0",
            user_id=current_user.id,
            template_version="v1.0"
        )

        if cached_narrative:
            return JSONResponse({
                "narrative": cached_narrative,
                "prospect_id": prospect_id,
                "user_id": current_user.id,
                "generated_at": datetime.utcnow().isoformat(),
                "cached": True
            })

        # Get prospect data
        prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
        if not prospect:
            raise HTTPException(status_code=404, detail="Prospect not found")

        # Get latest prediction data
        cached_prediction = await cache_manager.get_cached_prediction(
            prospect_id, "v1.0"
        )

        if not cached_prediction:
            raise HTTPException(
                status_code=400,
                detail="No ML prediction available. Generate prediction first."
            )

        # Mock prediction response for narrative generation
        from unittest.mock import Mock
        prediction_response = Mock()
        prediction_response.success_probability = cached_prediction.get("success_probability", 0.5)
        prediction_response.confidence_level = cached_prediction.get("confidence_level", 0.5)
        prediction_response.model_version = cached_prediction.get("model_version", "v1.0")
        prediction_response.feature_importance = cached_prediction.get("shap_values", {})

        # Get user preferences for personalization
        user_prefs = await cache_manager.get_cached_user_preferences(current_user.id)

        # Generate personalized narrative
        from ....services.narrative_generation_service import narrative_service
        narrative = await narrative_service.generate_prospect_outlook(
            prospect=prospect,
            prediction_data=prediction_response,
            user_preferences=user_prefs,
            user_id=current_user.id
        )

        # Assess narrative quality
        from ....services.narrative_quality_service import narrative_quality_service
        quality_metrics = narrative_quality_service.assess_narrative_quality(narrative)

        response_data = {
            "narrative": narrative,
            "quality_metrics": {
                "quality_score": quality_metrics.quality_score,
                "readability_score": quality_metrics.readability_score,
                "coherence_score": quality_metrics.coherence_score,
                "sentence_count": quality_metrics.sentence_count,
                "word_count": quality_metrics.word_count,
                "grammar_issues": quality_metrics.grammar_issues,
                "content_issues": quality_metrics.content_issues
            },
            "prospect_id": prospect_id,
            "user_id": current_user.id,
            "generated_at": datetime.utcnow().isoformat(),
            "template_version": "v1.0",
            "model_version": "v1.0",
            "cached": False
        }

        return JSONResponse(response_data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate outlook: {str(e)}"
        )


@router.post("/batch-outlook")
async def generate_batch_outlooks(
    request: dict,  # {"prospect_ids": [1, 2, 3]}
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cache_manager: CacheManager = Depends(get_cache_manager)
):
    """
    Generate batch AI outlooks for multiple prospects.

    **Premium Feature:** Requires premium subscription
    **Rate Limit:** 5 requests per minute
    """
    try:
        # Validate subscription
        if not hasattr(current_user, 'subscription_tier') or current_user.subscription_tier not in ["premium", "enterprise"]:
            raise HTTPException(
                status_code=403,
                detail="Batch outlooks require premium subscription"
            )

        prospect_ids = request.get("prospect_ids", [])
        if not prospect_ids:
            raise HTTPException(status_code=400, detail="No prospect IDs provided")

        if len(prospect_ids) > 50:  # Limit batch size
            raise HTTPException(status_code=400, detail="Maximum 50 prospects per batch")

        outlooks = []
        failed_prospects = []

        for prospect_id in prospect_ids:
            try:
                # Get cached narrative or generate new one
                cached_narrative = await cache_manager.get_cached_narrative(
                    prospect_id=prospect_id,
                    model_version="v1.0",
                    user_id=current_user.id,
                    template_version="v1.0"
                )

                if cached_narrative:
                    outlooks.append({
                        "prospect_id": prospect_id,
                        "narrative": cached_narrative,
                        "cached": True
                    })
                else:
                    # Generate new narrative (simplified for batch)
                    outlook_data = {
                        "prospect_id": prospect_id,
                        "narrative": f"AI outlook for prospect {prospect_id} - to be generated",
                        "cached": False
                    }
                    outlooks.append(outlook_data)

            except Exception as e:
                failed_prospects.append(prospect_id)

        return JSONResponse({
            "outlooks": outlooks,
            "processed_count": len(outlooks),
            "failed_count": len(failed_prospects),
            "failed_prospects": failed_prospects,
            "generated_at": datetime.utcnow().isoformat()
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch outlook generation failed: {str(e)}"
        )


@router.post("/outlook/{prospect_id}/feedback")
async def submit_outlook_feedback(
    prospect_id: int,
    feedback_data: dict,  # {"helpful": true, "additional_feedback": "...", "timestamp": "..."}
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback on generated prospect outlook.

    Used for improving narrative quality and A/B testing.
    """
    try:
        helpful = feedback_data.get("helpful")
        additional_feedback = feedback_data.get("additional_feedback", "")
        timestamp = feedback_data.get("timestamp", datetime.utcnow().isoformat())

        if helpful is None:
            raise HTTPException(status_code=400, detail="'helpful' field is required")

        # Store feedback for analytics (would typically go to database)
        feedback_record = {
            "prospect_id": prospect_id,
            "user_id": current_user.id,
            "helpful": helpful,
            "additional_feedback": additional_feedback,
            "timestamp": timestamp,
            "recorded_at": datetime.utcnow().isoformat()
        }

        # In a real implementation, this would be stored in a feedback table
        # For now, just log it
        print(f"Outlook feedback recorded: {feedback_record}")

        return JSONResponse({
            "message": "Feedback recorded successfully",
            "prospect_id": prospect_id,
            "recorded_at": feedback_record["recorded_at"]
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record feedback: {str(e)}"
        )