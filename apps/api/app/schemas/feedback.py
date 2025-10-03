"""Pydantic schemas for feedback operations."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """Schema for creating feedback."""
    type: str = Field(..., description="Feedback type: bug, feature_request, general, nps")
    rating: Optional[int] = Field(None, ge=1, le=10)
    message: Optional[str] = None
    feature_request: Optional[str] = None


class FeedbackResponse(BaseModel):
    """Schema for feedback API response."""
    id: int
    user_id: int
    type: str
    rating: Optional[int]
    message: Optional[str]
    feature_request: Optional[str]
    submitted_at: datetime

    class Config:
        from_attributes = True
