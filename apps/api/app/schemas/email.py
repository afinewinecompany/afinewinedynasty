"""
Pydantic schemas for email preferences and digest operations.

@module email
@since 1.0.0
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class EmailPreferencesBase(BaseModel):
    """
    Base schema for email preferences.

    @since 1.0.0
    """
    digest_enabled: bool = True
    frequency: str = "weekly"  # daily, weekly, monthly
    preferences: Dict[str, Any] = {}


class EmailPreferencesCreate(EmailPreferencesBase):
    """
    Schema for creating email preferences.

    @since 1.0.0
    """
    user_id: int


class EmailPreferencesUpdate(BaseModel):
    """
    Schema for updating email preferences.

    @since 1.0.0
    """
    digest_enabled: Optional[bool] = None
    frequency: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None


class EmailPreferencesResponse(EmailPreferencesBase):
    """
    Schema for email preferences API response.

    @since 1.0.0
    """
    id: int
    user_id: int
    last_sent: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DigestContentRequest(BaseModel):
    """
    Schema for requesting digest content preview.

    @since 1.0.0
    """
    user_id: int


class UnsubscribeRequest(BaseModel):
    """
    Schema for unsubscribe request.

    @since 1.0.0
    """
    token: str
