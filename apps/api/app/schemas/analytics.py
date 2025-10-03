"""Pydantic schemas for analytics operations."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class AnalyticsEventCreate(BaseModel):
    """Schema for tracking analytics event."""
    event_name: str
    event_data: Optional[Dict[str, Any]] = None


class AnalyticsEventResponse(BaseModel):
    """Schema for analytics event API response."""
    id: int
    user_id: Optional[int]
    event_name: str
    event_data: Optional[Dict[str, Any]]
    timestamp: datetime

    class Config:
        from_attributes = True
