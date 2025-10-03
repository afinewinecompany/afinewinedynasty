"""
Pydantic schemas for watchlist API endpoints

@module WatchlistSchemas
@version 1.0.0
@since 1.0.0
"""

from pydantic import BaseModel, Field
from typing import Optional


class WatchlistAddRequest(BaseModel):
    """Request to add prospect to watchlist"""
    prospect_id: int = Field(..., description="Prospect ID to add")
    notes: Optional[str] = Field(None, description="Optional notes")
    notify_on_changes: bool = Field(True, description="Enable change notifications")


class WatchlistUpdateNotesRequest(BaseModel):
    """Request to update watchlist notes"""
    notes: str = Field(..., description="Updated notes content")


class WatchlistToggleNotificationsRequest(BaseModel):
    """Request to toggle notifications"""
    enabled: bool = Field(..., description="Enable or disable notifications")


class WatchlistEntry(BaseModel):
    """Watchlist entry response"""
    id: int
    prospect_id: int
    prospect_name: str
    prospect_position: str
    prospect_organization: Optional[str]
    notes: Optional[str]
    added_at: str
    notify_on_changes: bool

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "prospect_id": 42,
                "prospect_name": "Bobby Witt Jr.",
                "prospect_position": "SS",
                "prospect_organization": "KC",
                "notes": "Great bat speed, solid defense",
                "added_at": "2025-10-03T12:00:00",
                "notify_on_changes": True
            }
        }
