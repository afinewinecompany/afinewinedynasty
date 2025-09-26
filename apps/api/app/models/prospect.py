"""Pydantic models for Prospect data validation."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator


class ProspectBase(BaseModel):
    """Base model for prospect data validation."""

    mlb_id: int = Field(..., description="MLB player ID")
    name: str = Field(..., min_length=1, max_length=255)
    position: Optional[str] = Field(None, max_length=10)
    organization: Optional[str] = Field(None, max_length=100)
    level: Optional[str] = Field(None, max_length=50)
    age: Optional[int] = Field(None, ge=16, le=50)
    eta_year: Optional[int] = Field(None, ge=2024, le=2030)

    @validator('position')
    def validate_position(cls, v):
        """Validate position is a valid baseball position."""
        valid_positions = [
            'P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF',
            'DH', 'IF', 'OF', 'RHP', 'LHP', 'RP', 'SP'
        ]
        if v and v not in valid_positions:
            # Allow but log warning for unknown positions
            pass
        return v

    @validator('level')
    def validate_level(cls, v):
        """Validate minor league level."""
        valid_levels = [
            'MLB', 'Triple-A', 'Double-A', 'High-A', 'Low-A',
            'Rookie', 'Complex', 'DSL', 'FCL'
        ]
        if v and v not in valid_levels:
            # Allow but standardize if close match
            level_map = {
                'AAA': 'Triple-A',
                'AA': 'Double-A',
                'A+': 'High-A',
                'A': 'Low-A'
            }
            return level_map.get(v, v)
        return v

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "mlb_id": 123456,
                "name": "John Smith",
                "position": "SS",
                "organization": "New York Yankees",
                "level": "Double-A",
                "age": 22,
                "eta_year": 2026
            }
        }


class ProspectCreate(ProspectBase):
    """Model for creating a new prospect."""
    pass


class ProspectUpdate(BaseModel):
    """Model for updating prospect data."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    position: Optional[str] = Field(None, max_length=10)
    organization: Optional[str] = Field(None, max_length=100)
    level: Optional[str] = Field(None, max_length=50)
    age: Optional[int] = Field(None, ge=16, le=50)
    eta_year: Optional[int] = Field(None, ge=2024, le=2030)


class ProspectInDB(ProspectBase):
    """Model for prospect data from database."""

    id: int
    date_recorded: datetime
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ProspectWithStats(ProspectInDB):
    """Model for prospect with associated stats."""

    batting_avg: Optional[float] = Field(None, ge=0, le=1)
    on_base_pct: Optional[float] = Field(None, ge=0, le=1)
    slugging_pct: Optional[float] = Field(None, ge=0, le=2)
    era: Optional[float] = Field(None, ge=0)
    whip: Optional[float] = Field(None, ge=0)
    overall_grade: Optional[float] = Field(None, ge=20, le=80)