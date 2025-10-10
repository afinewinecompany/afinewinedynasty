"""Pydantic schemas for Fangraphs data validation."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator


class FangraphsScoutingGrades(BaseModel):
    """Scouting grades on the 20-80 scale."""

    hit: Optional[int] = Field(None, ge=20, le=80)
    power: Optional[int] = Field(None, ge=20, le=80)
    speed: Optional[int] = Field(None, ge=20, le=80)
    field: Optional[int] = Field(None, ge=20, le=80)
    arm: Optional[int] = Field(None, ge=20, le=80)
    overall: Optional[int] = Field(None, ge=20, le=80)

    @validator('*', pre=True)
    def round_to_nearest_5(cls, v):
        """Round grades to nearest 5 (20, 25, 30, ..., 80)."""
        if v is not None and isinstance(v, (int, float)):
            return round(v / 5) * 5
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "hit": 55,
                "power": 60,
                "speed": 50,
                "field": 45,
                "arm": 55,
                "overall": 55
            }
        }


class FangraphsStatistics(BaseModel):
    """Baseball statistics from Fangraphs."""

    # Batting statistics
    games: Optional[int] = Field(None, ge=0)
    plate_appearances: Optional[int] = Field(None, ge=0)
    at_bats: Optional[int] = Field(None, ge=0)
    hits: Optional[int] = Field(None, ge=0)
    doubles: Optional[int] = Field(None, ge=0)
    triples: Optional[int] = Field(None, ge=0)
    home_runs: Optional[int] = Field(None, ge=0)
    runs: Optional[int] = Field(None, ge=0)
    rbis: Optional[int] = Field(None, ge=0)
    walks: Optional[int] = Field(None, ge=0)
    strikeouts: Optional[int] = Field(None, ge=0)
    stolen_bases: Optional[int] = Field(None, ge=0)
    caught_stealing: Optional[int] = Field(None, ge=0)

    # Batting averages
    batting_avg: Optional[float] = Field(None, ge=0.0, le=1.0)
    on_base_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    slugging_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    ops: Optional[float] = Field(None, ge=0.0, le=3.0)

    # Advanced batting metrics
    wrc_plus: Optional[int] = Field(None, ge=0, le=300)
    war: Optional[float] = Field(None, ge=-10.0, le=15.0)
    woba: Optional[float] = Field(None, ge=0.0, le=1.0)
    iso: Optional[float] = Field(None, ge=0.0, le=1.0)
    babip: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Pitching statistics
    innings_pitched: Optional[float] = Field(None, ge=0.0)
    wins: Optional[int] = Field(None, ge=0)
    losses: Optional[int] = Field(None, ge=0)
    saves: Optional[int] = Field(None, ge=0)
    earned_runs: Optional[int] = Field(None, ge=0)
    era: Optional[float] = Field(None, ge=0.0, le=30.0)
    whip: Optional[float] = Field(None, ge=0.0, le=10.0)
    strikeouts_per_9: Optional[float] = Field(None, ge=0.0, le=20.0)
    walks_per_9: Optional[float] = Field(None, ge=0.0, le=20.0)
    home_runs_per_9: Optional[float] = Field(None, ge=0.0, le=10.0)

    # Advanced pitching metrics
    fip: Optional[float] = Field(None, ge=0.0, le=20.0)
    xfip: Optional[float] = Field(None, ge=0.0, le=20.0)
    siera: Optional[float] = Field(None, ge=0.0, le=20.0)

    # Season/level info
    year: Optional[int] = Field(None, ge=2000, le=2050)
    level: Optional[str] = None
    team: Optional[str] = None


class FangraphsBioInfo(BaseModel):
    """Biographical information for a prospect."""

    age: Optional[int] = Field(None, ge=15, le=50)
    height: Optional[str] = None
    weight: Optional[int] = Field(None, ge=100, le=400)
    bats: Optional[str] = Field(None, regex="^(L|R|S)$")
    throws: Optional[str] = Field(None, regex="^(L|R)$")
    position: Optional[str] = None
    organization: Optional[str] = None
    draft_year: Optional[int] = Field(None, ge=2000, le=2050)
    draft_round: Optional[int] = Field(None, ge=1, le=50)
    school: Optional[str] = None
    birthdate: Optional[datetime] = None


class FangraphsRankings(BaseModel):
    """Prospect rankings from various sources."""

    overall: Optional[int] = Field(None, ge=1, le=1000)
    organization: Optional[int] = Field(None, ge=1, le=100)
    position: Optional[int] = Field(None, ge=1, le=100)
    future_value: Optional[int] = Field(None, ge=20, le=80)


class FangraphsProspectData(BaseModel):
    """Complete prospect data from Fangraphs."""

    name: str
    source: str = "fangraphs"
    fetched_at: datetime
    scouting_grades: Optional[FangraphsScoutingGrades] = None
    statistics: Optional[Dict[str, FangraphsStatistics]] = Field(default_factory=dict)
    rankings: Optional[FangraphsRankings] = None
    bio: Optional[FangraphsBioInfo] = None
    profile_url: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Jackson Holliday",
                "source": "fangraphs",
                "fetched_at": "2025-01-15T12:00:00Z",
                "scouting_grades": {
                    "hit": 60,
                    "power": 55,
                    "speed": 55,
                    "field": 50,
                    "arm": 50,
                    "overall": 60
                },
                "rankings": {
                    "overall": 1,
                    "organization": 1,
                    "position": 1,
                    "future_value": 60
                }
            }
        }


class FangraphsProspectListItem(BaseModel):
    """Item in prospect rankings list."""

    rank: int = Field(..., ge=1, le=1000)
    name: str
    organization: str
    position: str
    eta: Optional[str] = None
    profile_url: Optional[str] = None

    @validator('rank', pre=True)
    def parse_rank(cls, v):
        """Parse rank from string if needed."""
        if isinstance(v, str):
            # Remove '#' or other non-numeric characters
            rank_str = ''.join(c for c in v if c.isdigit())
            return int(rank_str) if rank_str else None
        return v


class FangraphsDataResponse(BaseModel):
    """Response for Fangraphs data requests."""

    success: bool
    data: Optional[FangraphsProspectData] = None
    error: Optional[str] = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class FangraphsBatchResponse(BaseModel):
    """Response for batch Fangraphs data requests."""

    success: bool
    total_requested: int
    total_fetched: int
    prospects: List[FangraphsProspectData] = Field(default_factory=list)
    errors: List[Dict[str, str]] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)