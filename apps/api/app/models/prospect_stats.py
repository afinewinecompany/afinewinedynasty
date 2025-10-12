"""Pydantic models for Prospect Statistics data validation."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ProspectStatsBase(BaseModel):
    """Base model for prospect statistics validation."""

    prospect_id: int = Field(..., description="Reference to prospect")
    date_recorded: datetime = Field(..., description="When stats were recorded")

    # Hitting stats
    games_played: Optional[int] = Field(None, ge=0)
    at_bats: Optional[int] = Field(None, ge=0)
    hits: Optional[int] = Field(None, ge=0)
    home_runs: Optional[int] = Field(None, ge=0)
    rbi: Optional[int] = Field(None, ge=0)
    batting_avg: Optional[float] = Field(None, ge=0, le=1)
    on_base_pct: Optional[float] = Field(None, ge=0, le=1)
    slugging_pct: Optional[float] = Field(None, ge=0, le=2)

    # Pitching stats
    innings_pitched: Optional[float] = Field(None, ge=0)
    era: Optional[float] = Field(None, ge=0, le=100)
    whip: Optional[float] = Field(None, ge=0, le=10)
    strikeouts_per_nine: Optional[float] = Field(None, ge=0, le=30)

    # Advanced metrics
    woba: Optional[float] = Field(None, ge=0, le=1)
    wrc_plus: Optional[float] = Field(None, ge=0, le=500)

    @field_validator('batting_avg', 'on_base_pct', 'slugging_pct', 'woba')
    @classmethod
    def validate_percentages(cls, v, field):
        """Ensure percentage stats are in proper decimal format."""
        if v is not None:
            # Convert from percentage to decimal if needed
            if v > 1 and field.name in ['batting_avg', 'on_base_pct', 'woba']:
                return v / 1000 if v > 100 else v / 100
            elif v > 2 and field.name == 'slugging_pct':
                return v / 1000
        return v

    @field_validator('hits')
    @classmethod
    def validate_hits(cls, v, values):
        """Hits cannot exceed at bats."""
        if v is not None and 'at_bats' in values:
            at_bats = values['at_bats']
            if at_bats and v > at_bats:
                raise ValueError('Hits cannot exceed at bats')
        return v

    @field_validator('era', 'whip')
    @classmethod
    def validate_pitching_rates(cls, v):
        """Validate pitching rate stats are reasonable."""
        if v is not None:
            # ERA above 20 or WHIP above 5 are likely errors
            if v > 20:
                # Log warning but allow
                pass
        return v

    class Config:
        orm_mode = True
        json_schema_extra = {
            "example": {
                "prospect_id": 1,
                "date_recorded": "2025-01-15T00:00:00",
                "games_played": 120,
                "at_bats": 450,
                "hits": 135,
                "home_runs": 25,
                "rbi": 85,
                "batting_avg": 0.300,
                "on_base_pct": 0.380,
                "slugging_pct": 0.550,
                "woba": 0.370,
                "wrc_plus": 130
            }
        }


class ProspectStatsCreate(ProspectStatsBase):
    """Model for creating new prospect stats."""
    pass


class ProspectStatsUpdate(BaseModel):
    """Model for updating prospect stats."""

    games_played: Optional[int] = Field(None, ge=0)
    at_bats: Optional[int] = Field(None, ge=0)
    hits: Optional[int] = Field(None, ge=0)
    home_runs: Optional[int] = Field(None, ge=0)
    rbi: Optional[int] = Field(None, ge=0)
    batting_avg: Optional[float] = Field(None, ge=0, le=1)
    on_base_pct: Optional[float] = Field(None, ge=0, le=1)
    slugging_pct: Optional[float] = Field(None, ge=0, le=2)
    innings_pitched: Optional[float] = Field(None, ge=0)
    era: Optional[float] = Field(None, ge=0)
    whip: Optional[float] = Field(None, ge=0)
    strikeouts_per_nine: Optional[float] = Field(None, ge=0)
    woba: Optional[float] = Field(None, ge=0, le=1)
    wrc_plus: Optional[float] = Field(None, ge=0)


class ProspectStatsInDB(ProspectStatsBase):
    """Model for prospect stats from database."""

    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True


class ProspectStatsAggregated(BaseModel):
    """Model for aggregated prospect statistics."""

    prospect_id: int
    total_games: int
    avg_batting_avg: Optional[float]
    avg_on_base_pct: Optional[float]
    avg_slugging_pct: Optional[float]
    total_home_runs: Optional[int]
    total_rbi: Optional[int]
    avg_era: Optional[float]
    avg_whip: Optional[float]
    latest_level: Optional[str]
    stats_count: int