"""Pydantic schemas for ML prediction requests and responses."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, validator


class ConfidenceLevel(str, Enum):
    """Confidence level classifications for ML predictions."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class PredictionRequest(BaseModel):
    """Request schema for individual prospect prediction."""
    prospect_id: int = Field(..., description="Unique prospect identifier")
    include_explanation: bool = Field(True, description="Include SHAP explanation in response")
    model_version: Optional[str] = Field(None, description="Specific model version to use")


class BatchPredictionRequest(BaseModel):
    """Request schema for batch prospect predictions."""
    prospect_ids: List[int] = Field(..., description="List of prospect IDs to predict")
    include_explanations: bool = Field(False, description="Include SHAP explanations (slower)")
    model_version: Optional[str] = Field(None, description="Specific model version to use")
    chunk_size: int = Field(100, description="Batch processing chunk size")

    @validator('prospect_ids')
    def validate_prospect_ids(cls, v):
        if len(v) == 0:
            raise ValueError("Must provide at least one prospect ID")
        if len(v) > 1000:
            raise ValueError("Cannot process more than 1000 prospects in a single batch")
        return v

    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v < 1 or v > 500:
            raise ValueError("Chunk size must be between 1 and 500")
        return v


class FeatureImportance(BaseModel):
    """Feature importance from SHAP explanation."""
    feature_name: str = Field(..., description="Name of the feature")
    importance: float = Field(..., description="SHAP importance value")
    feature_value: Any = Field(..., description="Actual feature value for this prospect")


class PredictionExplanation(BaseModel):
    """SHAP-based explanation for a prediction."""
    feature_importances: List[FeatureImportance] = Field(
        ..., description="Top feature importances affecting prediction"
    )
    base_probability: float = Field(..., description="Model base probability")
    narrative: str = Field(..., description="Human-readable explanation")


class PredictionResponse(BaseModel):
    """Response schema for individual prospect prediction."""
    prospect_id: int = Field(..., description="Unique prospect identifier")
    success_probability: float = Field(
        ...,
        description="Probability of MLB success (0.0 to 1.0)",
        ge=0.0,
        le=1.0
    )
    confidence_level: ConfidenceLevel = Field(..., description="Prediction confidence level")
    model_version: str = Field(..., description="Model version used for prediction")
    explanation: Optional[PredictionExplanation] = Field(
        None, description="SHAP-based prediction explanation"
    )
    prediction_time: datetime = Field(..., description="When prediction was generated")
    cache_hit: bool = Field(False, description="Whether result was served from cache")


class BatchPredictionResponse(BaseModel):
    """Response schema for batch prospect predictions."""
    predictions: List[PredictionResponse] = Field(..., description="Individual prediction results")
    batch_id: str = Field(..., description="Unique identifier for this batch")
    processed_count: int = Field(..., description="Number of prospects successfully processed")
    failed_count: int = Field(..., description="Number of prospects that failed processing")
    failed_prospects: List[int] = Field([], description="IDs of prospects that failed")
    model_version: str = Field(..., description="Model version used for predictions")
    processing_time: float = Field(..., description="Total processing time in seconds")
    created_at: datetime = Field(..., description="When batch was processed")


class PredictionError(BaseModel):
    """Error response for prediction failures."""
    prospect_id: int = Field(..., description="Prospect ID that failed")
    error_code: str = Field(..., description="Error classification code")
    error_message: str = Field(..., description="Human-readable error message")
    timestamp: datetime = Field(..., description="When error occurred")


class ModelInfo(BaseModel):
    """Information about the currently loaded model."""
    model_version: str = Field(..., description="Current model version")
    model_name: str = Field(..., description="Model name/identifier")
    trained_at: datetime = Field(..., description="When model was trained")
    accuracy: float = Field(..., description="Model validation accuracy")
    features_count: int = Field(..., description="Number of features in model")
    last_loaded: datetime = Field(..., description="When model was last loaded")


class ServiceStatus(BaseModel):
    """Overall service status and health information."""
    status: str = Field(..., description="Service status (healthy/unhealthy)")
    model_loaded: bool = Field(..., description="Whether ML model is loaded")
    cache_connected: bool = Field(..., description="Whether Redis cache is connected")
    predictions_served: int = Field(..., description="Total predictions served")
    average_response_time: float = Field(..., description="Average response time in ms")
    last_health_check: datetime = Field(..., description="Last health check timestamp")


class PredictionMetrics(BaseModel):
    """Service performance metrics."""
    total_predictions: int = Field(0, description="Total predictions served")
    successful_predictions: int = Field(0, description="Successful predictions")
    failed_predictions: int = Field(0, description="Failed predictions")
    cache_hits: int = Field(0, description="Cache hit count")
    cache_misses: int = Field(0, description="Cache miss count")
    average_response_time: float = Field(0.0, description="Average response time in ms")
    max_response_time: float = Field(0.0, description="Maximum response time in ms")
    predictions_per_minute: float = Field(0.0, description="Current predictions per minute")
    last_updated: datetime = Field(..., description="When metrics were last updated")