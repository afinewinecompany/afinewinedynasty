from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum


class PositionEnum(str, Enum):
    """Baseball positions."""
    C = "C"    # Catcher
    P = "P"    # Pitcher
    IF1B = "1B"  # First Base
    IF2B = "2B"  # Second Base
    IF3B = "3B"  # Third Base
    SS = "SS"    # Shortstop
    OF = "OF"    # Outfield
    LF = "LF"    # Left Field
    CF = "CF"    # Center Field
    RF = "RF"    # Right Field
    DH = "DH"    # Designated Hitter
    UTIL = "UTIL"  # Utility


class LevelEnum(str, Enum):
    """Minor league levels."""
    ROOKIE = "Rookie"
    A_MINUS = "A-"
    A = "A"
    A_PLUS = "A+"
    AA = "AA"
    AAA = "AAA"
    MLB = "MLB"


class MLBAPIPlayerResponse(BaseModel):
    """Schema for MLB API player response validation."""
    id: int = Field(..., description="MLB player ID")
    fullName: str = Field(..., description="Player full name")
    primaryPosition: Optional[Dict[str, Any]] = Field(None, description="Primary position info")
    currentTeam: Optional[Dict[str, Any]] = Field(None, description="Current team info")
    birthDate: Optional[str] = Field(None, description="Birth date in YYYY-MM-DD format")
    height: Optional[str] = Field(None, description="Player height")
    weight: Optional[int] = Field(None, description="Player weight")
    mlbDebutDate: Optional[str] = Field(None, description="MLB debut date")

    @validator('birthDate', 'mlbDebutDate', pre=True)
    def validate_date_format(cls, v):
        """Validate date format."""
        if v is None:
            return v
        if isinstance(v, str):
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
        return v

    @validator('weight')
    def validate_weight(cls, v):
        """Validate player weight."""
        if v is not None and (v < 100 or v > 350):
            raise ValueError(f"Invalid weight: {v}. Must be between 100-350 lbs")
        return v


class MLBAPIStatsResponse(BaseModel):
    """Schema for MLB API stats response validation."""
    stats: List[Dict[str, Any]] = Field(..., description="Statistics data")

    @validator('stats')
    def validate_stats_structure(cls, v):
        """Validate stats structure."""
        for stat in v:
            if 'type' not in stat or 'stats' not in stat:
                raise ValueError("Each stat must have 'type' and 'stats' fields")
        return v


class ProspectValidationSchema(BaseModel):
    """Schema for prospect data validation."""
    mlb_id: str = Field(..., min_length=1, max_length=20, description="MLB player ID")
    name: str = Field(..., min_length=2, max_length=100, description="Player name")
    position: str = Field(..., description="Player position")
    organization: Optional[str] = Field(None, max_length=100, description="Organization name")
    level: Optional[str] = Field(None, description="Minor league level")
    age: Optional[int] = Field(None, ge=16, le=50, description="Player age")
    eta_year: Optional[int] = Field(None, ge=2020, le=2035, description="Estimated arrival year")

    @validator('position')
    def validate_position(cls, v):
        """Validate position is a known baseball position."""
        valid_positions = [pos.value for pos in PositionEnum]
        if v not in valid_positions:
            # Allow position if it looks like a valid abbreviation
            if len(v) <= 4 and v.isalpha():
                return v
            raise ValueError(f"Invalid position: {v}")
        return v

    @validator('level')
    def validate_level(cls, v):
        """Validate minor league level."""
        if v is None:
            return v
        valid_levels = [level.value for level in LevelEnum]
        if v not in valid_levels:
            # Allow custom levels that look reasonable
            if len(v) <= 10:
                return v
            raise ValueError(f"Invalid level: {v}")
        return v


class HittingStatsValidationSchema(BaseModel):
    """Schema for hitting statistics validation."""
    games_played: Optional[int] = Field(None, ge=0, le=200, description="Games played")
    at_bats: Optional[int] = Field(None, ge=0, le=800, description="At bats")
    hits: Optional[int] = Field(None, ge=0, le=300, description="Hits")
    home_runs: Optional[int] = Field(None, ge=0, le=80, description="Home runs")
    rbi: Optional[int] = Field(None, ge=0, le=200, description="RBI")
    stolen_bases: Optional[int] = Field(None, ge=0, le=100, description="Stolen bases")
    walks: Optional[int] = Field(None, ge=0, le=200, description="Walks")
    strikeouts: Optional[int] = Field(None, ge=0, le=300, description="Strikeouts")
    batting_avg: Optional[float] = Field(None, ge=0.0, le=1.0, description="Batting average")
    on_base_pct: Optional[float] = Field(None, ge=0.0, le=1.0, description="On-base percentage")
    slugging_pct: Optional[float] = Field(None, ge=0.0, le=4.0, description="Slugging percentage")
    woba: Optional[float] = Field(None, ge=0.0, le=1.0, description="wOBA")
    wrc_plus: Optional[int] = Field(None, ge=0, le=300, description="wRC+")

    @root_validator
    def validate_hitting_consistency(cls, values):
        """Validate statistical consistency for hitting stats."""
        at_bats = values.get('at_bats')
        hits = values.get('hits')
        home_runs = values.get('home_runs')
        batting_avg = values.get('batting_avg')

        # Check hits vs at_bats consistency
        if at_bats is not None and hits is not None:
            if hits > at_bats:
                raise ValueError("Hits cannot exceed at-bats")

            # Check batting average consistency (allow small rounding differences)
            if batting_avg is not None and at_bats > 0:
                calculated_avg = hits / at_bats
                if abs(batting_avg - calculated_avg) > 0.01:
                    raise ValueError(f"Batting average {batting_avg} inconsistent with hits/at-bats")

        # Check home runs vs hits consistency
        if hits is not None and home_runs is not None:
            if home_runs > hits:
                raise ValueError("Home runs cannot exceed hits")

        return values


