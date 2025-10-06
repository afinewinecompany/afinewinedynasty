"""Pydantic models for user lineups"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


# Lineup Prospect Models

class LineupProspectBase(BaseModel):
    """Base model for lineup prospect relationship"""
    prospect_id: int
    position: Optional[str] = None
    rank: Optional[int] = None
    notes: Optional[str] = None


class LineupProspectCreate(LineupProspectBase):
    """Model for adding a prospect to a lineup"""
    pass


class LineupProspectUpdate(BaseModel):
    """Model for updating a prospect in a lineup"""
    position: Optional[str] = None
    rank: Optional[int] = None
    notes: Optional[str] = None


class LineupProspectResponse(LineupProspectBase):
    """Response model for lineup prospect with full prospect details"""
    id: int
    lineup_id: int
    added_at: datetime

    # Nested prospect information
    prospect_name: Optional[str] = None
    prospect_position: Optional[str] = None
    prospect_organization: Optional[str] = None
    prospect_eta: Optional[int] = None

    class Config:
        from_attributes = True


# User Lineup Models

class UserLineupBase(BaseModel):
    """Base model for user lineups"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: bool = False
    lineup_type: str = Field(default='custom', pattern='^(custom|fantrax_sync|watchlist)$')
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @validator('name')
    def validate_name(cls, v):
        """Validate lineup name is not empty or just whitespace"""
        if not v or not v.strip():
            raise ValueError('Lineup name cannot be empty')
        return v.strip()


class UserLineupCreate(UserLineupBase):
    """Model for creating a new lineup"""
    pass


class UserLineupUpdate(BaseModel):
    """Model for updating a lineup"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    is_public: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None

    @validator('name')
    def validate_name(cls, v):
        """Validate lineup name if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Lineup name cannot be empty')
        return v.strip() if v else v


class UserLineupResponse(UserLineupBase):
    """Response model for a lineup without prospects"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    prospect_count: Optional[int] = 0

    class Config:
        from_attributes = True


class UserLineupDetailResponse(UserLineupResponse):
    """Response model for a lineup with full prospect details"""
    prospects: List[LineupProspectResponse] = []

    class Config:
        from_attributes = True


class UserLineupListResponse(BaseModel):
    """Response model for listing lineups"""
    lineups: List[UserLineupResponse]
    total: int


# Fantrax Sync Models

class FantraxSyncRequest(BaseModel):
    """Request model for syncing a Fantrax league to a lineup"""
    league_id: int
    lineup_name: Optional[str] = None

    @validator('lineup_name')
    def validate_lineup_name(cls, v):
        """Validate lineup name if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Lineup name cannot be empty')
        return v.strip() if v else v


class FantraxSyncResponse(BaseModel):
    """Response model for Fantrax sync operation"""
    lineup_id: int
    lineup_name: str
    prospects_synced: int
    success: bool
    message: str


# Bulk Operations

class BulkAddProspectsRequest(BaseModel):
    """Request model for adding multiple prospects to a lineup"""
    prospect_ids: List[int] = Field(..., min_items=1, max_items=100)

    @validator('prospect_ids')
    def validate_unique_prospects(cls, v):
        """Ensure no duplicate prospect IDs"""
        if len(v) != len(set(v)):
            raise ValueError('Duplicate prospect IDs are not allowed')
        return v


class BulkAddProspectsResponse(BaseModel):
    """Response model for bulk add operation"""
    added_count: int
    skipped_count: int
    errors: List[str] = []
    lineup_id: int