class PitchingStatsValidationSchema(BaseModel):
    """Schema for pitching statistics validation."""
    innings_pitched: Optional[float] = Field(None, ge=0.0, le=300.0, description="Innings pitched")
    earned_runs: Optional[int] = Field(None, ge=0, le=200, description="Earned runs")
    era: Optional[float] = Field(None, ge=0.0, le=20.0, description="ERA")
    whip: Optional[float] = Field(None, ge=0.0, le=5.0, description="WHIP")
    strikeouts_per_nine: Optional[float] = Field(None, ge=0.0, le=20.0, description="K/9")
    walks_per_nine: Optional[float] = Field(None, ge=0.0, le=15.0, description="BB/9")

    @root_validator
    def validate_pitching_consistency(cls, values):
        """Validate statistical consistency for pitching stats."""
        innings = values.get('innings_pitched')
        earned_runs = values.get('earned_runs')
        era = values.get('era')

        # Check ERA consistency
        if all(v is not None for v in [innings, earned_runs, era]) and innings > 0:
            calculated_era = (earned_runs * 9) / innings
            if abs(era - calculated_era) > 0.1:
                raise ValueError(f"ERA {era} inconsistent with earned runs/innings")

        return values


class ProspectStatsValidationSchema(BaseModel):
    """Schema for complete prospect statistics validation."""
    date: date = Field(..., description="Statistics date")
    season: int = Field(..., ge=1900, le=2050, description="Season year")

    # Hitting stats
    games_played: Optional[int] = Field(None, ge=0, le=200)
    at_bats: Optional[int] = Field(None, ge=0, le=800)
    hits: Optional[int] = Field(None, ge=0, le=300)
    home_runs: Optional[int] = Field(None, ge=0, le=80)
    rbi: Optional[int] = Field(None, ge=0, le=200)
    stolen_bases: Optional[int] = Field(None, ge=0, le=100)
    walks: Optional[int] = Field(None, ge=0, le=200)
    strikeouts: Optional[int] = Field(None, ge=0, le=300)
    batting_avg: Optional[float] = Field(None, ge=0.0, le=1.0)
    on_base_pct: Optional[float] = Field(None, ge=0.0, le=1.0)
    slugging_pct: Optional[float] = Field(None, ge=0.0, le=4.0)

    # Pitching stats
    innings_pitched: Optional[float] = Field(None, ge=0.0, le=300.0)
    earned_runs: Optional[int] = Field(None, ge=0, le=200)
    era: Optional[float] = Field(None, ge=0.0, le=20.0)
    whip: Optional[float] = Field(None, ge=0.0, le=5.0)
    strikeouts_per_nine: Optional[float] = Field(None, ge=0.0, le=20.0)
    walks_per_nine: Optional[float] = Field(None, ge=0.0, le=15.0)

    # Advanced metrics
    woba: Optional[float] = Field(None, ge=0.0, le=1.0)
    wrc_plus: Optional[int] = Field(None, ge=0, le=300)

    @validator('date')
    def validate_date_not_future(cls, v):
        """Validate date is not in the future."""
        if v > date.today():
            raise ValueError("Statistics date cannot be in the future")
        return v

    @validator('season')
    def validate_season_reasonable(cls, v):
        """Validate season is reasonable."""
        current_year = datetime.now().year
        if v > current_year + 1:
            raise ValueError(f"Season {v} is too far in the future")
        if v < current_year - 20:
            raise ValueError(f"Season {v} is too far in the past")
        return v


class ValidationResult(BaseModel):
    """Result of data validation."""
    is_valid: bool = Field(..., description="Whether data passed validation")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    data_quality_score: float = Field(..., ge=0.0, le=1.0, description="Data quality score")
    outliers_detected: List[Dict[str, Any]] = Field(default_factory=list, description="Statistical outliers")


class DataQualityReport(BaseModel):
    """Comprehensive data quality report."""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_records_validated: int = Field(..., ge=0)
    valid_records: int = Field(..., ge=0)
    invalid_records: int = Field(..., ge=0)
    validation_errors: Dict[str, int] = Field(default_factory=dict)
    outliers_summary: Dict[str, int] = Field(default_factory=dict)
    overall_quality_score: float = Field(..., ge=0.0, le=1.0)
    recommendations: List[str] = Field(default_factory=list)